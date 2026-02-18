import hashlib
import shlex
import subprocess
import time
from dataclasses import dataclass

from opentelemetry.trace import StatusCode

from sentry.allowlist.validator import AllowlistValidator
from sentry.audit.logger import AuditLogger
from sentry.config.schema import SecurityConfig
from sentry.telemetry.setup import get_meter, get_tracer

tracer = get_tracer(__name__)
meter = get_meter(__name__)

command_duration = meter.create_histogram(
    name="sentry.executor.duration_ms",
    description="Duration of shell command execution in milliseconds",
    unit="ms",
)
command_count = meter.create_counter(
    name="sentry.executor.command_count",
    description="Number of shell commands executed",
    unit="1",
)


@dataclass
class ExecutionResult:
    command: str
    return_code: int
    stdout: str
    stderr: str
    duration: float
    timed_out: bool


class ShellExecutor:
    def __init__(
        self,
        validator: AllowlistValidator,
        audit_logger: AuditLogger,
        config: SecurityConfig,
    ) -> None:
        self.validator = validator
        self.audit_logger = audit_logger
        self.config = config

    def execute(self, command_string: str) -> ExecutionResult:
        """Execute a validated command."""
        exec_start = time.monotonic()
        with tracer.start_as_current_span("executor.execute") as span:
            # Record only the binary name and a hash — never the full command,
            # which may contain secrets or PII in its arguments.
            argv0 = shlex.split(command_string)[0] if command_string else ""
            span.set_attribute("command.name", argv0)
            span.set_attribute("command.args_sha256", hashlib.sha256(command_string.encode()).hexdigest())
            command_count.add(1)

            # 1. Validate command.
            with tracer.start_as_current_span("executor.validate"):
                result = self.validator.validate(command_string)

            span.set_attribute("command.allowed", result.allowed)

            # 2. If denied, audit log and raise PermissionError.
            if not result.allowed:
                self.audit_logger.log_validation(
                    command=command_string, allowed=False, reason=result.reason
                )
                err = PermissionError(f"Command denied: {result.reason}")
                span.set_status(StatusCode.ERROR, "command denied")
                span.record_exception(err)
                raise err

            self.audit_logger.log_validation(
                command=command_string, allowed=True, reason=result.reason
            )

            # 3. Execute with subprocess.
            args_list = shlex.split(command_string)
            start_time = time.monotonic()

            with tracer.start_as_current_span("executor.subprocess") as sub_span:
                try:
                    proc = subprocess.run(
                        args_list,
                        capture_output=True,
                        text=True,
                        env={},
                        cwd="/tmp",
                        timeout=self.config.max_command_timeout,
                    )
                except subprocess.TimeoutExpired as e:
                    duration = time.monotonic() - start_time
                    sub_span.set_status(StatusCode.ERROR, "command timed out")
                    sub_span.record_exception(e)
                    sub_span.set_attribute("command.timed_out", True)
                    self.audit_logger.log_timeout(
                        command=command_string,
                        timeout=self.config.max_command_timeout,
                    )
                    return ExecutionResult(
                        command=command_string,
                        return_code=-1,
                        stdout="",
                        stderr=f"Command timed out after {self.config.max_command_timeout}s",
                        duration=duration,
                        timed_out=True,
                    )

                duration = time.monotonic() - start_time
                sub_span.set_attribute("command.return_code", proc.returncode)

            # 4. Truncate output at max_output_bytes.
            stdout = proc.stdout
            stderr = proc.stderr
            if len(stdout.encode()) > self.config.max_output_bytes:
                stdout = stdout[: self.config.max_output_bytes] + "\n... [output truncated]"
            if len(stderr.encode()) > self.config.max_output_bytes:
                stderr = stderr[: self.config.max_output_bytes] + "\n... [output truncated]"

            output_bytes = len(stdout.encode()) + len(stderr.encode())
            span.set_attribute("command.output_bytes", output_bytes)

            # 5. Audit log result.
            self.audit_logger.log_execution(
                command=command_string,
                return_code=proc.returncode,
                duration=duration,
                output_bytes=output_bytes,
            )

            # 6. Return ExecutionResult.
            exec_duration_ms = (time.monotonic() - exec_start) * 1000
            command_duration.record(exec_duration_ms)
            return ExecutionResult(
                command=command_string,
                return_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration=duration,
                timed_out=False,
            )
