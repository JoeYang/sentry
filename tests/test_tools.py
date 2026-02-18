"""Tests for tool command generation.

Verifies that every tool's build_commands() output produces commands
that pass allowlist validation.
"""

import pytest

from sentry.allowlist.validator import AllowlistValidator
from sentry.tools import ALL_TOOLS
from sentry.tools.diagnostics import DIAGNOSTIC_ROUTINES
from sentry.tools.files import FilesTool
from sentry.tools.logs import LogsTool
from sentry.tools.network import NetworkTool
from sentry.tools.processes import ProcessesTool
from sentry.tools.services import ServicesTool
from sentry.tools.system_health import SystemHealthTool
from sentry.tools.resources import ResourcesTool
from sentry.tools.diagnostics import DiagnosticsTool


@pytest.fixture
def validator():
    return AllowlistValidator()


class TestSystemHealthTool:
    def test_default_commands_pass_validation(self, validator):
        tool = SystemHealthTool()
        for cmd in tool.build_commands():
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_has_name_and_description(self):
        tool = SystemHealthTool()
        assert tool.name == "check_system_health"
        assert len(tool.description) > 0


class TestResourcesTool:
    def test_default_commands_pass_validation(self, validator):
        tool = ResourcesTool()
        for cmd in tool.build_commands():
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestNetworkTool:
    def test_default_commands_pass_validation(self, validator):
        tool = NetworkTool()
        for cmd in tool.build_commands():
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_with_target_passes_validation(self, validator):
        tool = NetworkTool()
        for cmd in tool.build_commands(target="google.com"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestProcessesTool:
    def test_default_commands_pass_validation(self, validator):
        tool = ProcessesTool()
        for cmd in tool.build_commands():
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_with_filter_passes_validation(self, validator):
        tool = ProcessesTool()
        for cmd in tool.build_commands(filter_name="nginx"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_sort_by_memory(self, validator):
        tool = ProcessesTool()
        for cmd in tool.build_commands(sort_by="%mem"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestLogsTool:
    def test_file_search_passes_validation(self, validator):
        tool = LogsTool()
        for cmd in tool.build_commands(pattern="error", file="/var/log/syslog"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_journal_search_passes_validation(self, validator):
        tool = LogsTool()
        for cmd in tool.build_commands(unit="nginx"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_journal_with_since_passes_validation(self, validator):
        tool = LogsTool()
        for cmd in tool.build_commands(unit="nginx", since="1h ago"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestServicesTool:
    def test_commands_pass_validation(self, validator):
        tool = ServicesTool()
        for cmd in tool.build_commands(service_name="nginx"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestFilesTool:
    def test_default_commands_pass_validation(self, validator):
        tool = FilesTool()
        for cmd in tool.build_commands(path="/etc/hosts"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_tail_mode_passes_validation(self, validator):
        tool = FilesTool()
        for cmd in tool.build_commands(path="/var/log/syslog", show_tail="true", lines="50"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"

    def test_checksum_passes_validation(self, validator):
        tool = FilesTool()
        for cmd in tool.build_commands(path="/etc/hosts", checksum="sha256"):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} — {result.reason}"


class TestDiagnosticsTool:
    @pytest.mark.parametrize("routine", list(DIAGNOSTIC_ROUTINES.keys()))
    def test_routine_commands_pass_validation(self, validator, routine):
        tool = DiagnosticsTool()
        for cmd in tool.build_commands(routine=routine):
            result = validator.validate(cmd)
            assert result.allowed, f"Command rejected: {cmd} (routine={routine}) — {result.reason}"

    def test_unknown_routine_falls_back_to_general(self):
        tool = DiagnosticsTool()
        commands = tool.build_commands(routine="nonexistent")
        assert commands == DIAGNOSTIC_ROUTINES["general"]


class TestAllToolsHaveNameAndDescription:
    @pytest.mark.parametrize("tool_cls", ALL_TOOLS)
    def test_tool_metadata(self, tool_cls):
        tool = tool_cls()
        assert isinstance(tool.name, str) and len(tool.name) > 0
        assert isinstance(tool.description, str) and len(tool.description) > 0
