from __future__ import annotations

import argparse
import asyncio
import json
import logging
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from aiohttp import WSMsgType, web

from .command_manager import CommandManager
from .config import AgentConfig, load_config_or_default
from .serial_manager import SerialManager, SerialSession, SerialSettings


LOGGER = logging.getLogger("console-agent")


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Serial Console Agent</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #111318;
      --panel: #1b1f29;
      --panel-2: #151923;
      --line: #343b4d;
      --text: #eef2f8;
      --muted: #9ba7ba;
      --accent: #5cc8ff;
      --danger: #ff6b6b;
      --ok: #74d99f;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      background: var(--bg);
      color: var(--text);
      font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 20px 0;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: 0;
    }
    .status {
      color: var(--muted);
      min-width: 160px;
      text-align: right;
    }
    .status.connected { color: var(--ok); }
    .status.error { color: var(--danger); }
    .layout {
      display: grid;
      grid-template-columns: 320px 1fr;
      gap: 16px;
      align-items: stretch;
    }
    aside, section {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    aside { padding: 16px; }
    label {
      display: block;
      margin: 14px 0 6px;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }
    select, input {
      width: 100%;
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--panel-2);
      color: var(--text);
      padding: 0 10px;
      font: inherit;
    }
    button {
      height: 38px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #252b38;
      color: var(--text);
      padding: 0 12px;
      font: inherit;
      cursor: pointer;
    }
    button.primary {
      border-color: #2a84aa;
      background: #116487;
    }
    button.danger {
      border-color: #8c3434;
      background: #6f2525;
    }
    button:disabled, select:disabled, input:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .actions {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 16px;
    }
    .quick {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      margin-top: 8px;
    }
    .terminal-wrap {
      display: grid;
      grid-template-rows: 1fr auto;
      min-height: calc(100vh - 110px);
    }
    #terminal {
      min-height: 420px;
      max-height: calc(100vh - 210px);
      overflow: auto;
      margin: 0;
      padding: 14px;
      background: #07090d;
      border-radius: 8px 8px 0 0;
      color: #d8f7dd;
      font: 13px/1.45 Consolas, "Cascadia Mono", "Courier New", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }
    .command-row {
      display: grid;
      grid-template-columns: 1fr 92px;
      gap: 8px;
      padding: 12px;
      border-top: 1px solid var(--line);
    }
    .hint {
      color: var(--muted);
      font-size: 12px;
      margin-top: 10px;
    }
    @media (max-width: 820px) {
      .layout { grid-template-columns: 1fr; }
      .terminal-wrap { min-height: 560px; }
      #terminal { max-height: 520px; }
      header { align-items: flex-start; flex-direction: column; }
      .status { text-align: left; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Serial Console Agent</h1>
      <div id="status" class="status">Loading...</div>
    </header>
    <div class="layout">
      <aside>
        <button id="refreshPorts" type="button">Refresh ports</button>

        <label for="port">Serial port</label>
        <select id="port"></select>

        <label for="baudrate">Baudrate</label>
        <select id="baudrate"></select>

        <label for="profile">Command profile</label>
        <select id="profile">
          <option value="default">default</option>
        </select>

        <div class="actions">
          <button id="connect" class="primary" type="button">Connect</button>
          <button id="disconnect" class="danger" type="button" disabled>Disconnect</button>
        </div>

        <label>Quick command</label>
        <div id="quick" class="quick"></div>
        <div class="hint">After connecting, port settings are locked until Disconnect.</div>
      </aside>

      <section class="terminal-wrap">
        <pre id="terminal"></pre>
        <div class="command-row">
          <input id="command" type="text" placeholder="Type command and press Enter" disabled>
          <button id="send" type="button" disabled>Send</button>
        </div>
      </section>
    </div>
  </main>

  <script>
    const state = { ws: null, commands: {}, connected: false };
    const $ = (id) => document.getElementById(id);
    const portSelect = $("port");
    const baudrateSelect = $("baudrate");
    const profileSelect = $("profile");
    const terminal = $("terminal");
    const statusEl = $("status");
    const commandInput = $("command");

    function setStatus(text, cls = "") {
      statusEl.textContent = text;
      statusEl.className = `status ${cls}`.trim();
    }

    function append(text) {
      terminal.textContent += text;
      terminal.scrollTop = terminal.scrollHeight;
    }

    function setLocked(locked) {
      state.connected = locked;
      portSelect.disabled = locked;
      baudrateSelect.disabled = locked;
      profileSelect.disabled = locked;
      $("refreshPorts").disabled = locked;
      $("connect").disabled = locked;
      $("disconnect").disabled = !locked;
      commandInput.disabled = !locked;
      $("send").disabled = !locked;
      for (const button of document.querySelectorAll("[data-command]")) {
        button.disabled = !locked;
      }
    }

    async function loadStatus() {
      const response = await fetch("/api/status");
      const data = await response.json();
      baudrateSelect.innerHTML = "";
      for (const rate of data.baudrates) {
        const option = new Option(rate, rate);
        if (rate === data.default_baudrate) option.selected = true;
        baudrateSelect.add(option);
      }
      setStatus(`${data.name} online`);
    }

    async function loadPorts() {
      const response = await fetch("/api/ports");
      const ports = await response.json();
      portSelect.innerHTML = "";

      if (!ports.length) {
        portSelect.add(new Option("No serial ports found", ""));
        setStatus("No serial ports found", "error");
        return;
      }

      for (const port of ports) {
        const label = port.description ? `${port.device} - ${port.description}` : port.device;
        portSelect.add(new Option(label, port.device));
      }
      setStatus(`${ports.length} port(s) found`);
    }

    async function loadCommands() {
      const profile = profileSelect.value || "default";
      const response = await fetch(`/api/commands?profile=${encodeURIComponent(profile)}`);
      const data = await response.json();
      state.commands = data.commands || {};
      const quick = $("quick");
      quick.innerHTML = "";

      for (const name of Object.keys(state.commands)) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = name;
        button.dataset.command = name;
        button.disabled = !state.connected;
        button.addEventListener("click", () => sendQuick(name));
        quick.appendChild(button);
      }
    }

    function wsUrl() {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      const params = new URLSearchParams({
        port: portSelect.value,
        baudrate: baudrateSelect.value,
        profile: profileSelect.value || "default",
      });
      return `${scheme}://${location.host}/ws/console?${params}`;
    }

    function connect() {
      if (!portSelect.value) {
        setStatus("Select a serial port first", "error");
        return;
      }

      const ws = new WebSocket(wsUrl());
      state.ws = ws;
      setStatus("Connecting...");

      ws.onopen = () => {
        setLocked(true);
        append(`\\n[connected ${portSelect.value} @ ${baudrateSelect.value}]\\n`);
      };

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "serial") append(message.data);
        if (message.type === "connected") setStatus(`${message.port} connected`, "connected");
        if (message.type === "error") {
          append(`\\n[error] ${message.message}\\n`);
          setStatus(message.message, "error");
        }
      };

      ws.onclose = () => {
        setLocked(false);
        setStatus("Disconnected");
        append("\\n[disconnected]\\n");
        state.ws = null;
      };

      ws.onerror = () => {
        setStatus("WebSocket error", "error");
      };
    }

    function disconnect() {
      if (state.ws) state.ws.close();
    }

    function sendCommand() {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
      const value = commandInput.value;
      if (!value) return;
      state.ws.send(JSON.stringify({ type: "command", data: `${value}\\n` }));
      commandInput.value = "";
    }

    function sendQuick(name) {
      if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
      state.ws.send(JSON.stringify({ type: "quick_command", name }));
    }

    $("refreshPorts").addEventListener("click", loadPorts);
    $("connect").addEventListener("click", connect);
    $("disconnect").addEventListener("click", disconnect);
    $("send").addEventListener("click", sendCommand);
    commandInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") sendCommand();
    });
    profileSelect.addEventListener("change", loadCommands);

    Promise.all([loadStatus(), loadPorts(), loadCommands()]).catch((error) => {
      setStatus(error.message, "error");
    });
  </script>
