"""Network monitoring tool."""

from sentry.tools.base import BaseTool


class NetworkTool(BaseTool):
    """Check network interfaces, connections, and routing."""

    @property
    def name(self) -> str:
        return "check_network"

    @property
    def description(self) -> str:
        return "Check network status: listening ports, active connections, interfaces, and routes."

    def build_commands(self, target: str = "", **params: str) -> list[str]:
        commands = [
            "ss -tulnp",
            "ss -anp",
            "ip addr",
            "ip route",
        ]
        if target:
            commands.append(f"dig {target}")
        else:
            commands.append("dig")
        return commands
