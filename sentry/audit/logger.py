import json
import os
from datetime import datetime, timezone


class AuditLogger:
    def __init__(self, log_path: str) -> None:
        log_dir = os.path.dirname(log_path)
        if log_dir:
            try:
                os.makedirs(log_dir, exist_ok=True)
            except PermissionError:
                # Fall back to a local directory when we can't write to the
                # configured path (e.g. /var/log/sentry without root).
                fallback_dir = os.path.join(os.getcwd(), ".sentry_logs")
                os.makedirs(fallback_dir, exist_ok=True)
                log_path = os.path.join(fallback_dir, os.path.basename(log_path))
        self._log_path = log_path
        self._file = open(log_path, "a")

    def _write_entry(self, entry: dict) -> None:
        entry["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._file.write(json.dumps(entry) + "\n")
        self._file.flush()

    def log_validation(self, command: str, allowed: bool, reason: str) -> None:
        self._write_entry(
            {
                "event_type": "validation",
                "command": command,
                "allowed": allowed,
                "reason": reason,
            }
        )

    def log_execution(
        self, command: str, return_code: int, duration: float, output_bytes: int
    ) -> None:
        self._write_entry(
            {
                "event_type": "execution",
                "command": command,
                "return_code": return_code,
                "duration": duration,
                "output_bytes": output_bytes,
            }
        )

    def log_timeout(self, command: str, timeout: float) -> None:
        self._write_entry(
            {
                "event_type": "timeout",
                "command": command,
                "timeout": timeout,
            }
        )

    def close(self) -> None:
        self._file.close()
