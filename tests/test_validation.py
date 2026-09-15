from __future__ import annotations

import pandas as pd
import pytest

from multigas.core.exceptions import ColumnError
from multigas.utils.validation import check_columns_exist, check_sampling_consistency


def test_check_sampling_consistency_allows_two_rows_with_matching_frequency() -> None:
    df = pd.DataFrame(
        {"value": [1, 2]},
        index=pd.date_range("2025-01-01", periods=2, freq="1min"),
    )

    is_consistent, consistent, inconsistent, rate = check_sampling_consistency(
        df, expected_freq="1min"
    )

    assert is_consistent is True
    assert len(consistent) == 2
    assert inconsistent.empty
    assert rate == 60


def test_check_sampling_consistency_uses_total_seconds_for_long_intervals() -> None:
    df = pd.DataFrame(
        {"value": [1, 2]},
        index=pd.date_range("2025-01-01", periods=2, freq="6h"),
    )

    is_consistent, _, _, rate = check_sampling_consistency(
        df, expected_freq="6h", tolerance="0s"
    )

    assert is_consistent is True
    assert rate == 21_600


def test_check_columns_exist_accepts_single_name_when_present() -> None:
    check_columns_exist("a", ["a", "b"])


def test_check_columns_exist_accepts_list_when_all_present() -> None:
    check_columns_exist(["a", "b"], ["a", "b", "c"])


def test_check_columns_exist_raises_column_error_for_single_missing_name() -> None:
    with pytest.raises(ColumnError) as exc_info:
        check_columns_exist("nope", ["a", "b"])

    message = str(exc_info.value)
    assert "Column(s) not found: ['nope']" in message
    assert "Available: ['a', 'b']" in message


def test_check_columns_exist_reports_all_missing_names_in_one_message() -> None:
    with pytest.raises(ColumnError) as exc_info:
        check_columns_exist(["a", "c", "d"], ["a", "b"])

    message = str(exc_info.value)
    assert "Column(s) not found: ['c', 'd']" in message
    assert "Available: ['a', 'b']" in message


def test_check_columns_exist_preserves_order_of_missing_names() -> None:
    with pytest.raises(ColumnError) as exc_info:
        check_columns_exist(["z", "a", "y", "b"], ["a", "b"])

    message = str(exc_info.value)
    assert "Column(s) not found: ['z', 'y']" in message


def test_check_columns_exist_ignores_pre_filtered_names() -> None:
    # Replaces the old exclude_columns feature: filter before calling.
    excluded = {"missing"}
    to_check = [c for c in ["a", "missing"] if c not in excluded]

    check_columns_exist(to_check, ["a", "b"])
