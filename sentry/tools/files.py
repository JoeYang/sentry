"""File inspection tool."""

from sentry.tools.base import BaseTool


class FilesTool(BaseTool):
    """Inspect file metadata and contents (read-only)."""

    @property
    def name(self) -> str:
        return "inspect_file"

    @property
    def description(self) -> str:
        return "Inspect a file: view metadata, type, head/tail content, and checksums."

    def build_commands(
        self,
        path: str,
        lines: str = "20",
        show_tail: str = "false",
        checksum: str = "",
        **params: str,
    ) -> list[str]:
        commands = [
            f"stat {path}",
            f"file {path}",
        ]
        if show_tail.lower() == "true":
            commands.append(f"tail -n {lines} {path}")
        else:
            commands.append(f"head -n {lines} {path}")
        if checksum == "md5":
            commands.append(f"md5sum {path}")
        elif checksum == "sha256":
            commands.append(f"sha256sum {path}")
        return commands
