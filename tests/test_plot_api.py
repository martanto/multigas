from pathlib import Path
import shutil

import pandas as pd
import pytest
from click.testing import CliRunner

from multigas.core.exceptions import ColumnError, DatasetError
from multigas.core.types import DatasetType
from multigas.data.multigas_data import MultiGasData
from multigas.plot import Plot

TESTS_DIR = Path(__file__).parent


def _dataset() -> MultiGasData:
    index = pd.date_range("2024-01-01", periods=10, freq="6h", name="TIMESTAMP")
    from multigas.plot.six_hours import REQUIRED_COLUMNS

    frame = pd.DataFrame({column: range(10) for column in REQUIRED_COLUMNS}, index=index)
    return MultiGasData(frame, DatasetType.SIX_HOURS, TESTS_DIR / "plot-api.dat")


def test_plot_validates_dataset_type_and_columns() -> None:
    data = _dataset()
    with pytest.raises(DatasetError, match="conflicts"):
        Plot(data, DatasetType.ONE_MINUTE)
    wrong_type = MultiGasData(data.df, DatasetType.ONE_MINUTE, data.source_path)
    with pytest.raises(DatasetError, match="not supported"):
        Plot(wrong_type)
    missing = MultiGasData(data.df.drop(columns=[data.df.columns[0]]),
                           DatasetType.SIX_HOURS, data.source_path)
    with pytest.raises(ColumnError):
        Plot(missing)
    with pytest.raises(ValueError, match="PNG, PDF, or HTML"):
        Plot(data, save_as="SVG")


@pytest.mark.parametrize(
    "format_name, suffix", [("png", ".png"), ("PDF", ".pdf"), ("HTML", ".html")]
)
@pytest.mark.parametrize("columns", [1, 2])
@pytest.mark.parametrize("log_scale", [False, True])
def test_plot_all_renders_both_periods(format_name: str, suffix: str, columns: int,
                                     log_scale: bool, monkeypatch) -> None:
    import multigas.plot.six_hours as layout

    scales = []
    original_y_axis = layout.y_axis

    def capture_scale(values, is_ratio, log_scale=False):
        result = original_y_axis(values, is_ratio, log_scale)
        scales.append(result[0])
        return result

    monkeypatch.setattr(layout, "y_axis", capture_scale)
    data = _dataset()
    data.df += 1  # Every ratio is positive, so log axes can be used.
    output_root = TESTS_DIR / f"plot-api-output-{format_name.lower()}"
    paths = Plot(data, save_as=format_name, output_dir=output_root, columns=columns,
                 log_scale=log_scale).plot_all()
    try:
        assert set(paths) == {"full_period", "trailing_three_months"}
        assert all(path.suffix == suffix and path.exists() for path in paths.values())
        assert all(path.parent == output_root / "figures" for path in paths.values())
        assert scales == ([log_scale] * 5 + [False] * 4) * 2
    finally:
        for path in paths.values():
            path.unlink(missing_ok=True)
        paths[next(iter(paths))].parent.rmdir()
        output_root.rmdir()


def test_plot_all_slices_inclusive_dates(monkeypatch) -> None:
    import multigas.plot.six_hours as layout

    captured: list[tuple[pd.Timestamp, pd.Timestamp]] = []

    def fake_render(data, start, end, path, save_as, columns=2, width=None, height=None,
                    log_scale=False):
        captured.append((start, end))
        return path

    monkeypatch.setattr(layout, "render", fake_render)
    paths = Plot(
        _dataset(),
        output_dir=TESTS_DIR / "plot-api-date-output",
        start_date="2024-01-02",
        end_date="2024-01-02",
    ).plot_all()
    assert len(paths) == 2
    assert captured == [
        (pd.Timestamp("2024-01-02 00:00"), pd.Timestamp("2024-01-02 18:00")),
        (pd.Timestamp("2024-01-02 00:00"), pd.Timestamp("2024-01-02 18:00")),
    ]
    (TESTS_DIR / "plot-api-date-output" / "figures").rmdir()
    (TESTS_DIR / "plot-api-date-output").rmdir()


def test_plot_all_empty_date_range_raises_clear_error() -> None:
    with pytest.raises(DatasetError, match="No data found.*overlaps the dataset"):
        Plot(
            _dataset(), start_date="2025-01-01", end_date="2025-01-02"
        ).plot_all()


def test_plot_command_json(monkeypatch) -> None:
    from multigas.cli.main import cli

    input_path = TESTS_DIR / "plot-cli.csv"
    _dataset().df.to_csv(input_path)
    output_root = TESTS_DIR / "plot-cli-output"
    try:
        result = CliRunner().invoke(cli, ["plot", str(input_path), "--dataset-type", "6h",
                                          "--output-dir", str(output_root), "--one-column", "--json"])
        assert result.exit_code == 0, result.output
        assert '"full_period"' in result.output
        assert '"trailing_three_months"' in result.output
    finally:
        input_path.unlink(missing_ok=True)
        shutil.rmtree(output_root, ignore_errors=True)


def test_plot_command_reports_empty_date_range() -> None:
    from multigas.cli.main import cli

    input_path = TESTS_DIR / "plot-cli-empty-range.csv"
    _dataset().df.to_csv(input_path)
    output_root = TESTS_DIR / "plot-cli-empty-range-output"
    try:
        result = CliRunner().invoke(
            cli,
            [
                "plot",
                str(input_path),
                "--dataset-type",
                "6h",
                "--output-dir",
                str(output_root),
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-01-02",
            ],
        )
        assert result.exit_code == 1
        assert "Error: No data found between 2025-01-01 and 2025-01-02" in result.output
        assert "Choose a date range that overlaps the dataset" in result.output
    finally:
        input_path.unlink(missing_ok=True)
        shutil.rmtree(output_root, ignore_errors=True)


