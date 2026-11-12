"""Selected-column CLI, validation, slicing and real export regression tests."""

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest
from click.testing import CliRunner

from multigas.core.exceptions import ColumnError, DatasetError, PlotError
from multigas.core.types import DatasetType
from multigas.data.multigas_data import MultiGasData
from multigas.plot import plot_columns
from multigas.plot.columns import _select_dates, parse_column_names

MODULE = importlib.import_module("multigas.plot.columns")
HERE = Path(__file__).parent


@pytest.fixture
def cli():
    # The import-isolation suite deliberately removes modules from sys.modules.
    # Resolve the CLI at invocation time, like the existing plot API tests.
    from multigas.cli.main import cli
    return cli


@pytest.fixture
def output():
    root = HERE / "columns-test-output"
    root.mkdir(exist_ok=True)
    yield root
    shutil.rmtree(root)


@pytest.fixture
def data():
    index = pd.date_range("2025-01-01", periods=12, freq="6h", name="TIMESTAMP")
    return MultiGasData(pd.DataFrame({
        "Avg_CO2_lowpass": np.arange(12, dtype=float),
        "Avg_SO2": [-1, 0, np.inf, -np.inf, np.nan, 2, 1, 0, 2, 4, 8, 1e6],
        "Avg_H2S": np.arange(12, dtype=float),
        "empty": [None] * 12,
        "text": ["station"] * 12,
        "text2": ["site"] * 12,
        "RECORD": np.arange(12),
    }, index=index), DatasetType.SIX_HOURS, HERE / "columns-source.csv")


@pytest.mark.parametrize("tokens", [
    [" A,B", "B", " C "], " A,B,C,A ", ["A", "B", "C", "A"],
])
def test_parse_order(tokens):
    assert parse_column_names(tokens) == ["A", "B", "C"]


@pytest.mark.parametrize("tokens", [[], "", ["A,"], [",A"], ["A,,B"], [" "]])
def test_parse_empty_names(tokens):
    with pytest.raises(ValueError, match="non-empty"):
        parse_column_names(tokens)


def test_missing_and_nonnumeric_aggregated(data, output):
    with pytest.raises(ColumnError) as caught:
        plot_columns(data, ["absent", "also_absent"], output_dir=output)
    message = str(caught.value)
    assert "absent" in message and "also_absent" in message
    assert str(data.df.columns.tolist()) in message
    with pytest.raises(ColumnError, match="text.*text2.*numeric"):
        plot_columns(data, ["text", "text2"], output_dir=output)


@pytest.mark.parametrize("start,end,count", [
    ("2025-01-02", "2025-01-02", 4),
    ("2025-01-02", None, 8), (None, "2025-01-02", 8),
    (None, "2025-01-02 00:00", 5), (None, None, 12),
])
def test_inclusive_dates(data, start, end, count):
    assert len(_select_dates(data.df, start, end)) == count


@pytest.mark.parametrize("start,end", [
    ("broken", None), (None, "broken"), ("NaT", None),
    ("2025-01-03", "2025-01-01"), ("2026-01-01", None),
])
def test_bad_dates(data, start, end):
    with pytest.raises(DatasetError, match="date range"):
        _select_dates(data.df, start, end)


def test_finite_order_caption_and_no_mutation(data, output, monkeypatch):
    original = data.df.copy(deep=True)
    captured = {}

    def render(frame, path, columns, text):
        captured.update(frame=frame, columns=columns, text=text)

    monkeypatch.setattr(MODULE, "_render_static", render)
    plot_columns(data, ["Avg_SO2,empty", "Avg_H2S", "Avg_SO2"], output_dir=output)
    frame = captured["frame"]
    assert list(frame) == ["Avg_SO2", "empty", "Avg_H2S"]
    assert np.isfinite(frame["Avg_SO2"].dropna()).all()
    assert frame["Avg_SO2"].max() == 1e6
    assert "Excluded 15" in captured["text"]
    assert "Observations only" in captured["text"]
    assert "cross-sensitivity" in captured["text"]
    assert "Source:" in captured["text"]
    pd.testing.assert_frame_equal(data.df, original)


def test_normalized_path_sampling_and_empty_column(data, output, monkeypatch):
    source = output / "raw.csv"
    frame = data.df.copy()
    frame = frame.drop(frame.index[3])
    # A duplicate retains its last reading; the first row after the gap is removed.
    frame = pd.concat([frame, frame.iloc[[1]].assign(Avg_CO2_lowpass=999)])
    frame.to_csv(source)
    captured = {}
    monkeypatch.setattr(MODULE, "_render_static", lambda frame, *args: captured.update(frame=frame))
    plot_columns(source, ["Avg_CO2_lowpass", "empty"], "6h", output_dir=output)
    result = captured["frame"]
    assert len(result) == 10
    assert result.loc[data.df.index[1], "Avg_CO2_lowpass"] == 999
    assert data.df.index[4] not in result.index
    assert result["empty"].isna().all()


