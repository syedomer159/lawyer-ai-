import hashlib
import os

# Before app imports: the app's startup must not export to Phoenix from tests (test_llm captures
# spans in memory instead). An env var beats the developer's .env.
os.environ["TRACING"] = "false"

import re
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict

from app.api.deps import get_embedder, get_settings
from app.config import REPO_ROOT, Settings
from app.main import app

SAMPLES = REPO_ROOT / "samples"
CASE1 = SAMPLES / "case1_state_v_arjun_verma" / "files"
CASE2 = SAMPLES / "case2_state_v_kavita_rao" / "files"


class TestSettings(Settings):
    """Settings that ignore the developer's .env, so tests behave the same on every machine."""

    __test__ = False  # not a pytest test class
    model_config = SettingsConfigDict(env_file=None, extra="ignore", env_ignore_empty=True)


class FakeEmbedder:
    """Deterministic bag-of-words hashing: shared words -> similar vectors. No Ollama needed."""

    DIM = 256

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.DIM, dtype=np.float32)
        for word in re.findall(r"\w+", text.lower()):
            v[int(hashlib.md5(word.encode()).hexdigest(), 16) % self.DIM] += 1
        n = np.linalg.norm(v)
        return v / n if n else v

    async def embed_documents(self, texts: list[str]) -> np.ndarray:
        return np.array([self._vec(t) for t in texts], dtype=np.float32).reshape(-1, self.DIM)

    async def embed_query(self, text: str) -> np.ndarray:
        return self._vec(text)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"  # async tests run via the anyio plugin that ships with FastAPI


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_settings] = lambda: TestSettings(data_dir=tmp_path)
    app.dependency_overrides[get_embedder] = FakeEmbedder
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def create_case(client: TestClient, title: str = "Test case") -> str:
    res = client.post("/api/cases", json={"title": title, "client": "Client"})
    assert res.status_code == 201
    return res.json()["id"]


def upload(client: TestClient, case_id: str, *paths: Path) -> list[dict]:
    files = [("files", (p.name, p.read_bytes())) for p in paths]
    res = client.post(f"/api/cases/{case_id}/documents", files=files)
    assert res.status_code == 201, res.text
    return res.json()


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
