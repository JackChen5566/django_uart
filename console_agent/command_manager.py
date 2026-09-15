from __future__ import annotations


class CommandManager:
    def __init__(self, profiles: dict[str, dict[str, str]]) -> None:
        self._profiles = profiles

    def list_profiles(self) -> list[str]:
        return sorted(self._profiles)

    def list_commands(self, profile: str = "default") -> dict[str, str]:
        commands = self._profiles.get(profile)
        if commands is None and profile != "default":
            commands = self._profiles.get("default")
        return dict(commands or {})

    def resolve(self, name: str, profile: str = "default") -> str | None:
        command = self.list_commands(profile).get(name)
        if command is None:
            return None
        return command if command.endswith("\n") else f"{command}\n"

