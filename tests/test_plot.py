from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from multigas.core.types import DatasetType
from multigas.data.multigas_data import MultiGasData
from multigas.plot import plot_completeness

TESTS_DIR = Path(__file__).parent


@pytest.fixture
def output_files():
    """Track files written into ``tests/`` and remove them afterwards."""
    created: list[Path] = []
    yield created
    for path in created:
        path.unlink(missing_ok=True)


def _write_completeness_csv(path: Path, rows: int = 5) -> Path:
    pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=rows).strftime("%Y-%m-%d"),
            "total_data": [1440] * rows,
            "completeness": [100.0] * rows,
        }
    ).to_csv(path, index=False)
    return path


def test_plot_completeness_saves_png_and_closes_figure(output_files) -> None:
    csv_path = TESTS_DIR / "plot-completeness-ok.csv"
    png_path = csv_path.with_suffix(".png")
    output_files.extend([csv_path, png_path])
    _write_completeness_csv(csv_path)
    plt.close("all")

    result = plot_completeness(csv_path, title="site_a (one-minute)")

    assert result == png_path
    assert png_path.exists()
    assert plt.get_fignums() == []


def test_plot_completeness_returns_none_on_failure(output_files) -> None:
    csv_path = TESTS_DIR / "plot-completeness-empty.csv"
    output_files.extend([csv_path, csv_path.with_suffix(".png")])
    _write_completeness_csv(csv_path, rows=0)

    assert plot_completeness(csv_path) is None
    assert not csv_path.with_suffix(".png").exists()


def test_extract_daily_survives_plot_failure(monkeypatch, output_files) -> None:
    plot_module = importlib.import_module("multigas.plot.plot_completeness")

    def _boom(*args, **kwargs):
        raise RuntimeError("plot failed")

    monkeypatch.setattr(plot_module, "PlotAvailability", _boom)

    index = pd.date_range("2024-01-01", periods=3, freq="1min", name="TIMESTAMP")
    df = pd.DataFrame({"TIMESTAMP": index, "CO2": [1.0, 2.0, 3.0]})
    ds = MultiGasData(df, DatasetType.ONE_MINUTE, TESTS_DIR / "plot_extract.dat")

    output_dir = TESTS_DIR / "plot_extract_output"
    try:
        result = ds.extract_daily(output_dir)
        assert isinstance(result, pd.DataFrame)
        assert result["total_data"].tolist() == [3]
    finally:
        shutil.rmtree(output_dir, ignore_errors=True)


def test_import_multigas_does_not_load_matplotlib() -> None:
    code = "import sys, multigas; print('matplotlib' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"
