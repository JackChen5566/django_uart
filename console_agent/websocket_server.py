from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from .command_manager import CommandManager
from .config import AgentConfig, load_config
from .serial_manager import SerialManager, SerialSession, SerialSettings


LOGGER = logging.getLogger("console-agent")


@web.middleware
async def cors_middleware(request: web.Request, handler: web.RequestHandler) -> web.StreamResponse:
    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        response = await handler(request)

    config: AgentConfig = request.app["config"]
    origin = request.headers.get("Origin")
    if "*" in config.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = "*"
    elif origin in config.cors_origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"

    response.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    return response


def create_app(config: AgentConfig) -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app["config"] = config
    app["commands"] = CommandManager(config.commands)
    app.router.add_get("/api/status", status)
    app.router.add_get("/api/ports", ports)
    app.router.add_post("/api/connect", connect)
    app.router.add_get("/api/commands", commands)
    app.router.add_get("/ws/console", console_ws)
    return app


async def status(request: web.Request) -> web.Response:
    config: AgentConfig = request.app["config"]
    return web.json_response(
        {
            "name": config.pc_name,
            "status": "online",
            "port": config.port,
            "tls": config.tls_enabled,
            "devices": [
                {
                    "name": device.name,
                    "port": device.port,
                    "baudrate": device.baudrate,
                    "profile": device.profile,
                }
                for device in config.devices
            ],
            "baudrates": config.baudrates,
        }
    )


async def ports(request: web.Request) -> web.Response:
    return web.json_response(SerialManager.list_ports())


async def connect(request: web.Request) -> web.Response:
    try:
        payload = await request.json()
        settings = settings_from_payload(payload, request.app["config"])
        await asyncio.to_thread(SerialManager.validate, settings)
    except Exception as exc:
        LOGGER.exception("Serial validation failed")
        return web.json_response({"ok": False, "error": str(exc)}, status=400)

    scheme = "wss" if request.app["config"].tls_enabled else "ws"
    host = request.host
    query = f"port={settings.port}&baudrate={settings.baudrate}"
    return web.json_response({"ok": True, "websocket_url": f"{scheme}://{host}/ws/console?{query}"})


async def commands(request: web.Request) -> web.Response:
    manager: CommandManager = request.app["commands"]
    profile = request.query.get("profile", "default")
    return web.json_response({"profile": profile, "commands": manager.list_commands(profile)})


async def console_ws(request: web.Request) -> web.WebSocketResponse:
    ws = web.WebSocketResponse(heartbeat=20)
    await ws.prepare(request)

    try:
        settings = settings_from_payload(request.query, request.app["config"])
    except Exception as exc:
        await ws.send_json({"type": "error", "message": str(exc)})
        await ws.close()
        return ws

    profile = request.query.get("profile", "default")
    manager: CommandManager = request.app["commands"]

    try:
        async with SerialSession(settings) as session:
            await ws.send_json(
                {
                    "type": "connected",
                    "port": settings.port,
                    "baudrate": settings.baudrate,
                }
            )
            reader = asyncio.create_task(serial_to_websocket(session, ws))
            writer = asyncio.create_task(websocket_to_serial(ws, session, manager, profile))
            done, pending = await asyncio.wait({reader, writer}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            for task in done:
                task.result()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        LOGGER.exception("Console session failed")
        if not ws.closed:
            await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        if not ws.closed:
            await ws.close()

    return ws


async def serial_to_websocket(session: SerialSession, ws: web.WebSocketResponse) -> None:
    while not ws.closed:
        text = await session.read_text()
        if text:
            await ws.send_json({"type": "serial", "data": text})


async def websocket_to_serial(
    ws: web.WebSocketResponse,
    session: SerialSession,
    manager: CommandManager,
    profile: str,
) -> None:
    async for message in ws:
        if message.type == WSMsgType.TEXT:
            await handle_ws_text(message.data, session, manager, profile)
        elif message.type == WSMsgType.BINARY:
            await session.write_bytes(message.data)
        elif message.type in {WSMsgType.CLOSE, WSMsgType.CLOSING, WSMsgType.CLOSED, WSMsgType.ERROR}:
            break


async def handle_ws_text(
    text: str,
    session: SerialSession,
    manager: CommandManager,
    profile: str,
) -> None:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        await session.write_text(text)
        return

    message_type = payload.get("type")
    if message_type == "command":
        await session.write_text(str(payload.get("data", "")))
    elif message_type == "quick_command":
        command_name = str(payload.get("name", ""))
        command = manager.resolve(command_name, profile)
        if command is None:
            raise ValueError(f"Unknown quick command: {command_name}")
        await session.write_text(command)
    elif message_type == "bytes_base64":
        await session.write_base64(str(payload.get("data", "")))
    else:
        raise ValueError(f"Unsupported WebSocket message type: {message_type}")


def settings_from_payload(payload: Any, config: AgentConfig) -> SerialSettings:
    port = str(payload.get("port", "")).strip()
    if not port:
        device_name = str(payload.get("device", "")).strip()
        match = next((device for device in config.devices if device.name == device_name), None)
        if match is None:
            raise ValueError("Missing serial port")
        port = match.port
        baudrate = match.baudrate
    else:
        baudrate = int(payload.get("baudrate", config.default_baudrate))

    return SerialSettings(
        port=port,
        baudrate=baudrate,
        bytesize=int(payload.get("bytesize", 8)),
        parity=str(payload.get("parity", "N")).upper(),
        stopbits=float(payload.get("stopbits", 1)),
    )


def ssl_context(config: AgentConfig) -> ssl.SSLContext | None:
    if not config.tls_enabled:
        return None
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(config.certfile, config.keyfile)
    return context


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local serial console agent.")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).with_name("config.json")),
        help="Path to agent config JSON.",
    )
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    config = load_config(args.config)
    protocol = "wss" if config.tls_enabled else "ws"
    LOGGER.info("Starting %s on %s:%s (%s)", config.pc_name, config.host, config.port, protocol)
    web.run_app(create_app(config), host=config.host, port=config.port, ssl_context=ssl_context(config))


if __name__ == "__main__":
    main()

