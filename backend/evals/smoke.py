"""One real model call per profile through run_role, traced to Phoenix. Checks the wiring
(routing, tracing, usage rows), not quality.

Run from backend/:  uv run python -m evals.smoke --profile cloud local
"""

import argparse
import asyncio
import tempfile
from pathlib import Path

from pydantic import BaseModel

from app.config import Settings, settings
from app.contracts.cases import CaseCreate
from app.llm.prompts import load_prompt
from app.llm.registry import Profile
from app.llm.runner import run_role
from app.observability import setup_tracing
from app.store.case_store import CaseStore
from app.store.registry import Registry

STATEMENT = (
    "Statement of Ramesh Kumar u/s 180 BNSS. On 12-03-2026 I was standing near my tea stall at "
    "about 8:30 pm when a man in a red jacket snatched the gold chain of an elderly lady. "
    "The street light was on and I saw his face clearly."
)


class Claim(BaseModel):
    speaker: str
    statement: str
    quote: str


class Claims(BaseModel):
    claims: list[Claim]


async def smoke(profile: Profile, tmp: Path) -> None:
    registry = Registry(tmp / profile)
    case = registry.create(CaseCreate(title=f"smoke-{profile}", client="smoke"), "nomic-embed-text")
    store = CaseStore(registry.case_dir(case.id))
    run_settings = Settings(**{**settings.model_dump(), "model_profile": profile})
    try:
        out = await run_role(
            "extractor", case=case, store=store, settings=run_settings,
            prompt=load_prompt("smoke"), user_prompt=f"<document>\n{STATEMENT}\n</document>",
            output_type=Claims, job_id=f"smoke-{profile}",
        )  # fmt: skip
        row = store.db.execute("SELECT * FROM llm_calls").fetchone()
        print(f"[{profile}] {row['model']}: {len(out.claims)} claims, {row['latency_ms']} ms, "
              f"{row['input_tokens']} in / {row['output_tokens']} out, cost {row['cost_usd']}, "
              f"trace {row['trace_id']}")  # fmt: skip
    finally:
        store.close()
        registry.close()


async def main(profiles: list[Profile]) -> None:
    provider = setup_tracing(settings)
    with tempfile.TemporaryDirectory() as tmp:
        for profile in profiles:
            await smoke(profile, Path(tmp))
    if provider:
        provider.shutdown()  # flush spans to Phoenix before exit


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", nargs="+", choices=["local", "hybrid", "cloud"], required=True)
    asyncio.run(main(parser.parse_args().profile))
