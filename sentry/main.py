"""Sentry monitoring agent entrypoint."""

import argparse
import logging
import sys

from sentry.config.loader import load_config
from sentry.telemetry.setup import setup_telemetry


def main() -> None:
    parser = argparse.ArgumentParser(description="Sentry Linux Monitoring Agent")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    parser.add_argument(
        "--transport",
        choices=["sse", "stdio"],
        default=None,
        help="MCP transport type (overrides config)",
    )
    args = parser.parse_args()

    config = load_config(args.config)

    # Initialize telemetry BEFORE importing instrumented modules so that
    # module-level meters and tracers bind to the real SDK provider.
    setup_telemetry(config.telemetry)

    # Deferred import: must happen after setup_telemetry() so module-level
    # OTel instruments (histograms, counters) attach to the configured provider.
    from sentry.mcp.server import create_mcp_server

    logging.basicConfig(
        level=getattr(logging, config.logging.level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    transport = args.transport or config.mcp.transport
    logger.info("Starting Sentry MCP server (transport=%s)", transport)

    mcp = create_mcp_server(config)

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
