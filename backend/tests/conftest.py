"""Shared test fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tiny_repository() -> Path:
    return Path(__file__).parent / "fixtures" / "tiny_repo"
