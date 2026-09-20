"""The experiment helpers are deliberately limited to development data."""

from pathlib import Path

import pytest

from scripts.analyse_signal_ranking import analyse
from scripts.benchmark_signal_ranking import _summary, measure


def test_diagnostic_rejects_holdout_before_accessing_database(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Only DEV1 and DEV2"):
        analyse(object(), "holdout", tmp_path)


def test_benchmark_rejects_holdout_before_accessing_database() -> None:
    with pytest.raises(ValueError, match="Only DEV1 and DEV2"):
        measure(object(), "holdout", 8, 3)


def test_latency_summary_reports_actual_sample_count_and_percentiles() -> None:
    assert _summary([0.001, 0.004, 0.002, 0.003]) == {
        "observations": 4,
        "median_ms": 2.5,
        "p95_ms": 4.0,
    }
