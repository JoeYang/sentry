# Sentry

A read-only Linux monitoring agent that exposes diagnostic tools over the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/). An LLM connects via MCP, invokes tools to inspect the host, and receives summarized results — no SSH required.

## How It Works

```
LLM client  ──MCP──▶  Sentry server
                         │
                   ┌─────┼─────┐
                   ▼     ▼     ▼
               Planner  Tool  Allowlist
                   │     │     │
                   ▼     ▼     ▼
               Build   Validate  Execute
               cmds    against   subprocess
                       allowlist
                         │
                         ▼
                    LLM formatter
                    (summarize output)
                         │
                         ▼
                    MCP response
```

1. An MCP request arrives specifying a tool and parameters.
2. The **planner** selects the tool; the tool **builds shell commands** from parameters.
3. Each command is validated against the **allowlist** (regex-based rules).
4. Approved commands run in a sandboxed **subprocess** (empty env, no `shell=True`, timeout, output cap).
5. Raw output passes through an **LLM formatter** that produces a human-readable summary.
6. The summary is returned as an MCP response.

## Available Tools

| Tool | Description |
|------|-------------|
| `check_system_health` | Uptime, kernel version, and recent kernel warnings/errors |
| `check_resources` | CPU, memory, disk space, and I/O statistics |
| `check_network` | Listening ports, active connections, interfaces, and routes |
| `list_processes` | Running processes, filtered by name or sorted by resource usage |
| `search_logs` | Search logs by pattern, time range, or service unit |
| `check_service_status` | Systemd service status and recent journal entries |
| `inspect_file` | File metadata, type, head/tail content, and checksums |
| `run_diagnostic` | Predefined diagnostic routines (quick-health, network-check, etc.) |

## Quick Start

### Development (requires Bazel)

```bash
bazel build //...
bazel test //...
bazel run //sentry:sentry
```

### Production

```bash
# Build the distributable tarball
bash scripts/package.sh

# Copy dist/sentry-0.1.0.tar.gz to the target host, then:
tar xzf sentry-0.1.0.tar.gz
cd sentry-0.1.0
sudo bash scripts/install.sh

# Manage the service
sudo systemctl start sentry
sudo systemctl enable sentry
```

## Configuration

The default config lives at `/etc/sentry/config.yaml` after installation. Key sections:

- **llm** — LLM endpoint, model, timeout (`base_url`, `model`, `timeout`)
- **mcp** — Transport and bind address (`transport`, `host`, `port`)
- **security** — Command timeout, output size cap, allowed filesystem paths
- **logging** — Log level, audit log path, application log path
- **telemetry** — OpenTelemetry exporter endpoint and service metadata

## Observability

Sentry emits OpenTelemetry traces and metrics to a configurable OTLP endpoint. A typical pipeline:

```
Sentry  ──OTLP/gRPC──▶  OTel Collector  ──▶  ClickHouse  ──▶  Grafana
```

## Security

- **Allowlist**: Every command is validated against regex-based rules before execution. Commands that don't match are rejected.
- **Empty environment**: Subprocesses run with a clean environment — no inherited secrets.
- **No `shell=True`**: Commands execute directly via `subprocess`, preventing shell injection.
- **Output truncation**: Output is capped at a configurable byte limit to prevent memory exhaustion.
- **Systemd hardening**: The service runs as an unprivileged user with `NoNewPrivileges`, `ProtectSystem=strict`, `ReadOnlyPaths=/`, and `MemoryDenyWriteExecute`.
