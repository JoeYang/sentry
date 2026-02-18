"""System health monitoring tool."""

from sentry.tools.base import BaseTool


class SystemHealthTool(BaseTool):
    """Check overall system health: uptime, kernel info, and recent warnings."""

    @property
    def name(self) -> str:
        return "check_system_health"

    @property
    def description(self) -> str:
        return "Check overall system health including uptime, kernel version, and recent kernel warnings/errors."

    def build_commands(self, **params: str) -> list[str]:
        return [
            "uptime",
            "uname -a",
            "dmesg --level=warn,err -T",
        ]
