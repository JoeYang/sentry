"""Log searching tool."""

from sentry.tools.base import BaseTool


class LogsTool(BaseTool):
    """Search system and application logs."""

    @property
    def name(self) -> str:
        return "search_logs"

    @property
    def description(self) -> str:
        return "Search logs by pattern, time range, or service unit."

    def build_commands(
        self,
        pattern: str = "",
        file: str = "",
        context_lines: str = "3",
        unit: str = "",
        since: str = "",
        **params: str,
    ) -> list[str]:
        commands = []
        if file and pattern:
            commands.append(f"grep -n -C{context_lines} {pattern} {file}")
        if unit:
            cmd = f"journalctl -u {unit} -n 100 --no-pager"
            if since:
                cmd = f"journalctl -u {unit} --since {since} --no-pager"
            if pattern:
                cmd += f" --grep {pattern}"
            commands.append(cmd)
        elif not file:
            cmd = "journalctl -n 100 --no-pager"
            if since:
                cmd = f"journalctl --since {since} --no-pager"
            if pattern:
                cmd += f" --grep {pattern}"
            commands.append(cmd)
        return commands
