# Sentry — Architecture & Project Documentation

## Overview

Sentry is a read-only Linux system monitoring agent that exposes eight diagnostic tools over the **Model Context Protocol (MCP)**. An MCP client (such as an AI assistant) calls a tool — e.g. `check_resources` or `search_logs` — and Sentry runs the corresponding shell commands, validates them against a strict allowlist, executes them in a sanitized subprocess, then passes the raw output through a local LLM (Ollama) to produce a human-readable summary.

Every command execution is audit-logged as structured JSONL. The full request lifecycle emits OpenTelemetry traces and metrics to an external collector.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12 |
| MCP framework | `mcp` 1.26.0 (`FastMCP`) |
| HTTP client | `httpx` 0.28 (async, auto-instrumented by OTel) |
| Config | Pydantic v2 + YAML |
| LLM backend | Ollama (`qwen2.5-coder:7b`, `http://localhost:11434`) |
| Telemetry | OpenTelemetry SDK → OTLP gRPC → OTel Collector → ClickHouse → Grafana |
| Build system | Bazel bzlmod (`rules_python` 1.7.0) |
| Tests | pytest 9.x |

---

## Project Structure

```
sentry/
├── MODULE.bazel                  # Bazel bzlmod config
├── BUILD.bazel                   # Root exports (requirements, config)
├── .bazelrc                      # build --enable_bzlmod
├── requirements.txt              # Direct dependencies
├── requirements_lock.txt         # Pinned (pip-compile generated)
├── config.yaml                   # Default configuration
├── docker-compose.yml            # Ollama with GPU support
│
├── sentry/
│   ├── main.py                   # Entrypoint (py_binary)
│   ├── __init__.py
│   ├── BUILD.bazel               # sentry_lib + sentry binary
│   │
│   ├── config/                   # Configuration system
│   │   ├── schema.py             # Pydantic models (SentryConfig)
│   │   ├── loader.py             # YAML → SentryConfig
│   │   └── BUILD.bazel
│   │
│   ├── allowlist/                # Security boundary
│   │   ├── rules.py              # ALLOWLIST_RULES (28 commands)
│   │   ├── validator.py          # AllowlistValidator
│   │   └── BUILD.bazel
│   │
│   ├── audit/                    # Audit logging
│   │   ├── logger.py             # JSONL event writer
│   │   └── BUILD.bazel
│   │
│   ├── executor/                 # Command execution
│   │   ├── shell.py              # ShellExecutor + ExecutionResult
│   │   └── BUILD.bazel
│   │
│   ├── formatter/                # LLM summarization
│   │   ├── response_formatter.py # ResponseFormatter (Ollama POST)
│   │   └── BUILD.bazel
│   │
│   ├── planner/                  # LLM tool selection (standalone use)
│   │   ├── command_planner.py    # CommandPlanner
│   │   └── BUILD.bazel
│   │
│   ├── mcp/                      # MCP server + tool registration
│   │   ├── server.py             # create_mcp_server(), _run_tool()
│   │   └── BUILD.bazel
│   │
│   ├── tools/                    # 8 MCP tool definitions
│   │   ├── base.py               # BaseTool ABC
│   │   ├── system_health.py
│   │   ├── resources.py
│   │   ├── network.py
│   │   ├── processes.py
│   │   ├── logs.py
│   │   ├── services.py
│   │   ├── files.py
│   │   ├── diagnostics.py
│   │   ├── __init__.py           # ALL_TOOLS list
│   │   └── BUILD.bazel
│   │
│   └── telemetry/                # OpenTelemetry setup
│       ├── setup.py              # setup_telemetry(), get_tracer(), get_meter()
│       ├── __init__.py
│       └── BUILD.bazel
│
├── tests/
│   ├── test_config.py
│   ├── test_allowlist.py
│   ├── test_executor.py
│   ├── test_tools.py
│   ├── BUILD.bazel
│   └── integration/
│       ├── test_pipeline.py      # End-to-end (requires Ollama)
│       └── BUILD.bazel
│
└── scripts/
    ├── build.sh
    ├── test.sh
    └── install.sh                # systemd service installer
```

---

## Request Pipeline

