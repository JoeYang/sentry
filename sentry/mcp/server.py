"""FastMCP server with tool registration."""

import logging
import time

from mcp.server.fastmcp import FastMCP

from opentelemetry.trace import StatusCode

from sentry.allowlist.validator import AllowlistValidator
from sentry.audit.logger import AuditLogger
from sentry.config.schema import SentryConfig
from sentry.executor.shell import ShellExecutor
from sentry.formatter.response_formatter import ResponseFormatter
from sentry.telemetry.setup import get_meter, get_tracer
from sentry.tools import ALL_TOOLS

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)

tool_call_duration = meter.create_histogram(
    name="sentry.tool_call.duration_ms",
    description="Total duration of an MCP tool call in milliseconds",
    unit="ms",
)
tool_call_count = meter.create_counter(
    name="sentry.tool_call.count",
    description="Number of MCP tool calls",
    unit="1",
)


def create_mcp_server(config: SentryConfig) -> FastMCP:
    """Create and configure the MCP server with all tools registered."""
    mcp = FastMCP("sentry", host=config.mcp.host, port=config.mcp.port)

    validator = AllowlistValidator()
    audit_logger = AuditLogger(config.logging.audit_log_path)
    executor = ShellExecutor(validator, audit_logger, config.security)
    formatter = ResponseFormatter(config.llm)

    # Instantiate all tools
    tool_instances = {}
    for tool_cls in ALL_TOOLS:
        instance = tool_cls()
        tool_instances[instance.name] = instance

    async def _run_tool(tool_name: str, **params: str) -> str:
        """Common execution pipeline for all tools."""
        start = time.monotonic()
        with tracer.start_as_current_span("mcp.tool_call") as span:
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("tool.param_count", len(params))
            tool_call_count.add(1, {"tool.name": tool_name})

            tool = tool_instances.get(tool_name)
            if tool is None:
                span.set_status(StatusCode.ERROR, f"unknown tool: {tool_name}")
                return f"Unknown tool: {tool_name}"

            commands = tool.build_commands(**params)
            span.set_attribute("tool.command_count", len(commands))
            outputs = []

            for cmd in commands:
                try:
                    result = executor.execute(cmd)
                    output = result.stdout
                    if result.stderr:
                        output += f"\n[stderr] {result.stderr}"
                    if result.timed_out:
                        output += "\n[command timed out]"
                    outputs.append(f"$ {cmd}\n{output}")
                except PermissionError as e:
                    outputs.append(f"$ {cmd}\n[DENIED] {e}")

            raw_output = "\n\n".join(outputs)
            span.set_attribute("tool.total_output_bytes", len(raw_output))

            try:
                summary = await formatter.format(tool_name, raw_output)
                return summary
            except Exception as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, "LLM formatting failed")
                logger.warning("LLM formatting failed, returning raw output: %s", e)
                return raw_output
            finally:
                duration_ms = (time.monotonic() - start) * 1000
                tool_call_duration.record(duration_ms, {"tool.name": tool_name})

    # Register each tool as an MCP tool
    @mcp.tool()
    async def check_system_health() -> str:
        """Check overall system health: uptime, kernel version, and recent kernel warnings/errors."""
        return await _run_tool("check_system_health")

    @mcp.tool()
    async def check_resources() -> str:
        """Check system resource usage: CPU, memory, disk space, and I/O statistics."""
        return await _run_tool("check_resources")

    @mcp.tool()
    async def check_network(target: str = "") -> str:
        """Check network status: listening ports, active connections, interfaces, and routes."""
        return await _run_tool("check_network", target=target)

    @mcp.tool()
    async def list_processes(sort_by: str = "%cpu", filter_name: str = "") -> str:
        """List running processes, optionally filtered by name or sorted by resource usage."""
        return await _run_tool("list_processes", sort_by=sort_by, filter_name=filter_name)

    @mcp.tool()
    async def search_logs(
        pattern: str = "",
        file: str = "",
        context_lines: str = "3",
        unit: str = "",
        since: str = "",
    ) -> str:
        """Search system and application logs by pattern, time range, or service unit."""
        return await _run_tool(
            "search_logs",
            pattern=pattern,
            file=file,
            context_lines=context_lines,
            unit=unit,
            since=since,
        )

    @mcp.tool()
    async def check_service_status(service_name: str) -> str:
        """Check the status of a systemd service and its recent journal entries."""
        return await _run_tool("check_service_status", service_name=service_name)

    @mcp.tool()
    async def inspect_file(
        path: str,
        lines: str = "20",
        show_tail: str = "false",
        checksum: str = "",
    ) -> str:
        """Inspect a file: view metadata, type, head/tail content, and checksums."""
        return await _run_tool(
            "inspect_file",
            path=path,
            lines=lines,
            show_tail=show_tail,
            checksum=checksum,
        )

    @mcp.tool()
    async def run_diagnostic(routine: str = "general") -> str:
        """Run a predefined diagnostic routine (disk, memory, cpu, network, general)."""
        return await _run_tool("run_diagnostic", routine=routine)

    return mcp
