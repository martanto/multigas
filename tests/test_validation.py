from __future__ import annotations

import pandas as pd
import pytest

from multigas.utils.validation import check_sampling_consistency, validate_columns


def test_check_sampling_consistency_allows_two_rows_with_default_frequency() -> None:
    df = pd.DataFrame(
        {"value": [1, 2]},
        index=pd.date_range("2025-01-01", periods=2, freq="10min"),
    )

    is_consistent, consistent, inconsistent, rate = check_sampling_consistency(df)

    assert is_consistent is True
    assert len(consistent) == 2
    assert inconsistent.empty
    assert rate == 600


def test_check_sampling_consistency_uses_total_seconds_for_long_intervals() -> None:
    df = pd.DataFrame(
        {"value": [1, 2]},
        index=pd.date_range("2025-01-01", periods=2, freq="1D"),
    )

    is_consistent, _, _, rate = check_sampling_consistency(
        df, expected_freq="1D", tolerance="0s"
    )

    assert is_consistent is True
    assert rate == 86_400


def test_validate_columns_ignores_excluded_columns() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    validate_columns(df, columns=["a", "missing"], exclude_columns=["missing"])


def test_validate_columns_reports_all_missing_columns() -> None:
    df = pd.DataFrame({"a": [1], "b": [2]})

    with pytest.raises(ValueError) as exc_info:
        validate_columns(df, columns=["a", "c", "d"])

    message = str(exc_info.value)
    assert "Missing required columns: ['c', 'd']" in message
    assert "Available columns: ['a', 'b']" in message
