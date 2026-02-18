"""LLM-based response formatter using Ollama."""

import logging
import time

import httpx
from opentelemetry.trace import StatusCode

from sentry.config.schema import LLMConfig
from sentry.telemetry.setup import get_meter, get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)
meter = get_meter(__name__)

formatter_llm_duration = meter.create_histogram(
    name="sentry.formatter.llm_duration_ms",
    description="Duration of formatter LLM calls in milliseconds",
    unit="ms",
)

MAX_INPUT_BYTES = 8192

SUMMARIZE_PROMPT = """\
You are a Linux system monitoring assistant. Summarize the following command output \
in a clear, human-readable format. Highlight any warnings, errors, or anomalies. \
Be concise but include all important details.

Command: {command}

Output:
{output}\
"""


class ResponseFormatter:
    """Formats raw command output into human-readable summaries via Ollama."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.client = httpx.AsyncClient(
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def format(self, command: str, raw_output: str) -> str:
        """Summarize raw command output using the LLM.

        Truncates input to 8KB before sending to the LLM.
        """
        llm_start = time.monotonic()
        with tracer.start_as_current_span("formatter.llm_call") as span:
            span.set_attribute("llm.model", self.config.model)

            truncated = raw_output[:MAX_INPUT_BYTES]
            if len(raw_output) > MAX_INPUT_BYTES:
                truncated += "\n... [output truncated]"

            span.set_attribute("llm.input_bytes", len(truncated))
            prompt = SUMMARIZE_PROMPT.format(command=command, output=truncated)

            try:
                response = await self.client.post(
                    "/api/chat",
                    json={
                        "model": self.config.model,
                        "messages": [
                            {"role": "user", "content": prompt},
                        ],
                        "stream": False,
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["message"]["content"]
                span.set_attribute("llm.output_bytes", len(content))
                return content
            except (httpx.HTTPError, KeyError) as e:
                span.record_exception(e)
                span.set_status(StatusCode.ERROR, "LLM call failed")
                logger.warning("Formatting failed, returning raw output: %s", e)
                return f"[Raw output — LLM formatting unavailable]\n{truncated}"
            finally:
                duration_ms = (time.monotonic() - llm_start) * 1000
                formatter_llm_duration.record(duration_ms, {"llm.model": self.config.model})

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
