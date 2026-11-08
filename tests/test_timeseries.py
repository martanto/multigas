"""Scientific figure contracts and deterministic rendered regression fixture."""

from pathlib import Path

import matplotlib
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
import pytest

from multigas.plot import plot_timeseries
from multigas.core.exceptions import PlotError
from multigas.utils.analysis import PANELS

HERE = Path(__file__).parent


def fixture_frame():
    index = pd.date_range(
        "2026-01-01", periods=2880, freq="min", name="TIMESTAMP", tz="UTC"
    )
    phase = np.arange(len(index))
    co2 = 430 + 50 * np.sin(phase / 31) + 10 * np.sin(phase / 7)
    so2 = 2 + 0.8 * np.sin(phase / 71)
    h2s = 0.5 + 0.2 * np.cos(phase / 39)
    frame = pd.DataFrame(
        {
            "Avg_CO2_lowpass": co2,
            "Avg_SO2": so2,
            "Avg_H2S": h2s,
            "H2O": 1.5 + 0.4 * np.sin(phase / 57),
            "Avg_CO2_S_tot_ratio": co2 / (so2 + h2s),
            "Avg_H2S_SO2_ratio": h2s / so2,
            "calculated_CO2_H2S": co2 / h2s,
            "Avg_CO2_SO2_ratio": co2 / so2,
            "Avg_H2O_CO2_ratio": 40 + 8 * np.sin(phase / 83),
            "Avg_SO2_proportion": so2 / (so2 + h2s),
            "Avg_H2S_proportion": h2s / (so2 + h2s),
        },
        index=index,
    )
    frame.iloc[100:120, :] = np.nan
    frame.iloc[1440, frame.columns.get_loc("Avg_CO2_lowpass")] = 1500
    units = {
        "Avg_CO2_lowpass": "ppm",
        "Avg_SO2": "ppm",
        "Avg_H2S": "ppm",
        "H2O": "%",
        "Avg_SO2_proportion": "fraction",
        "Avg_H2S_proportion": "fraction",
    }
    return frame, units


def test_summary_layout_and_styles(monkeypatch):
    frame, units = fixture_frame()
    observed = {}
    original = Figure.savefig
    before = dict(matplotlib.rcParams)

    def capture(figure, *args, **kwargs):
        observed["labels"] = [ax.get_ylabel() for ax in figure.axes]
        observed["limits"] = [ax.get_xlim() for ax in figure.axes]
        observed["ylimits"] = [ax.get_ylim() for ax in figure.axes]
        observed["legend"] = figure.axes[-1].get_legend()
        observed["rasterized"] = all(
            c.get_rasterized() for ax in figure.axes for c in ax.collections
        )
        return original(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    output = HERE / "summary-layout.png"
    try:
        plot_timeseries(frame, output, units=units, dpi=60)
        assert [label.split("\n")[0] for label in observed["labels"]] == [
            p.label for p in PANELS
        ]
        assert len(set(observed["limits"])) == 1
        assert len(set(observed["ylimits"])) > 5
        assert observed["ylimits"][5][1] > 1500  # spike retained, never clipped
        assert observed["legend"] is not None
        assert observed["rasterized"]
        assert dict(matplotlib.rcParams) == before
        assert plt.get_fignums() == []
    finally:
        output.unlink(missing_ok=True)


@pytest.mark.parametrize("format", ["png", "pdf", "svg"])
def test_export_formats_and_unavailable_panels(format, monkeypatch):
    frame, units = fixture_frame()
    frame = frame.drop(columns=["Avg_H2O_CO2_ratio"])
    captured = {}
    original = Figure.savefig

    def capture(figure, *args, **kwargs):
        captured["annotation"] = [t.get_text() for t in figure.axes[4].texts]
        captured["limits"] = figure.axes[5].get_ylim()
        return original(figure, *args, **kwargs)

    monkeypatch.setattr(Figure, "savefig", capture)
    output = HERE / f"summary-format.{format}"
    try:
        assert (
            plot_timeseries(
                frame, output, units=units, dpi=60, y_limits={"co2": (0, 2000)}
            )
            == output
        )
        assert output.stat().st_size > 1000
        assert captured["annotation"] == ["column unavailable"]
        assert captured["limits"] == (0, 2000)
    finally:
        output.unlink(missing_ok=True)


def test_failure_cleanup_and_rejection(monkeypatch):
    frame, units = fixture_frame()
    before = dict(matplotlib.rcParams)
    monkeypatch.setattr(
        Figure, "savefig", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full"))
    )
    with pytest.raises(PlotError, match="disk full"):
        plot_timeseries(frame, HERE / "failed.png", units=units)
    assert plt.get_fignums() == []
    assert dict(matplotlib.rcParams) == before
    with pytest.raises(PlotError, match="usable"):
        plot_timeseries(frame.iloc[:0], HERE / "failed.png")
    assert not (HERE / "failed.png").exists()


def test_default_summary_image_regression():
    frame, units = fixture_frame()
    output = HERE / "summary-actual.png"
    try:
        plot_timeseries(frame, output, units=units)
        reference = mpimg.imread(HERE / "summary-reference.png")
        actual = mpimg.imread(output)
        assert actual.shape == reference.shape == (4800, 3000, 4)
        assert np.abs(actual.astype(float) - reference.astype(float)).mean() < 0.015
    finally:
        output.unlink(missing_ok=True)


def test_every_finite_observation_is_scattered(monkeypatch):
    frame = pd.DataFrame(
        {"Avg_SO2": np.arange(20001, dtype=float)},
        index=pd.date_range("2026-01-01", periods=20001, freq="2s"),
    )
    counts = []

    def inspect(figure, *args, **kwargs):
        assert not figure.axes[0].lines
        counts.append(len(figure.axes[0].collections[0].get_offsets()))

    monkeypatch.setattr(Figure, "savefig", inspect)
    plot_timeseries(frame, HERE / "all-points.png", panels=["so2"], dpi=60)
    assert counts == [20001]


if __name__ == "__main__":
    frame, units = fixture_frame()
    plot_timeseries(frame, HERE / "summary-reference.png", units=units)
