"""Gemini API key pool: rotate across keys, classify failures, remember quota resets.

Status per key: active, invalid (expired / revoked / not valid: never used again until the key
changes), or quota-exhausted per model until the reset time Google reports (RetryInfo), else the
next midnight Pacific for daily quotas. State lives in data/gemini_keys.json, keyed by a
fingerprint: the keys themselves are never written there or logged.

Note: Gemini quotas are per Google Cloud project, so keys from the same project share one quota.

CLI (from backend/):
  uv run python -m app.llm.keys --check              test every key, print the status table
  uv run python -m app.llm.keys --check --prune-env  ...and rewrite .env without invalid keys
"""

import asyncio
import hashlib
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import cache
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic_ai.exceptions import FallbackExceptionGroup, ModelHTTPError

KeyState = Literal["active", "invalid"]
MAX_WAIT_FOR_RESET = timedelta(seconds=60)  # a per-minute limit: wait rather than fail
_INVALID_MARKERS = (
    "API_KEY_INVALID",
    "API key expired",
    "API key not valid",
    "PERMISSION_DENIED",
    "has been suspended",
    "reported as leaked",
)


def fingerprint(key: str) -> str:
    return f"{hashlib.sha256(key.encode()).hexdigest()[:8]}..{key[-4:]}"


class NoGeminiKey(RuntimeError):
    """Every key is invalid or out of quota for this model."""


