"""LLM-based command planner using Ollama."""

import json
import logging
import time

import httpx
from opentelemetry.trace import StatusCode

from sentry.config.schema import LLMConfig
from sentry.telemetry.setup import get_meter, get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)

planner_llm_duration = meter.create_histogram(
    name="sentry.planner.llm_duration_ms",
    description="Duration of planner LLM calls in milliseconds",
    unit="ms",
)

SYSTEM_PROMPT = """\
You are a Linux system monitoring assistant. Given a user query, select the most \
appropriate monitoring tool and parameters.

Available tools:
- check_system_health: Check uptime, kernel version, recent kernel warnings/errors.
- check_resources: Check CPU, memory, disk, and I/O usage.
- check_network: Check network interfaces, connections, routing. Parameters: target (optional hostname for DNS lookup).
- list_processes: List running processes. Parameters: sort_by (default: %cpu), filter_name (optional process name filter).
- search_logs: Search logs. Parameters: pattern (search term), file (log file path), context_lines (default: 3), unit (systemd unit), since (time range).
- check_service_status: Check systemd service. Parameters: service_name (required).
- inspect_file: Inspect a file. Parameters: path (required), lines (default: 20), show_tail (true/false), checksum (md5/sha256).
- run_diagnostic: Run diagnostic routine. Parameters: routine (disk/memory/cpu/network/general).

Respond with ONLY a JSON object:
{"tool": "<tool_name>", "parameters": {<key>: <value>, ...}}

Do not include any explanation, just the JSON.\
"""


class CommandPlanner:
    """Selects monitoring tools via Ollama LLM."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def plan(self, query: str) -> dict:
        """Ask the LLM which tool to invoke for the given query.

        Returns a dict with 'tool' and 'parameters' keys.
        """
        llm_start = time.monotonic()
        with tracer.start_as_current_span("planner.llm_call") as span:
            span.set_attribute("llm.model", self.config.model)
            # Only record query length — the raw query may contain secrets or PII.
            span.set_attribute("planner.query_length", len(query))

            try:
                for attempt in range(self.config.max_retries + 1):
                    span.set_attribute("planner.attempt", attempt + 1)
                    try:
                        response = await self.client.post(
                            "/api/chat",
                            json={
                                "model": self.config.model,
                                "messages": [
                                    {"role": "system", "content": SYSTEM_PROMPT},
                                    {"role": "user", "content": query},
                                ],
                                "stream": False,
                                "format": "json",
                            },
                        )
                        response.raise_for_status()
                        data = response.json()
                        content = data["message"]["content"]
                        result = json.loads(content)
                        if "tool" not in result:
                            raise ValueError("LLM response missing 'tool' key")
                        result.setdefault("parameters", {})
                        return result
                    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
                        logger.warning("Planner attempt %d failed: %s", attempt + 1, e)
                        if attempt == self.config.max_retries:
                            span.record_exception(e)
                            span.set_status(StatusCode.ERROR, "planning failed after retries")
                            raise RuntimeError(f"Command planning failed after {self.config.max_retries + 1} attempts: {e}") from e
            finally:
                duration_ms = (time.monotonic() - llm_start) * 1000
                planner_llm_duration.record(duration_ms, {"llm.model": self.config.model})

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