@pytest.mark.parametrize("options, expected", [([], False), (["--log-scale"], True)])
def test_plot_command_forwards_log_scale(monkeypatch, options, expected) -> None:
    import importlib
    from multigas.cli.main import cli

    command = importlib.import_module("multigas.cli.commands.plot")
    captured = {}

    class FakePlot:
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)

        def plot_all(self):
            return {"full_period": TESTS_DIR / "example.png"}

    monkeypatch.setattr(command, "Plot", FakePlot)
    result = CliRunner().invoke(
        cli, ["plot", __file__, "--dataset-type", "6h", "--json", *options]
    )
    assert result.exit_code == 0, result.output
    assert captured["log_scale"] is expected


def _series(values: list[float]) -> pd.Series:
    index = pd.date_range("2024-01-01", periods=len(values), freq="6h")
    return pd.Series(values, index=index, dtype=float)


def test_y_axis_defaults_to_linear_and_log_is_optional_for_positive_ratios() -> None:
    from multigas.plot.six_hours import y_axis

    wide = _series([1.0, 5.0, 20.0, 400.0] * 10)
    assert y_axis(wide, is_ratio=True)[0] is False
    use_log, lower, upper = y_axis(wide, is_ratio=True, log_scale=True)
    assert use_log and 0 < lower < 1.0 and upper > 400.0
    assert y_axis(wide, is_ratio=False, log_scale=True)[0] is False
    assert y_axis(_series([2.0, 3.0, 4.0] * 10), True, True)[0] is True
    assert y_axis(_series([3.0] * 10), True, True)[0] is True
    for minimum in [-1.0, 0.0]:
        assert y_axis(_series([minimum, 5.0, 400.0] * 10), True, True)[0] is False


def test_y_axis_excludes_only_far_outliers() -> None:
    from multigas.plot.six_hours import y_axis

    faulty = _series([380.0 + (i % 20) for i in range(400)] + [0.0, 0.0])
    _, lower, upper = y_axis(faulty, is_ratio=False)
    assert 300 < lower < 380 and upper > 399
    mild = _series([380.0 + (i % 20) for i in range(400)] + [360.0])
    assert y_axis(mild, is_ratio=False)[1] < 360


def test_trend_breaks_across_gaps_and_needs_enough_days() -> None:
    from multigas.plot.six_hours import trend

    index = pd.date_range("2024-01-01", periods=40, freq="6h").append(
        pd.date_range("2024-03-01", periods=40, freq="6h")
    )
    line = trend(pd.Series(range(80), index=index, dtype=float))
    assert line is not None
    assert line.loc["2024-01-03":"2024-01-08"].notna().all()
    assert line.loc["2024-01-20":"2024-02-20"].isna().all()
    assert trend(_series([1.0, 2.0])) is None
    assert trend(pd.Series(dtype=float)) is None


def test_log_ticks_add_intermediate_labels_for_narrow_ranges() -> None:
    from multigas.plot.six_hours import log_ticks

    assert log_ticks(3, 40) == [5.0, 10.0, 20.0]
    assert log_ticks(0.5, 900) == [1.0, 10.0, 100.0]


@pytest.mark.parametrize("format_name", ["PNG", "HTML"])
def test_render_handles_empty_outlier_and_sparse_panels(format_name: str) -> None:
    data = _dataset()
    frame = data.df.astype(float)
    frame["Avg_CO2_SO2_ratio"] = float("nan")
    frame["Avg_SO2_proportion"] = float("nan")
    frame["Avg_H2S_proportion"] = float("nan")
    frame["Avg_CO2_lowpass"] = [400.0 + i for i in range(9)] + [0.0]
    frame["Avg_SO2"] -= 5
    data = MultiGasData(frame, DatasetType.SIX_HOURS, data.source_path)
    output_root = TESTS_DIR / f"plot-api-edge-output-{format_name.lower()}"
    try:
        paths = Plot(data, save_as=format_name, output_dir=output_root).plot_all()
        assert all(path.exists() and path.stat().st_size > 0 for path in paths.values())
    finally:
        shutil.rmtree(output_root, ignore_errors=True)


def test_gaps_reports_only_long_record_gaps() -> None:
    from multigas.plot.six_hours import gaps

    index = pd.date_range("2024-01-01", periods=8, freq="6h").append(
        pd.date_range("2024-01-10", periods=4, freq="6h")
    )
    assert gaps(index) == [
        (pd.Timestamp("2024-01-02 18:00"), pd.Timestamp("2024-01-10 00:00"))
    ]
    assert gaps(pd.date_range("2024-01-01", periods=8, freq="1D")) == []


def test_caption_flags_gaps_and_non_positive_so2_baseline() -> None:
    from multigas.plot.six_hours import caption

    data = _dataset()
    plain = caption(data, data.df, "Note.")
    assert "on linear axes" in plain
    assert "logarithmic" not in plain
    assert "logarithmic axes where all readings are positive, otherwise linear" in caption(
        data, data.df, "Note.", log_scale=True
    )
    assert "Grey bands" not in plain and "sensor baseline" not in plain
    frame = data.df.astype(float)
    frame.index = frame.index[:-1].append(
        pd.DatetimeIndex([pd.Timestamp("2024-02-01")])
    )
    frame["Avg_SO2"] = -0.1
    flagged = caption(data, frame, "Note.")
    assert "Grey bands mark periods of more than 2 days" in flagged
    assert "at or below zero (sensor baseline)" in flagged


@pytest.mark.parametrize("columns", [0, 3, True, 1.5, "1"])
def test_plot_rejects_invalid_columns(columns) -> None:
    with pytest.raises(ValueError, match="columns must be 1 or 2"):
        Plot(_dataset(), columns=columns)
