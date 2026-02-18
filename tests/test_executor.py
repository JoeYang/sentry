import subprocess
from unittest.mock import MagicMock, patch

import pytest

from sentry.allowlist.validator import AllowlistValidator
from sentry.audit.logger import AuditLogger
from sentry.config.schema import SecurityConfig
from sentry.executor.shell import ExecutionResult, ShellExecutor


@pytest.fixture
def mock_audit_logger():
    logger = MagicMock(spec=AuditLogger)
    return logger


@pytest.fixture
def validator():
    return AllowlistValidator()


@pytest.fixture
def config():
    return SecurityConfig(max_command_timeout=5, max_output_bytes=1024)


@pytest.fixture
def executor(validator, mock_audit_logger, config):
    return ShellExecutor(validator, mock_audit_logger, config)


class TestCommandDenial:
    def test_refuses_disallowed_command(self, executor):
        with pytest.raises(PermissionError, match="Command denied"):
            executor.execute("rm -rf /")

    def test_refuses_injection(self, executor):
        with pytest.raises(PermissionError):
            executor.execute("uptime; rm -rf /")

    def test_audit_logged_on_denial(self, executor, mock_audit_logger):
        with pytest.raises(PermissionError):
            executor.execute("rm /tmp/file")
        mock_audit_logger.log_validation.assert_called_once()
        call_kwargs = mock_audit_logger.log_validation.call_args
        assert call_kwargs[1]["allowed"] is False or call_kwargs[0][1] is False


class TestTimeoutEnforcement:
    @patch("sentry.executor.shell.subprocess.run")
    def test_timeout_returns_timed_out_result(
        self, mock_run, executor, mock_audit_logger
    ):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="uptime", timeout=5)
        result = executor.execute("uptime")
        assert result.timed_out is True
        assert result.return_code == -1
        mock_audit_logger.log_timeout.assert_called_once()

    @patch("sentry.executor.shell.subprocess.run")
    def test_timeout_value_from_config(self, mock_run, validator, mock_audit_logger):
        config = SecurityConfig(max_command_timeout=10)
        exec_ = ShellExecutor(validator, mock_audit_logger, config)
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )
        exec_.execute("uptime")
        mock_run.assert_called_once()
        assert mock_run.call_args[1]["timeout"] == 10


class TestOutputTruncation:
    @patch("sentry.executor.shell.subprocess.run")
    def test_output_truncated_at_max_bytes(self, mock_run, executor):
        big_output = "x" * 2048
        mock_run.return_value = MagicMock(
            returncode=0, stdout=big_output, stderr=""
        )
        result = executor.execute("uptime")
        assert len(result.stdout.encode()) <= 1024 + 50  # allow for truncation message


class TestSubprocessArgs:
    @patch("sentry.executor.shell.subprocess.run")
    def test_subprocess_called_with_empty_env(self, mock_run, executor):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        executor.execute("uptime")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["env"] == {}

    @patch("sentry.executor.shell.subprocess.run")
    def test_subprocess_called_with_tmp_cwd(self, mock_run, executor):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="", stderr=""
        )
        executor.execute("uptime")
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["cwd"] == "/tmp"


class TestAuditLogging:
    @patch("sentry.executor.shell.subprocess.run")
    def test_audit_logged_for_allowed_command(self, mock_run, executor, mock_audit_logger):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="up 5 days", stderr=""
        )
        executor.execute("uptime")
        # Should have log_validation (allowed) and log_execution
        mock_audit_logger.log_validation.assert_called_once()
        mock_audit_logger.log_execution.assert_called_once()

    def test_audit_logged_for_denied_command(self, executor, mock_audit_logger):
        with pytest.raises(PermissionError):
            executor.execute("rm /tmp/file")
        mock_audit_logger.log_validation.assert_called_once()
