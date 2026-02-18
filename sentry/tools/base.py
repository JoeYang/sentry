"""Abstract base class for Sentry monitoring tools."""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """Base class for all Sentry monitoring tools.

    Tools generate shell command strings that are validated by the allowlist
    before execution. Tools never execute commands directly.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """MCP tool name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable tool description."""

    @abstractmethod
    def build_commands(self, **params: str) -> list[str]:
        """Build shell command strings for this tool.

        Returns a list of command strings. Each command must pass allowlist
        validation independently.
        """
