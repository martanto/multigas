"""Shared date selection and daily extraction CLI tests."""

import importlib
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from multigas.core.exceptions import DatasetError, LoaderError
from multigas.core.types import DatasetType
from multigas.data.multigas_data import MultiGasData
from multigas.utils.dataframe import select_date_range


MODULE = importlib.import_module("multigas.cli.commands.extract")
HERE = Path(__file__).parent


@pytest.fixture
def cli():
    from multigas.cli.main import cli

    return cli


@pytest.fixture
def output():
    root = HERE / "extract-test-output"
    root.mkdir(exist_ok=True)
    yield root
    shutil.rmtree(root)


@pytest.fixture
def frame():
    index = pd.date_range("2026-01-01", periods=12, freq="6h", name="TIMESTAMP")
    return pd.DataFrame({"value": range(12)}, index=index)


def test_select_date_range_without_bounds_sorts(frame):
    selected = select_date_range(frame.sort_index(ascending=False))
    assert selected.index.is_monotonic_increasing
    pd.testing.assert_frame_equal(selected, frame)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("2026-01-02", None, 8),
        (None, "2026-01-02", 8),
        ("2026-01-02", "2026-01-02", 4),
    ],
)
def test_select_date_range_inclusive_and_one_sided(frame, start, end, expected):
    assert len(select_date_range(frame, start, end)) == expected


def test_select_date_range_timezone_aware():
    index = pd.date_range(
        "2026-01-01", periods=48, freq="h", tz="Asia/Jakarta", name="TIMESTAMP"
    )
    frame = pd.DataFrame({"value": range(48)}, index=index)
    selected = select_date_range(frame, "2026-01-02", "2026-01-02")
    assert len(selected) == 24
    assert selected.index.tz is not None
    assert selected.index.min() == pd.Timestamp("2026-01-02", tz="Asia/Jakarta")


@pytest.mark.parametrize(
    ("start", "end", "match"),
    [
        ("2026-01-03", "2026-01-01", "on or before"),
        ("not-a-date", None, "Invalid date range"),
        (None, "NaT", "Invalid date range"),
        ("2027-01-01", None, "No records"),
    ],
)
def test_select_date_range_rejects_bad_ranges(frame, start, end, match):
    with pytest.raises(DatasetError, match=match):
        select_date_range(frame, start, end)


@pytest.mark.parametrize(
    "bad_frame",
    [
        pd.DataFrame({"value": [1]}),
        pd.DataFrame(
            {"value": [1, 2]},
            index=pd.DatetimeIndex([pd.Timestamp("2026-01-01"), pd.NaT]),
        ),
    ],
)
def test_select_date_range_requires_valid_datetime_index(bad_frame):
    with pytest.raises(DatasetError, match="valid DatetimeIndex"):
        select_date_range(bad_frame)


def _write_source(path: Path) -> None:
    index = pd.to_datetime(
        [
            "2026-01-01 00:00",
            "2026-01-01 06:00",
            "2026-01-02 00:00",
            "2026-01-02 06:00",
            "2026-01-03 00:00",
            "2026-01-03 06:00",
        ]
    )
    pd.DataFrame(
        {"TIMESTAMP": index, "RECORD": range(6), "Avg_SO2": range(6)}
    ).to_csv(path, index=False)


def test_extract_is_registered_and_requires_arguments(cli):
    runner = CliRunner()
    root_help = runner.invoke(cli, ["--help"])
    assert root_help.exit_code == 0
    assert "extract" in root_help.output

    missing = runner.invoke(cli, ["extract"])
    assert missing.exit_code == 2
    assert "INPUT_PATH" in missing.output


@pytest.mark.parametrize("dataset_type", ["span", "wx", "bad"])
def test_extract_restricts_dataset_types(cli, output, dataset_type):
    source = output / "source.csv"
    _write_source(source)
    result = CliRunner().invoke(
        cli, ["extract", str(source), "--dataset-type", dataset_type]
    )
    assert result.exit_code == 2
    assert "Invalid value for '--dataset-type'" in result.output


