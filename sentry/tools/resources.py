"""System resource monitoring tool."""

from sentry.tools.base import BaseTool


class ResourcesTool(BaseTool):
    """Check CPU, memory, disk, and I/O usage."""

    @property
    def name(self) -> str:
        return "check_resources"

    @property
    def description(self) -> str:
        return "Check system resource usage: CPU, memory, disk space, and I/O statistics."

    def build_commands(self, **params: str) -> list[str]:
        return [
            "top -bn1 -o %CPU",
            "free -h",
            "df -h",
            "iostat -x 1 1",
        ]
