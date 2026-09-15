from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_BAUDRATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]


@dataclass(frozen=True)
class DeviceConfig:
    name: str
    port: str
    baudrate: int = 115200
    profile: str = "default"


@dataclass(frozen=True)
class AgentConfig:
    pc_name: str
    host: str = "0.0.0.0"
    port: int = 9001
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    default_baudrate: int = 115200
    baudrates: list[int] = field(default_factory=lambda: DEFAULT_BAUDRATES.copy())
    devices: list[DeviceConfig] = field(default_factory=list)
    commands: dict[str, dict[str, str]] = field(default_factory=dict)
    certfile: str | None = None
    keyfile: str | None = None
    log_dir: str = "logs"

    @property
    def tls_enabled(self) -> bool:
        return bool(self.certfile and self.keyfile)


def load_config(path: str | os.PathLike[str]) -> AgentConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data: dict[str, Any] = json.load(handle)

    devices = [
        DeviceConfig(
            name=str(item["name"]),
            port=str(item["port"]),
            baudrate=int(item.get("baudrate", data.get("default_baudrate", 115200))),
            profile=str(item.get("profile", "default")),
        )
        for item in data.get("devices", [])
    ]

    return AgentConfig(
        pc_name=str(data.get("pc_name") or platform.node() or "console-agent"),
        host=str(data.get("host", "0.0.0.0")),
        port=int(data.get("port", 9001)),
        cors_origins=[str(origin) for origin in data.get("cors_origins", ["*"])],
        default_baudrate=int(data.get("default_baudrate", 115200)),
        baudrates=[int(rate) for rate in data.get("baudrates", DEFAULT_BAUDRATES)],
        devices=devices,
        commands={
            str(profile): {str(name): str(command) for name, command in commands.items()}
            for profile, commands in data.get("commands", {}).items()
        },
        certfile=data.get("certfile"),
        keyfile=data.get("keyfile"),
        log_dir=str(data.get("log_dir", "logs")),
    )

