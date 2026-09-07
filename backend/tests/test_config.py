"""Tests for deterministic project configuration paths."""

from app.config import ENV_FILE, PROJECT_ROOT, Settings


def test_env_file_is_resolved_from_project_files() -> None:
    assert PROJECT_ROOT == ENV_FILE.parent
    assert ENV_FILE == PROJECT_ROOT / ".env"
    assert ENV_FILE.is_absolute()
    assert Settings.model_config["env_file"] == ENV_FILE