```
MCP Client (AI assistant)
        │
        │  SSE (:8585) or stdio
        ▼
  FastMCP server                    [sentry/mcp/server.py]
        │
        │  _run_tool(tool_name, **params)
        │  ┌─ SPAN: mcp.tool_call ─────────────────────────────────┐
        ▼  │                                                        │
  tool.build_commands(**params)     [sentry/tools/*.py]             │
        │                                                           │
        │  list[str] — raw command strings                         │
        ▼                                                           │
  FOR EACH command:                                                 │
    ShellExecutor.execute(cmd)      [sentry/executor/shell.py]     │
        │  ┌─ SPAN: executor.execute ──────────────────────┐       │
        │  │                                                │       │
        │  │  SPAN: executor.validate                       │       │
        │  │    AllowlistValidator.validate(cmd)            │       │
        │  │      ├─ DENY → PermissionError                │       │
        │  │      └─ ALLOW → continue                      │       │
        │  │                                                │       │
        │  │  SPAN: executor.subprocess                     │       │
        │  │    subprocess.run(env={}, cwd="/tmp")          │       │
        │  │      ├─ TimeoutExpired → ExecutionResult       │       │
        │  │      └─ OK → truncate → ExecutionResult        │       │
        │  └────────────────────────────────────────────────┘       │
        │                                                           │
        │  raw_output (joined)                                      │
        ▼                                                           │
  ResponseFormatter.format()        [sentry/formatter/...]          │
        │  ┌─ SPAN: formatter.llm_call ─────────────────┐          │
        │  │  POST /api/chat → Ollama                    │          │
        │  │  (httpx auto-instrumented by OTel)          │          │
        │  │  fallback: return raw output on failure     │          │
        │  └─────────────────────────────────────────────┘          │
        │                                                           │
        │  human-readable summary                                   │
        └───────────────────────────────────────────────────────────┘
        ▼
  MCP response → client
```

---

## The 8 MCP Tools

| Tool | MCP Name | Commands |
|------|----------|----------|
| SystemHealthTool | `check_system_health` | `uptime`, `uname -a`, `dmesg --level=warn,err -T` |
| ResourcesTool | `check_resources` | `top -bn1 -o %CPU`, `free -h`, `df -h`, `iostat -x 1 1` |
| NetworkTool | `check_network` | `ss -tulnp`, `ss -anp`, `ip addr`, `ip route`, optionally `dig <target>` |
| ProcessesTool | `list_processes` | `ps aux --sort=-{sort_by}`, optionally `pgrep -a {filter}` |
| LogsTool | `search_logs` | `grep` on file or `journalctl` with pattern/unit/since |
| ServicesTool | `check_service_status` | `systemctl status {name}`, `journalctl -u {name} -n 50` |
| FilesTool | `inspect_file` | `stat`, `file`, `head`/`tail`, optionally `md5sum`/`sha256sum` |
| DiagnosticsTool | `run_diagnostic` | Predefined routines: disk, memory, cpu, network, general |

**Design principle:** Tools are pure command builders (`build_commands() → list[str]`). They never execute commands. The allowlist is always consulted before execution.

---

## Security Model

### Allowlist (primary security boundary)

28 allowed commands with per-command validation:

1. **Shell metacharacter rejection**: `| ; & $ ( ) { } ! > < \` are blocked in raw input
2. **Null bytes and newlines**: rejected outright
3. **Per-command rules**: max args, required flags, denied flags, arg pattern matching
4. **Semantic checks**: `top` requires `-b`, `systemctl` only allows `status`, `ping` requires `-c`, `tail`/`journalctl -f` blocked, `find -exec/-delete` blocked
5. **Path traversal**: `..` and `~` rejected in all arguments

### Subprocess hardening

- `env={}` — completely empty environment
- `cwd="/tmp"` — restricted working directory
- No `shell=True` — no shell interpretation
- Timeout enforced (default 30s)
- Output truncated at 64 KB

### Telemetry data safety

- Raw command strings and user queries are **never** written to span attributes
- Only the command binary name (`argv[0]`) and a SHA-256 hash of the full command are recorded
- Query length (not content) is recorded for planner spans

---

## Configuration

All configuration is in `config.yaml`, validated by Pydantic schemas in `sentry/config/schema.py`:

```yaml
llm:
  base_url: "http://localhost:11434"   # Ollama endpoint
  model: "qwen2.5-coder:7b"
  timeout: 30
  max_retries: 2

mcp:
  transport: "sse"                     # "sse" or "stdio"
  host: "0.0.0.0"
  port: 8585

security:
  max_command_timeout: 30              # seconds
  max_output_bytes: 65536              # 64 KB

logging:
  level: "INFO"
  audit_log_path: "/var/log/sentry/audit.jsonl"
  app_log_path: "/var/log/sentry/sentry.log"

telemetry:
  enabled: true
  endpoint: "http://localhost:4317"    # OTel Collector gRPC
  service_name: "sentry"
  service_version: "0.1.0"
```

Missing config file or empty YAML both produce valid defaults.

---

## Telemetry & Observability

### Spans (trace hierarchy)

```
mcp.tool_call                          tool.name, tool.param_count, tool.command_count
  ├── executor.execute                 command.name, command.allowed, command.output_bytes
  │     ├── executor.validate
  │     └── executor.subprocess        command.return_code, command.timed_out
  └── formatter.llm_call               llm.model, llm.input_bytes, llm.output_bytes
        └── (httpx auto-instrumented)
