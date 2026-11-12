"""Whole-canvas dimensions across public plotting APIs and CLI commands."""

import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest
from PIL import Image
from click.testing import CliRunner

from multigas.core.exceptions import PlotError
from multigas.core.types import DatasetType
from multigas.data.multigas_data import MultiGasData
from multigas.plot import Plot, plot_columns
from multigas.plot.dimensions import validate_dimension

HERE = Path(__file__).parent


@pytest.fixture
def output():
    root = HERE / "dimension-output"
    root.mkdir(exist_ok=True)
    yield root
    shutil.rmtree(root)


@pytest.fixture
def data():
    from multigas.plot.six_hours import REQUIRED_COLUMNS

    index = pd.date_range("2025-01-01", periods=20, freq="6h", name="TIMESTAMP")
    frame = pd.DataFrame({name: range(1, 21) for name in REQUIRED_COLUMNS}, index=index)
    return MultiGasData(frame, DatasetType.SIX_HOURS, HERE / "dimension-source.csv")


@pytest.mark.parametrize("value", [True, False, 0, -1, float("nan"), float("inf"),
                                    -float("inf"), "200", 1j, 10**1000])
@pytest.mark.parametrize("name", ["width", "height"])
def test_invalid_dimensions(data, value, name):
    with pytest.raises(ValueError, match=name):
        validate_dimension(value, name)
    with pytest.raises(ValueError, match=name):
        Plot(data, **{name: value})
    with pytest.raises(ValueError, match=name):
        plot_columns(data, ["Avg_SO2"], **{name: value})


def _assert_png(path, width, height, dpi):
    with Image.open(path) as image:
        assert image.width == pytest.approx(width / 25.4 * dpi, abs=1)
        assert image.height == pytest.approx(height / 25.4 * dpi, abs=1)


@pytest.mark.parametrize("columns,width,height", [(2, 300, 220), (1, 200, 330),
                                                   (2, 300, None), (1, None, 330)])
def test_six_hour_png_dimensions(data, output, columns, width, height):
    before = plt.get_fignums()
    paths = Plot(data, output_dir=output, columns=columns,
                 width=width, height=height).plot_all()
    for path in paths.values():
        _assert_png(path, width or 280, height or (380 if columns == 1 else 190), 300)
    assert plt.get_fignums() == before


@pytest.mark.parametrize("count,columns,width,height", [
    (1, 2, 200, 150), (3, 2, 240, 190), (3, 1, 200, 240),
    (1, 1, 200, None), (2, 2, None, 150), (1, 2, None, None),
])
def test_selected_png_dimensions(data, output, count, columns, width, height):
    path = plot_columns(data, list(data.df)[:count], output_dir=output,
                        layout_columns=columns, width=width, height=height)
    with Image.open(path) as image:
        assert image.width == pytest.approx((width or 280) / 25.4 * 300, abs=1)
        if height is not None:
            assert image.height == pytest.approx(height / 25.4 * 300, abs=1)
    assert plt.get_fignums() == []


@pytest.mark.parametrize("standard", [True, False])
def test_pdf_page_dimensions(data, output, standard):
    if standard:
        paths = Plot(data, output_dir=output, save_as="PDF", width=300, height=220
                     ).plot_all().values()
    else:
        paths = [plot_columns(data, ["Avg_SO2"], output_dir=output, save_as="PDF",
                              width=300, height=220)]
    for path in paths:
        match = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)",
                          path.read_bytes())
        assert match is not None
        assert float(match[1]) == pytest.approx(300 / 25.4 * 72)
        assert float(match[2]) == pytest.approx(220 / 25.4 * 72)


