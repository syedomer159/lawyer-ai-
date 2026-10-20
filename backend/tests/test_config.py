from pathlib import Path

import pytest

from app.config import REPO_ROOT
from tests.conftest import TestSettings


def test_blank_env_values_fall_back_to_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATA_DIR", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    s = TestSettings()
    assert s.data_dir == REPO_ROOT / "data"
    assert s.gemini_api_key is None


def test_explicit_env_values_still_apply(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MODEL_PROFILE", "local")
    s = TestSettings()
    assert s.data_dir == tmp_path and s.model_profile == "local"