def test_extract_loads_normalized_data_and_passes_all_rows(
    cli, output, monkeypatch
):
    source = output / "source.csv"
    source.touch()
    index = pd.date_range("2026-01-01", periods=4, freq="6h", name="TIMESTAMP")
    dataset = MultiGasData(
        pd.DataFrame({"value": range(4)}, index=index),
        DatasetType.ZERO,
        source,
    )
    captured = {}

    def fake_read_file(*args, **kwargs):
        captured["load"] = (args, kwargs)
        return dataset

    def fake_extract_daily(root):
        captured["frame"] = dataset.df.copy()
        captured["root"] = root
        return pd.DataFrame(
            [{"date": "2026-01-01", "total_data": 4, "completeness": 100.0}]
        )

    monkeypatch.setattr(MODULE, "read_file", fake_read_file)
    monkeypatch.setattr(dataset, "extract_daily", fake_extract_daily)
    result = CliRunner().invoke(
        cli,
        [
            "extract",
            str(source),
            "--dataset-type",
            "zero",
            "--output-dir",
            str(output),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["load"][1]["normalize"] is True
    assert captured["load"][1]["index_col"] == "TIMESTAMP"
    pd.testing.assert_frame_equal(captured["frame"], dataset.df)
    assert captured["root"] == output


def test_extract_bounded_range_and_json_outputs(cli, output):
    source = output / "bounded.csv"
    _write_source(source)
    result = CliRunner().invoke(
        cli,
        [
            "extract",
            str(source),
            "--dataset-type",
            "zero",
            "--start-date",
            "2026-01-02",
            "--end-date",
            "2026-01-02",
            "--output-dir",
            str(output),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["start_date"] == payload["end_date"] == "2026-01-02"
    assert payload["extracted_days"] == 1
    assert payload["extracted_records"] == 2
    assert Path(payload["daily_directory"]).joinpath("2026-01-02.csv").exists()
    assert Path(payload["completeness_csv"]).exists()
    assert Path(payload["completeness_csv"]).with_suffix(".png").exists()


def test_extract_all_data_creates_each_daily_file(cli, output):
    source = output / "all.csv"
    _write_source(source)
    result = CliRunner().invoke(
        cli,
        [
            "extract",
            str(source),
            "--dataset-type",
            "zero",
            "--output-dir",
            str(output),
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["extracted_days"] == 3
    assert payload["extracted_records"] == 6
    daily = Path(payload["daily_directory"])
    assert sorted(path.name for path in daily.glob("*.csv")) == [
        "2026-01-01.csv",
        "2026-01-02.csv",
        "2026-01-03.csv",
    ]


def test_extract_reports_loading_selection_and_extraction_errors(
    cli, output, monkeypatch
):
    source = output / "errors.csv"
    _write_source(source)
    runner = CliRunner()

    monkeypatch.setattr(
        MODULE,
        "read_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(LoaderError("broken source")),
    )
    loading = runner.invoke(
        cli, ["extract", str(source), "--dataset-type", "zero"]
    )
    assert loading.exit_code == 1
    assert "Could not load input: broken source" in loading.output

    dataset = MultiGasData(
        pd.DataFrame(
            {"value": [1]},
            index=pd.DatetimeIndex(["2026-01-01"], name="TIMESTAMP"),
        ),
        DatasetType.ZERO,
        source,
    )
    monkeypatch.setattr(MODULE, "read_file", lambda *args, **kwargs: dataset)
    selection = runner.invoke(
        cli,
        [
            "extract",
            str(source),
            "--dataset-type",
            "zero",
            "--start-date",
            "2027-01-01",
        ],
    )
    assert selection.exit_code == 1
    assert "Could not select dates: No records" in selection.output

    monkeypatch.setattr(
        dataset,
        "extract_daily",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk full")),
    )
    extraction = runner.invoke(
        cli, ["extract", str(source), "--dataset-type", "zero"]
    )
    assert extraction.exit_code == 1
    assert "Could not extract daily files: disk full" in extraction.output


def test_extract_rejects_non_iso_dates(cli, output):
    source = output / "dates.csv"
    _write_source(source)
    result = CliRunner().invoke(
        cli,
        [
            "extract",
            str(source),
            "--dataset-type",
            "zero",
            "--start-date",
            "01/02/2026",
        ],
    )
    assert result.exit_code == 2
    assert "does not match the format" in result.output