@pytest.mark.parametrize("standard,columns", [(True, 2), (True, 1), (False, 2), (False, 1)])
@pytest.mark.parametrize("width,height", [(300, 500), (300, None), (None, 500)])
def test_html_outer_dimensions(data, output, standard, columns, width, height):
    if standard:
        paths = Plot(data, output_dir=output, save_as="HTML", columns=columns,
                     width=width, height=height).plot_all().values()
    else:
        paths = [plot_columns(data, list(data.df)[:3], output_dir=output, save_as="HTML",
                              layout_columns=columns, width=width, height=height)]
    for path in paths:
        html = path.read_text(encoding="utf-8")
        payload = re.search(r'<script type="application/json"[^>]*>(.*?)</script>',
                            html, re.S)
        doc = next(iter(json.loads(payload[1]).values()))
        attrs = doc["roots"][0]["attributes"]
        if width is not None:
            assert attrs["width"] == round(width * 96 / 25.4)
        if height is not None:
            assert attrs["height"] == round(height * 96 / 25.4)
        assert attrs["sizing_mode"] == "fixed"


@pytest.mark.parametrize("format", ["PNG", "HTML"])
def test_undersized_layouts(data, output, format):
    with pytest.raises(PlotError, match="too small|cannot accommodate"):
        Plot(data, output_dir=output, save_as=format, width=10, height=10).plot_all()
    with pytest.raises(PlotError, match="too small|cannot accommodate"):
        plot_columns(data, ["Avg_SO2"], output_dir=output,
                     save_as=format, width=10, height=10)
    assert plt.get_fignums() == []


@pytest.mark.parametrize("standard", [True, False])
def test_cli_forwarding_and_option_errors(data, output, monkeypatch, standard):
    from multigas.cli.main import cli

    module = importlib.import_module("multigas.cli.commands.plot")
    path = output / "source.csv"
    path.touch()
    captured = {}
    if standard:
        class FakePlot:
            def __init__(self, *args, **kwargs):
                captured.update(kwargs)

            def plot_all(self):
                return {"full_period": path, "trailing_three_months": path}
        monkeypatch.setattr(module, "Plot", FakePlot)
        args = ["plot", str(path), "--dataset-type", "6h"]
    else:
        def fake_columns(*args, **kwargs):
            captured.update(kwargs)
            return path
        monkeypatch.setattr(importlib.import_module("multigas.plot.columns"),
                            "plot_columns", fake_columns)
        args = ["plot", "columns", "Avg_SO2", "--source", str(path),
                "--dataset-type", "6h"]
    result = CliRunner().invoke(cli, [*args, "--width", "300", "--height", "220", "--json"])
    assert result.exit_code == 0, result.output
    assert captured["width"] == 300 and captured["height"] == 220
    json.loads(result.output)
    for option in ["--width", "--height"]:
        for value in ["0", "-2", "nan", "inf"]:
            result = CliRunner().invoke(cli, [*args, option, value])
            assert result.exit_code == 2
            assert option in result.output


def test_dimensions_import_is_lazy():
    result = subprocess.run([sys.executable, "-c",
        "import sys; from multigas.plot.dimensions import validate_dimension; "
        "from multigas.plot import Plot, plot_columns, plot_completeness; "
        "assert not any(n in sys.modules for n in ('matplotlib', 'seaborn', 'bokeh'))"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_html_panels_and_text_fit_container():
    from bokeh.plotting import figure
    from multigas.plot.dimensions import size_html

    plots = [figure(width=550, height=220) for _ in range(3)]
    layout = size_html(plots, "Title", "Caption " * 60, 2, 240, 190, 1130, 220)
    heading, grid, caption = layout.children
    assert layout.width == round(240 * 96 / 25.4)
    assert layout.height == round(190 * 96 / 25.4)
    assert grid.width == layout.width
    assert heading.height + grid.height + caption.height <= layout.height
    assert all(plot.width * 2 <= layout.width for plot in plots)
    assert all(plot.height * 2 < grid.height for plot in plots)


def test_custom_export_failure_closes_figures(data, output, monkeypatch):
    from matplotlib.figure import Figure

    def fail(*args, **kwargs):
        raise OSError("Export failed")

    monkeypatch.setattr(Figure, "savefig", fail)
    for standard in [True, False]:
        with pytest.raises(PlotError, match="Export failed"):
            if standard:
                Plot(data, output_dir=output, width=300, height=220).plot_all()
            else:
                plot_columns(data, ["Avg_SO2"], output_dir=output, width=200, height=150)
        assert plt.get_fignums() == []
