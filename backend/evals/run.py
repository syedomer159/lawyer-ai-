"""Eval runner. Scores the pipeline against samples/<case>/{manifest.json, answer_key.yaml}.

Suites:
  ingest   - OCR accuracy and retrieval recall (local embedder; free).
  analysis - full analysis workflow with real models, scored against the answer keys.
  trial    - scripted mock-trial round per case: objections and witness grounding.

Run from backend/:
  uv run python -m evals.run --suite ingest
  uv run python -m evals.run --suite analysis --profile cloud
Writes evals/reports/<date>-<suite>[-<profile>].{md,json}; traces go to Phoenix.
"""

import argparse
import asyncio

from app.config import settings
from app.observability import setup_tracing
from evals import analysis_suite, ingest_suite, trial_suite


async def main(suite: str, profile: str | None) -> None:
    run_settings = settings.model_copy(update={"model_profile": profile}) if profile else settings
    provider = setup_tracing(run_settings)
    try:
        suite_module = {"analysis": analysis_suite, "trial": trial_suite}.get(suite, ingest_suite)
        print("report:", await suite_module.run(run_settings))
    finally:
        if provider:
            provider.shutdown()  # flush spans to Phoenix


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["ingest", "analysis", "trial"], required=True)
    parser.add_argument("--profile", choices=["local", "hybrid", "cloud"])
    args = parser.parse_args()
    asyncio.run(main(args.suite, args.profile))
