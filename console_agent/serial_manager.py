from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from typing import Any

import serial
from serial.tools import list_ports


@dataclass(frozen=True)
class SerialSettings:
    port: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.1
    write_timeout: float = 1


class SerialManager:
    @staticmethod
    def list_ports() -> list[dict[str, Any]]:
        ports = []
        for port in list_ports.comports():
            ports.append(
                {
                    "device": port.device,
                    "name": port.name,
                    "description": port.description,
                    "hwid": port.hwid,
                    "vid": port.vid,
                    "pid": port.pid,
                    "serial_number": port.serial_number,
                    "manufacturer": port.manufacturer,
                    "product": port.product,
                }
            )
        return ports

    @staticmethod
    def validate(settings: SerialSettings) -> None:
        with serial.Serial(
            port=settings.port,
            baudrate=settings.baudrate,
            bytesize=settings.bytesize,
            parity=settings.parity,
            stopbits=settings.stopbits,
            timeout=settings.timeout,
            write_timeout=settings.write_timeout,
        ):
            return


class SerialSession:
    def __init__(self, settings: SerialSettings) -> None:
        self.settings = settings
        self._serial: serial.Serial | None = None
        self._write_lock = asyncio.Lock()

    async def __aenter__(self) -> "SerialSession":
        self._serial = await asyncio.to_thread(
            serial.Serial,
            port=self.settings.port,
            baudrate=self.settings.baudrate,
            bytesize=self.settings.bytesize,
            parity=self.settings.parity,
            stopbits=self.settings.stopbits,
            timeout=self.settings.timeout,
            write_timeout=self.settings.write_timeout,
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._serial and self._serial.is_open:
            await asyncio.to_thread(self._serial.close)

    async def read_text(self, size: int = 4096) -> str:
        data = await self.read_bytes(size)
        return data.decode("utf-8", errors="replace")

    async def read_bytes(self, size: int = 4096) -> bytes:
        if self._serial is None:
            raise RuntimeError("Serial session is not open")
        return await asyncio.to_thread(self._serial.read, size)

    async def write_text(self, text: str) -> None:
        await self.write_bytes(text.encode("utf-8"))

    async def write_base64(self, data: str) -> None:
        await self.write_bytes(base64.b64decode(data))

    async def write_bytes(self, data: bytes) -> None:
        if self._serial is None:
            raise RuntimeError("Serial session is not open")
        async with self._write_lock:
            await asyncio.to_thread(self._serial.write, data)
            await asyncio.to_thread(self._serial.flush)

