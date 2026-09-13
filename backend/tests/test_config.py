"""Tests for deterministic project configuration paths and validation."""

import pytest
from pydantic import ValidationError

from app.config import ENV_FILE, PROJECT_ROOT, Settings


def test_env_file_is_resolved_from_project_files() -> None:
    assert PROJECT_ROOT == ENV_FILE.parent
    assert ENV_FILE == PROJECT_ROOT / ".env"
    assert ENV_FILE.is_absolute()
    assert Settings.model_config["env_file"] == ENV_FILE


def test_default_top_k_cannot_exceed_service_maximum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEFAULT_TOP_K", "51")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_llm_base_url_rejects_obviously_invalid_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LLM_BASE_URL", "not-a-url")

    with pytest.raises(ValidationError, match=r"absolute http\(s\) URL"):
        Settings(_env_file=None)
