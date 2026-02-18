from pydantic import BaseModel, Field


class LLMConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5-coder:7b"
    timeout: int = 30
    max_retries: int = 2


class MCPConfig(BaseModel):
    transport: str = "sse"
    host: str = "0.0.0.0"
    port: int = 8585


class SecurityConfig(BaseModel):
    max_command_timeout: int = 30
    max_output_bytes: int = 65536
    allowed_paths: list[str] = Field(
        default_factory=lambda: ["/var/log", "/etc", "/proc", "/sys", "/tmp"]
    )


class LoggingConfig(BaseModel):
    level: str = "INFO"
    audit_log_path: str = "/var/log/sentry/audit.jsonl"
    app_log_path: str = "/var/log/sentry/sentry.log"


class TelemetryConfig(BaseModel):
    enabled: bool = True
    endpoint: str = "http://localhost:4317"
    service_name: str = "sentry"
    service_version: str = "0.1.0"


class SentryConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