@dataclass
class KeyStatus:
    state: KeyState = "active"
    exhausted_until: dict[str, str] = field(default_factory=dict)  # model -> ISO time (UTC)
    last_error: str | None = None
    checked_at: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def classify(exc: ModelHTTPError) -> tuple[Literal["invalid", "quota"] | None, datetime | None]:
    """Is this failure about the key? Returns (kind, quota reset time)."""
    body = json.dumps(exc.body) if not isinstance(exc.body, str) else exc.body
    if exc.status_code == 429 and "RESOURCE_EXHAUSTED" in body:
        if delay := re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', body):
            return "quota", _now() + timedelta(seconds=float(delay.group(1)))
        if "PerDay" in body:  # daily free-tier quotas reset at midnight Pacific time
            pacific = _now().astimezone(ZoneInfo("America/Los_Angeles"))
            midnight = (pacific + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            return "quota", midnight.astimezone(UTC)
        return "quota", _now() + timedelta(seconds=60)
    if exc.status_code in (400, 401, 403) and any(m in body for m in _INVALID_MARKERS):
        return "invalid", None
    return None, None


class KeyPool:
    def __init__(self, keys: list[str], status_path: Path) -> None:
        self.keys = list(dict.fromkeys(k for k in keys if k))
        self.path = status_path
        self._lock = threading.Lock()
        self._next = 0
        raw: dict[str, Any] = json.loads(status_path.read_text()) if status_path.exists() else {}
        self.status = {fingerprint(k): KeyStatus(**raw.get(fingerprint(k), {})) for k in self.keys}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {fp: s.__dict__ for fp, s in self.status.items()}
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _usable(self, key: str, model: str) -> datetime | None:
        """None if usable now, else when it becomes usable (datetime.max if never)."""
        s = self.status[fingerprint(key)]
        if s.state == "invalid":
            return datetime.max.replace(tzinfo=UTC)
        until = s.exhausted_until.get(model)
        return (
            datetime.fromisoformat(until)
            if until and datetime.fromisoformat(until) > _now()
            else None
        )

    async def acquire(self, model: str) -> str:
        """Next usable key for this model, round-robin. Waits briefly for a per-minute reset."""
        while True:
            with self._lock:
                for i in range(len(self.keys)):
                    key = self.keys[(self._next + i) % len(self.keys)]
                    if self._usable(key, model) is None:
                        self._next = (self._next + i + 1) % len(self.keys)
                        return key
                waits = [w for k in self.keys if (w := self._usable(k, model)) is not None]
                soonest = min(waits, default=None)
            if soonest is None or soonest == datetime.max.replace(tzinfo=UTC):
                raise NoGeminiKey(f"no valid Gemini key for {model} (all {len(self.keys)} invalid)")
            wait = soonest - _now()
            if wait > MAX_WAIT_FOR_RESET:
                raise NoGeminiKey(
                    f"all Gemini keys are out of quota for {model} until "
                    f"{soonest.isoformat(timespec='minutes')} UTC"
                )
            await asyncio.sleep(max(wait.total_seconds(), 0.5))

    def mark_ok(self, key: str) -> None:
        with self._lock:
            s = self.status[fingerprint(key)]
            s.state, s.last_error, s.checked_at = "active", None, _now().isoformat()
            self._save()

    def report(self, key: str, model: str, exc: ModelHTTPError) -> bool:
        """Record a failure. True if it was the key's fault (so another key may succeed)."""
        kind, reset = classify(exc)
        if kind is None:
            return False
        with self._lock:
            s = self.status[fingerprint(key)]
            s.checked_at, s.last_error = _now().isoformat(), f"{exc.status_code} {kind}"
            if kind == "invalid":
                s.state = "invalid"
            elif reset:
                s.exhausted_until[model] = reset.isoformat()
            self._save()
        return True

    def report_run_failure(self, exc: BaseException, leases: dict[str, str]) -> bool:
        """For a failed agent run: mark every key that caused a ModelHTTPError in it."""
        errors = exc.exceptions if isinstance(exc, FallbackExceptionGroup) else (exc,)
        blamed = False
        for e in errors:
            if isinstance(e, ModelHTTPError) and (key := leases.get(e.model_name)):
                blamed |= self.report(key, e.model_name, e)
        return blamed


@cache
def get_pool(keys: tuple[str, ...], status_path: Path) -> KeyPool:
    return KeyPool(list(keys), status_path)


def table(pool: KeyPool) -> str:
    rows = [f"{'key':<16} {'state':<8} {'out of quota until (UTC)':<40} last error"]
    for key in pool.keys:
        fp = fingerprint(key)
        s = pool.status[fp]
        quota = (
            ", ".join(
                f"{m}: {t[:16]}"
                for m, t in s.exhausted_until.items()
                if datetime.fromisoformat(t) > _now()
            )
            or "-"
        )
        rows.append(f"{fp:<16} {s.state:<8} {quota:<40} {s.last_error or '-'}")
    return "\n".join(rows)


async def _check(pool: KeyPool, models: list[str]) -> None:
    from pydantic_ai import Agent
    from pydantic_ai.models.google import GoogleModel
    from pydantic_ai.providers.google import GoogleProvider

    for key in pool.keys:
        for model in models:
            agent = Agent(GoogleModel(model, provider=GoogleProvider(api_key=key)))
            try:
                await agent.run("Reply with OK.")
                pool.mark_ok(key)
            except ModelHTTPError as exc:
                if not pool.report(key, model, exc):
                    print(f"{fingerprint(key)} {model}: unexpected {exc.status_code}")
            if pool.status[fingerprint(key)].state == "invalid":
                break


def prune_env(env_path: Path, pool: KeyPool) -> tuple[int, int]:
    """Rewrite .env: one GEMINI_API_KEYS line with every non-invalid key; invalid keys and the
    old key lines/comments are removed. A backup goes to .env.bak (gitignored)."""
    text = env_path.read_text(encoding="utf-8")
    env_path.with_suffix(".bak").write_text(text, encoding="utf-8")
    keep = [k for k in pool.keys if pool.status[fingerprint(k)].state != "invalid"]
    key_re = re.compile(r"AIza[0-9A-Za-z_-]{20,}")
    lines = [
        ln
        for ln in text.splitlines()
        if not key_re.search(ln) and not ln.startswith(("GEMINI_API_KEY", "GEMINI_API_KEYS"))
    ]
    lines.append(f"GEMINI_API_KEYS={','.join(keep)}")
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(keep), len(pool.keys) - len(keep)


if __name__ == "__main__":
    import argparse

    from app.config import REPO_ROOT, settings

    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="test every key with a tiny call")
    parser.add_argument("--prune-env", action="store_true", help="rewrite .env without bad keys")
    parser.add_argument(
        "--all-in-env", action="store_true", help="also test keys found in .env comments"
    )
    args = parser.parse_args()
    keys = settings.gemini_keys()
    env = REPO_ROOT / ".env"
    if args.all_in_env and env.exists():
        keys += re.findall(r"AIza[0-9A-Za-z_-]{20,}", env.read_text(encoding="utf-8"))
    pool = KeyPool(keys, settings.data_dir / "gemini_keys.json")
    if args.check:
        asyncio.run(_check(pool, ["gemini-3.5-flash-lite", "gemini-3.5-flash"]))
    print(table(pool))
    if args.prune_env:
        kept, removed = prune_env(env, pool)
        print(
            f".env rewritten: {kept} key(s) kept in GEMINI_API_KEYS, {removed} invalid removed "
            f"(backup: .env.bak)"
        )
