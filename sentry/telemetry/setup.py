"""OpenTelemetry provider initialization."""

import atexit
import logging

from opentelemetry import metrics, trace

from sentry.config.schema import TelemetryConfig

logger = logging.getLogger(__name__)

_initialized = False


def setup_telemetry(config: TelemetryConfig) -> None:
    """Initialize OpenTelemetry tracing and metrics.

    When config.enabled is False, this is a no-op and the default
    NoOp providers remain active.
    """
    global _initialized
    if _initialized:
        return

    if not config.enabled:
        logger.info("Telemetry disabled, skipping OTel setup")
        _initialized = True
        return

    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    resource = Resource.create(
        {
            "service.name": config.service_name,
            "service.version": config.service_version,
        }
    )

    # insecure=True disables TLS; acceptable only for loopback/sidecar collectors.
    # For remote endpoints, configure TLS via OTEL_EXPORTER_OTLP_CERTIFICATE env var.
    _insecure = config.endpoint.startswith("http://")

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=config.endpoint, insecure=_insecure)
        )
    )
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=config.endpoint, insecure=_insecure),
        export_interval_millis=5000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Flush pending spans and metrics on process exit.
    atexit.register(tracer_provider.shutdown)
    atexit.register(meter_provider.shutdown)

    # Auto-instrument httpx (covers planner + formatter HTTP calls to Ollama).
    HTTPXClientInstrumentor().instrument()

    _initialized = True
    logger.info(
        "Telemetry initialized: endpoint=%s service=%s",
        config.endpoint,
        config.service_name,
    )


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer from the global provider."""
    return trace.get_tracer(name)


def get_meter(name: str) -> metrics.Meter:
    """Return a meter from the global provider."""
    return metrics.get_meter(name)
