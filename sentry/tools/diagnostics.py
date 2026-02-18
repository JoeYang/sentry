"""Diagnostic routine tool."""

from sentry.tools.base import BaseTool


# Predefined diagnostic routines with hardcoded command sequences.
DIAGNOSTIC_ROUTINES: dict[str, list[str]] = {
    "disk": [
        "df -h",
        "lsblk -f",
        "iostat -x 1 1",
    ],
    "memory": [
        "free -h",
        "vmstat 1 3",
        "ps aux --sort=-%mem",
    ],
    "cpu": [
        "mpstat",
        "vmstat 1 3",
        "ps aux --sort=-%cpu",
    ],
    "network": [
        "ss -tulnp",
        "ip addr",
        "ip route",
    ],
    "general": [
        "uptime",
        "uname -a",
        "free -h",
        "df -h",
        "ps aux --sort=-%cpu",
    ],
}


class DiagnosticsTool(BaseTool):
    """Run predefined diagnostic routines."""

    @property
    def name(self) -> str:
        return "run_diagnostic"

    @property
    def description(self) -> str:
        routines = ", ".join(DIAGNOSTIC_ROUTINES.keys())
        return f"Run a predefined diagnostic routine. Available routines: {routines}"

    def build_commands(self, routine: str = "general", **params: str) -> list[str]:
        if routine not in DIAGNOSTIC_ROUTINES:
            return DIAGNOSTIC_ROUTINES["general"]
        return DIAGNOSTIC_ROUTINES[routine]
