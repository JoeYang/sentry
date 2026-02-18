"""Service status monitoring tool."""

from sentry.tools.base import BaseTool


class ServicesTool(BaseTool):
    """Check systemd service status and recent logs."""

    @property
    def name(self) -> str:
        return "check_service_status"

    @property
    def description(self) -> str:
        return "Check the status of a systemd service and its recent journal entries."

    def build_commands(self, service_name: str, **params: str) -> list[str]:
        return [
            f"systemctl status {service_name}",
            f"journalctl -u {service_name} -n 50 --no-pager",
        ]