@pytest.mark.parametrize("kind", list(DatasetType))
def test_all_dataset_types(data, output, kind, cli):
    source = output / "source.csv"
    frame = data.df.copy()
    if kind.value in {"1s", "2s", "1min", "6h"}:
        frame.index = pd.date_range("2025-01-01", periods=len(frame), freq=kind.value,
                                    name="TIMESTAMP")
    frame.to_csv(source)
    result = CliRunner().invoke(cli, ["plot", "columns", "Avg_SO2",
        "--source", str(source), "--dataset-type", kind.value,
        "--save-as", "HTML", "--output-dir", str(output), "--json"])
    assert result.exit_code == 0, result.output
    assert Path(json.loads(result.output)["figure"]).exists()


@pytest.mark.parametrize("names", [["Avg_CO2_lowpass"],
    ["Avg_CO2_lowpass", "empty", "Avg_SO2"],
    ["Avg_CO2_lowpass", "Avg_SO2", "Avg_H2S", "empty"]])
@pytest.mark.parametrize("layout", [1, 2])
@pytest.mark.parametrize("fmt", ["PNG", "PDF", "HTML"])
def test_real_exports(data, output, names, layout, fmt):
    path = plot_columns(data, names, save_as=fmt, output_dir=output,
                        layout_columns=layout)
    assert path == output / "figures" / f"columns-source-columns.{fmt.lower()}"
    assert path.stat().st_size > 1000
    assert plt.get_fignums() == []
    if fmt == "HTML":
        html = path.read_text(encoding="utf-8")
        assert "Observations only" in html and "HoverTool" in html
        if "empty" in names:
            assert "No valid readings in this period" in html


def test_static_axis_layout_and_close_on_failure(data, output, monkeypatch):
    from matplotlib.figure import Figure

    def save(fig, *args, **kwargs):
        axes = fig.axes
        assert len(axes) == 4 and not axes[3].get_visible()
        assert axes[1].get_xlabel() == axes[2].get_xlabel() == "Date"
        assert axes[0].get_xlabel() == ""
        assert axes[0].get_yscale() == "linear"
        assert "Observations only" in fig.texts[-1].get_text()
        fig.canvas.draw()
        box = fig.texts[-1].get_window_extent(fig.canvas.get_renderer())
        assert box.x0 >= 0 and box.x1 <= fig.bbox.width
        assert box.y0 >= 0 and box.y1 < min(ax.bbox.y0 for ax in axes[:3])
        raise OSError("export failure")

    monkeypatch.setattr(Figure, "savefig", save)
    with pytest.raises(PlotError, match="export failure"):
        plot_columns(data, ["Avg_SO2", "empty", "Avg_H2S"], output_dir=output)
    assert plt.get_fignums() == []


@pytest.mark.parametrize("args,match", [
    ([], "COLUMN_NAMES"), (["A"], "--source"),
])
def test_cli_required(args, match, cli):
    result = CliRunner().invoke(cli, ["plot", "columns", *args])
    assert result.exit_code == 2 and match in result.output


def test_cli_required_type_and_bad_names(data, output, cli):
    source = output / "source.csv"
    data.df.to_csv(source)
    args = ["plot", "columns", "Avg_SO2", "--source", str(source)]
    assert "--dataset-type" in CliRunner().invoke(cli, args).output
    for names in [["Avg_SO2", "empty"], ["Avg_SO2,empty"], ["Avg_SO2, empty", "Avg_SO2"]]:
        result = CliRunner().invoke(cli, ["plot", "columns", *names,
            "--source", str(source), "--dataset-type", "6h", "--json",
            "--one-column", "--output-dir", str(output)])
        assert result.exit_code == 0, result.output
        assert set(json.loads(result.output)) == {"figure"}
    result = CliRunner().invoke(cli, [*args, "--dataset-type", "6h",
        "--start-date", "bad", "--output-dir", str(output)])
    assert result.exit_code == 1 and "Invalid date range" in result.output


def test_python_options(data, output):
    with pytest.raises(ValueError, match="required"):
        plot_columns("unused.csv", "A")
    with pytest.raises(DatasetError, match="conflicts"):
        plot_columns(data, "Avg_SO2", "wx")
    for layout in [True, 0, 3, 1.0]:
        with pytest.raises(ValueError, match="layout_columns"):
            plot_columns(data, "Avg_SO2", layout_columns=layout)
    with pytest.raises(ValueError, match="save_as"):
        plot_columns(data, "Avg_SO2", save_as="SVG")


def test_single_selection_automatically_uses_one_column(data, output, monkeypatch):
    captured = []
    monkeypatch.setattr(MODULE, "_render_static",
                        lambda frame, path, columns, text: captured.append(columns))
    plot_columns(data, "Avg_CO2_lowpass", output_dir=output)
    plot_columns(data, "Avg_CO2_lowpass", output_dir=output, layout_columns=1)
    assert captured == [1, 1]


def test_lazy_import():
    result = subprocess.run([sys.executable, "-c",
        "import multigas.plot, sys; print('matplotlib' in sys.modules)"],
        check=True, capture_output=True, text=True)
    assert result.stdout.strip() == "False"
