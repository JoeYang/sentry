import os
import re
import shlex
from dataclasses import dataclass, field

from sentry.allowlist.rules import ALLOWLIST_RULES, AllowlistRule


@dataclass
class ValidationResult:
    allowed: bool
    command: str
    args: list[str] = field(default_factory=list)
    reason: str = ""


# Shell metacharacters that indicate injection attempts.
_SHELL_METACHARACTERS = set("|;&$(){}!><`")


class AllowlistValidator:
    def __init__(self) -> None:
        self.rules: dict[str, AllowlistRule] = ALLOWLIST_RULES

    def validate(self, command_string: str) -> ValidationResult:
        """Validate a command string against the allowlist."""
        # Handle empty / whitespace-only input.
        if not command_string or not command_string.strip():
            return ValidationResult(
                allowed=False, command="", args=[], reason="Empty command"
            )

        # Check the ORIGINAL command string for shell metacharacters.
        for ch in command_string:
            if ch in _SHELL_METACHARACTERS:
                return ValidationResult(
                    allowed=False,
                    command=command_string,
                    args=[],
                    reason=f"Shell metacharacter '{ch}' detected in command string",
                )

        # Check for null bytes.
        if "\x00" in command_string:
            return ValidationResult(
                allowed=False,
                command=command_string,
                args=[],
                reason="Null byte detected in command string",
            )

        # Check for embedded newlines (command injection via newline).
        if "\n" in command_string or "\r" in command_string:
            return ValidationResult(
                allowed=False,
                command=command_string,
                args=[],
                reason="Newline character detected in command string",
            )

        # Safe tokenisation.
        try:
            tokens = shlex.split(command_string)
        except ValueError as exc:
            return ValidationResult(
                allowed=False,
                command=command_string,
                args=[],
                reason=f"Failed to parse command: {exc}",
            )

        if not tokens:
            return ValidationResult(
                allowed=False, command="", args=[], reason="Empty command after parsing"
            )

        # Extract base command (strip path prefix).
        base_command = os.path.basename(tokens[0])
        args = tokens[1:]

        # Check command exists in allowlist.
        if base_command not in self.rules:
            return ValidationResult(
                allowed=False,
                command=base_command,
                args=args,
                reason=f"Command '{base_command}' is not in the allowlist",
            )

        rule = self.rules[base_command]

        # Check arg count.
        if len(args) > rule.max_args:
            return ValidationResult(
                allowed=False,
                command=base_command,
                args=args,
                reason=f"Too many arguments ({len(args)} > {rule.max_args})",
            )

        # Validate top requires -b flag for batch mode.
        if base_command == "top":
            has_batch = any(
                arg == "-b" or arg.startswith("-bn") for arg in args
            )
            if not has_batch:
                return ValidationResult(
                    allowed=False,
                    command=base_command,
                    args=args,
                    reason="top must be run in batch mode (-b flag required)",
                )

        # Validate systemctl requires 'status' as first arg.
        if base_command == "systemctl":
            if not args or args[0] != "status":
                return ValidationResult(
                    allowed=False,
                    command=base_command,
                    args=args,
                    reason="systemctl only allows the 'status' subcommand",
                )

        # Validate ping requires -c flag (no unlimited ping).
        if base_command == "ping":
            if "-c" not in args:
                return ValidationResult(
                    allowed=False,
                    command=base_command,
                    args=args,
                    reason="ping requires -c flag to limit packet count",
                )

        # Validate each arg.
        for arg in args:
            # Block path traversal.
            if ".." in arg or arg.startswith("~"):
                return ValidationResult(
                    allowed=False,
                    command=base_command,
                    args=args,
                    reason=f"Path traversal detected in argument: {arg}",
                )

            # Check individual args for shell metacharacters.
            for ch in arg:
                if ch in _SHELL_METACHARACTERS:
                    return ValidationResult(
                        allowed=False,
                        command=base_command,
                        args=args,
                        reason=f"Shell metacharacter '{ch}' detected in argument: {arg}",
                    )

            # Check against denied patterns.
            for denied_pattern in rule.denied_args:
                if re.match(denied_pattern, arg):
                    return ValidationResult(
                        allowed=False,
                        command=base_command,
                        args=args,
                        reason=f"Argument '{arg}' matches denied pattern '{denied_pattern}'",
                    )

            # Check that arg matches at least one allowed pattern.
            if rule.allowed_args:
                matched = any(
                    re.match(pattern, arg) for pattern in rule.allowed_args
                )
                if not matched:
                    return ValidationResult(
                        allowed=False,
                        command=base_command,
                        args=args,
                        reason=f"Argument '{arg}' does not match any allowed pattern",
                    )

        return ValidationResult(
            allowed=True,
            command=base_command,
            args=args,
            reason="Command is allowed",
        )