</body>
</html>
"""


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
    app["active_ports"] = set()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_get("/api/ports", ports)
    app.router.add_post("/api/connect", connect)
    app.router.add_get("/api/commands", commands)
    app.router.add_get("/ws/console", console_ws)
    return app


async def index(request: web.Request) -> web.Response:
    return web.Response(text=INDEX_HTML, content_type="text/html")


async def status(request: web.Request) -> web.Response:
    config: AgentConfig = request.app["config"]
    return web.json_response(
        {
            "name": config.pc_name,
            "status": "online",
            "port": config.port,
            "tls": config.tls_enabled,
            "default_baudrate": config.default_baudrate,
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
    query = urlencode({"port": settings.port, "baudrate": settings.baudrate})
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
    active_ports: set[str] = request.app["active_ports"]

    if settings.port in active_ports:
        await ws.send_json({"type": "error", "message": f"{settings.port} is already connected"})
        await ws.close()
        return ws

    try:
        active_ports.add(settings.port)
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
        active_ports.discard(settings.port)
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
        default=None,
        help="Optional path to agent config JSON.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind when no config file is used.")
    parser.add_argument("--port", default=9001, type=int, help="Port to bind when no config file is used.")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args()
    config = load_config_or_default(args.config, host=args.host, port=args.port)
    protocol = "wss" if config.tls_enabled else "ws"
    LOGGER.info("Starting %s on %s:%s (%s)", config.pc_name, config.host, config.port, protocol)
    web.run_app(create_app(config), host=config.host, port=config.port, ssl_context=ssl_context(config))


if __name__ == "__main__":
    main()
