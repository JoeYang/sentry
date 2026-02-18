"""End-to-end integration test requiring a running Ollama instance.

Run with: bazel test //tests/integration:test_pipeline --test_tag_filters=requires-ollama
"""

import asyncio

import httpx
import pytest

from sentry.config.loader import load_config
from sentry.planner.command_planner import CommandPlanner
from sentry.formatter.response_formatter import ResponseFormatter
from sentry.allowlist.validator import AllowlistValidator
from sentry.audit.logger import AuditLogger
from sentry.executor.shell import ShellExecutor
from sentry.tools import ALL_TOOLS


def ollama_available() -> bool:
    """Check if Ollama is reachable."""
    try:
        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not ollama_available(), reason="Ollama not available"),
]


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def executor(config, tmp_path):
    validator = AllowlistValidator()
    audit_log = tmp_path / "audit.jsonl"
    audit_logger = AuditLogger(str(audit_log))
    return ShellExecutor(validator, audit_logger, config.security)


@pytest.fixture
def tool_map():
    return {tool_cls().name: tool_cls() for tool_cls in ALL_TOOLS}


class TestEndToEndPipeline:
    """Test the full query -> plan -> execute -> format pipeline."""

    def test_system_health_query(self, config, executor, tool_map):
        async def _run():
            planner = CommandPlanner(config.llm)
            formatter = ResponseFormatter(config.llm)
            try:
                plan = await planner.plan("How is the system doing?")
                assert "tool" in plan

                tool_name = plan["tool"]
                tool = tool_map.get(tool_name)
                assert tool is not None, f"Unknown tool: {tool_name}"

                params = plan.get("parameters", {})
                commands = tool.build_commands(**params)

                outputs = []
                for cmd in commands:
                    try:
                        result = executor.execute(cmd)
                        outputs.append(result.stdout)
                    except PermissionError:
                        outputs.append(f"[DENIED] {cmd}")
                    except Exception as e:
                        outputs.append(f"[ERROR] {cmd}: {e}")

                raw_output = "\n".join(outputs)

                summary = await formatter.format(tool_name, raw_output)
                assert isinstance(summary, str)
                assert len(summary) > 0
            finally:
                await planner.close()
                await formatter.close()

        asyncio.run(_run())

    def test_planner_returns_valid_tool(self, config):
        async def _run():
            planner = CommandPlanner(config.llm)
            try:
                valid_tools = {tool_cls().name for tool_cls in ALL_TOOLS}
                plan = await planner.plan("Show me disk usage")
                assert plan["tool"] in valid_tools
            finally:
                await planner.close()

        asyncio.run(_run())
