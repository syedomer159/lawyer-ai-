"""Spike a/b/e: typed output from a model string, embeddings via Ollama, trace to Phoenix.

Run from backend/:  uv run python ../scripts/spikes/spike_llm.py [model]
Default model: ollama:qwen3.5:4b. Needs OLLAMA_BASE_URL=http://localhost:11434/v1.
"""

import asyncio
import os
import sys
import time

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel
from pydantic_ai import Agent, Embedder, NativeOutput
from pydantic_ai.embeddings.openai import OpenAIEmbeddingModel
from pydantic_ai.models.instrumented import InstrumentationSettings
from pydantic_ai.providers.ollama import OllamaProvider

os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434/v1")

STATEMENT = (
    "Statement of Ramesh Kumar u/s 180 BNSS, recorded 14-03-2026. "
    "I was standing near the tea stall on MG Road at about 8:30 pm when a man in a red "
    "jacket snatched the gold chain of the complainant and ran towards the bus stand. "
    "The street light was on and I saw his face clearly."
)


class Claim(BaseModel):
    speaker: str
    aspect: str
    statement: str
    time: str | None
    place: str | None
    quote: str


class Claims(BaseModel):
    claims: list[Claim]


def setup_tracing() -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": "lawyer-ai-spike"}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces"))
    )
    trace.set_tracer_provider(provider)
    return provider


async def main(model: str) -> None:
    provider = setup_tracing()
    Agent.instrument_all(InstrumentationSettings(include_content=True))

    is_local = model.startswith("ollama:")
    output = NativeOutput(Claims) if is_local else Claims
    agent = Agent(
        model,
        output_type=output,
        # qwen3.5 is a thinking model; on CPU thinking makes a short extraction take 10+ minutes.
        model_settings={"openai_reasoning_effort": "none"} if is_local else None,
        instructions=(
            "Extract every factual claim from the witness statement. "
            "`quote` must be copied verbatim from the statement."
        ),
    )
    t0 = time.perf_counter()
    result = await agent.run(f"<document>\n{STATEMENT}\n</document>")
    print(f"[{model}] {time.perf_counter() - t0:.1f}s usage={result.usage}")
    for c in result.output.claims:
        print(" -", c.model_dump())

    embedder = Embedder(OpenAIEmbeddingModel("nomic-embed-text", provider=OllamaProvider()))
    t0 = time.perf_counter()
    emb = await embedder.embed_documents([STATEMENT, "red jacket"])
    print(f"embeddings: {len(emb.embeddings)} x {len(emb.embeddings[0])} in "
          f"{time.perf_counter() - t0:.1f}s")

    provider.force_flush()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "ollama:qwen3.5:4b"))