```

`planner.llm_call` emitted when `CommandPlanner` is used independently.

All error paths set `span.set_status(StatusCode.ERROR)` and `span.record_exception()`.

### Metrics

| Metric | Type | Labels | Purpose |
|--------|------|--------|---------|
| `sentry.tool_call.duration_ms` | Histogram | `tool.name` | End-to-end MCP call latency |
| `sentry.tool_call.count` | Counter | `tool.name` | Call volume by tool |
| `sentry.executor.duration_ms` | Histogram | — | Shell command execution time |
| `sentry.executor.command_count` | Counter | — | Total commands executed |
| `sentry.formatter.llm_duration_ms` | Histogram | `llm.model` | Formatter LLM call time |
| `sentry.planner.llm_duration_ms` | Histogram | `llm.model` | Planner LLM call time |

### Observability stack (dev-kit)

```
Sentry ──OTLP gRPC──▶ OTel Collector (:4317) ──TCP──▶ ClickHouse (:8123)
                                                              │
                                                        Grafana (:3000)
                                                   "Sentry MCP Observability"
```

Infrastructure lives at `/home/joeyang/Vibe/dev-kit` (Docker Compose). The Grafana dashboard (`sentry.json`) provides:

- **Tool Call Duration** — p50/p95/p99 over time
- **Time Breakdown: Sentry vs LLM** — stacked bar chart (executor vs formatter vs planner)
- **Tool Call Count** — by tool name
- **Formatter LLM Duration** — p50/p95/max
- **Executor Duration** — p50/p95/max
- **Recent Traces** — table with timestamp, span name, duration, tool, model

---

## Architecture Decisions

### 1. Tools as pure command builders

Tools implement only `build_commands() → list[str]`. They never execute commands. This enforces that the allowlist validator is always in the execution path and makes tools trivially unit-testable.

### 2. Single chokepoint for validation

`AllowlistValidator.validate()` is the only path to command execution. The validator checks both raw strings (metacharacters) and tokenized forms (per-argument patterns). Defense-in-depth: even if a tool generates an unexpected command, it cannot bypass the allowlist.

### 3. Empty subprocess environment

`subprocess.run(env={})` prevents environment variable injection. Commands resolve via the kernel's default binary search paths, not `$PATH`.

### 4. Deferred import for telemetry initialization

`setup_telemetry()` is called in `main.py` **before** importing `sentry.mcp.server` (and transitively all instrumented modules). This ensures module-level `meter.create_histogram()` calls bind to the real SDK `MeterProvider`, not the NoOp provider.

### 5. Lazy SDK imports in telemetry setup

Heavy OTel SDK classes (`TracerProvider`, `OTLPSpanExporter`, `HTTPXClientInstrumentor`, etc.) are imported inside `setup_telemetry()`, not at module top level. This avoids import-time dependency issues — e.g. `opentelemetry-instrumentation-httpx` requires `httpx` at import, but not all consumers of the telemetry module need httpx (as the test_executor failure demonstrated).

### 6. Insecure OTLP transport for localhost only

The OTLP exporter uses `insecure=True` when the endpoint starts with `http://`. For `https://` endpoints, TLS is enabled automatically. This is documented in the code and appropriate for the local collector sidecar pattern.

### 7. Graceful provider shutdown

`atexit` handlers flush the `TracerProvider` and `MeterProvider` on process exit, ensuring the final batch of spans and the last metric collection interval are not silently lost.

### 8. No raw secrets in telemetry

Command strings and user queries are never written to span attributes. Only the command binary name, a SHA-256 hash of the full command, and query length are recorded. The Grafana dashboard queries only these sanitized attributes.

---

## Build & Test

```bash
# Build everything
bazel build //...

# Run all tests
bazel test //...

# Run only unit tests (skip integration)
bazel test //... --test_tag_filters=-integration

# Run sentry
bazel run //sentry:sentry -- --transport sse --config config.yaml

# Regenerate pip lockfile
pip-compile --output-file=requirements_lock.txt requirements.txt
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `mcp>=1.26.0` | FastMCP server framework |
| `httpx>=0.28.0` | Async HTTP for Ollama calls |
| `pydantic>=2.0.0` | Config schema validation |
| `pyyaml>=6.0.1` | YAML config parsing |
| `pytest>=8.0.0` | Test framework |
| `opentelemetry-api>=1.20.0` | Tracer/meter interfaces |
| `opentelemetry-sdk>=1.20.0` | TracerProvider, MeterProvider, BatchSpanProcessor |
| `opentelemetry-exporter-otlp-proto-grpc>=1.20.0` | OTLP gRPC export |
| `opentelemetry-instrumentation-httpx>=0.41b0` | Auto-instrument httpx |
