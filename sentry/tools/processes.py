"""Process listing tool."""

from sentry.tools.base import BaseTool


class ProcessesTool(BaseTool):
    """List and filter running processes."""

    @property
    def name(self) -> str:
        return "list_processes"

    @property
    def description(self) -> str:
        return "List running processes, optionally filtered by name or sorted by resource usage."

    def build_commands(self, sort_by: str = "%cpu", filter_name: str = "", **params: str) -> list[str]:
        commands = [f"ps aux --sort=-{sort_by}"]
        if filter_name:
            commands.append(f"pgrep -a {filter_name}")
        return commands
