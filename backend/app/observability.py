"""OpenTelemetry -> Arize Phoenix (ADR-0004). pydantic-ai emits a span per agent run and model
request; run_role wraps each in a span tagged with case, role, prompt version and job."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic_ai import Agent, Embedder
from pydantic_ai.models.instrumented import InstrumentationSettings

from app.config import Settings

PROJECT = "lawyer-ai"
tracer = trace.get_tracer("lawyer-ai")


def setup_tracing(settings: Settings) -> TracerProvider | None:
    """Call once per process. TRACING=false disables export (tests)."""
    if not settings.tracing:
        return None
    provider = TracerProvider(
        # Phoenix groups traces into projects by this resource attribute.
        resource=Resource.create({"service.name": PROJECT, "openinference.project.name": PROJECT})
    )
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.phoenix_endpoint))
    )
    trace.set_tracer_provider(provider)
    # include_content=False keeps tokens/latency but drops confidential case text from traces.
    instrumentation = InstrumentationSettings(include_content=settings.trace_content)
    Agent.instrument_all(instrumentation)
    Embedder.instrument_all(instrumentation)
    return provider
