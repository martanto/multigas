"""End-to-end local API and bounded scientific pipeline contracts."""

import io
import json
import shutil
import time
from pathlib import Path
from zipfile import ZipFile

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("duckdb")
pytest.importorskip("pyarrow")
from fastapi.testclient import TestClient

from multigas.api.app import create_app
from multigas.utils.analysis import prepare_panels, daily_manifest
from multigas.utils.app_ingest import ingest
from multigas.utils.app_query import DatasetQuery
from multigas.api.schemas import AnalysisSpec

ROOT = Path(__file__).parent / "dashboard-output"


@pytest.fixture
def client():
    shutil.rmtree(ROOT, ignore_errors=True)
    with TestClient(create_app(ROOT)) as client:
        yield client
    shutil.rmtree(ROOT, ignore_errors=True)


def wait_job(client, identifier):
    for _ in range(1000):
        result = client.get(f"/api/v1/jobs/{identifier}").json()
        if result["status"] not in {"queued", "running", "cancelling"}:
            return result
        time.sleep(0.02)
    pytest.fail("Job did not finish")


def upload(client, data=None):
    if data is None:
        data = "TIMESTAMP,RECORD,Avg_CO2_lowpass,Avg_SO2,Avg_H2S,H2O\n" + "\n".join(
            f"2026-01-01T00:{i:02}:00Z,{i},{400 + i},{2 + i / 10},1,2"
            for i in range(60)
        )
    response = client.post("/api/v1/imports/preview?filename=station.csv", content=data)
    assert response.status_code == 200, response.text
    return response.json()


def import_dataset(client, data=None, **overrides):
    staged = upload(client, data)
    spec = {
        "station": "Lokon",
        "mode": "1min",
        "units": {
            "Avg_CO2_lowpass": "ppm",
            "Avg_SO2": "ppm",
            "Avg_H2S": "ppm",
            "H2O": "%",
        },
        **overrides,
    }
    response = client.post(f"/api/v1/imports/{staged['id']}/confirm", json=spec)
    assert response.status_code == 200, response.text
    result = wait_job(client, response.json()["id"])
    assert result["status"] == "complete", result
    return result["result"]["dataset"]


def test_api_workflow_and_exports(client):
    identifier = import_dataset(client)
    spec = {"dataset": identifier, "ratio_source": "calculated"}
    stats = client.post("/api/v1/statistics", json=spec)
    assert stats.status_code == 200, stats.text
    assert stats.json()["filtered_records"] == 60
    assert stats.json()["channels"]["Avg_CO2_lowpass"]["mean"] == 429.5
    response = client.post("/api/v1/series", json=spec)
    assert response.status_code == 200, response.text
    import pyarrow.ipc as ipc

    table = ipc.open_stream(response.content).read_all()
    assert table.num_rows > 0
    rows = client.post("/api/v1/rows?offset=0&limit=2", json=spec).json()
    assert len(rows["rows"]) == 2
    view = client.post("/api/v1/views", json={"name": "Morning", "analysis": spec})
    assert view.status_code == 200, view.text
    assert client.get("/api/v1/views").json()[0]["unavailable"] is None
    filtered = {
        **spec,
        "filters": [{"column": "Avg_SO2", "comparator": ">", "value": 5}],
    }
    assert (
        client.post("/api/v1/statistics", json=filtered).json()["filtered_records"] < 60
    )
    assert client.get(f"/api/v1/datasets/{identifier}/days").json()[0]["records"] == 60
    for kind, extra in [
        ("csv", {}),
        ("zip", {"days": ["2026-01-01"]}),
        ("figure", {"dpi": 60}),
    ]:
        response = client.post("/api/v1/exports", json={**spec, "kind": kind, **extra})
        assert response.status_code == 200, response.text
        result = wait_job(client, response.json()["id"])
        assert result["status"] == "complete", result
        artifact = result["result"]["artifact"]
        content = client.get(f"/api/v1/downloads/{artifact}")
        assert content.status_code == 200
        manifest = client.get(f"/api/v1/downloads/{artifact}?manifest=true").json()
        assert manifest["dataset"]["checksum"]
        if kind == "csv":
            assert len(pd.read_csv(io.BytesIO(content.content))) == 60
        elif kind == "zip":
            with ZipFile(io.BytesIO(content.content)) as archive:
                assert set(archive.namelist()) == {"2026-01-01.csv", "manifest.json"}
        else:
            assert content.content.startswith(b"\x89PNG")
            assert manifest["rendering"]["downsampling"] is False
            assert manifest["rendering"]["source_records"] == 60


def test_full_validation_and_safe_requests(client):
    staged = upload(client, "TIMESTAMP,RECORD\n" + "2026-01-01,1\n" * 12 + "broken,2\n")
    result = client.post(
        f"/api/v1/imports/{staged['id']}/confirm", json={"station": "A"}
    )
    assert wait_job(client, result.json()["id"])["status"] == "failed"
    assert client.get("/api/v1/datasets").json() == []
    assert (
        client.post(
            "/api/v1/imports/preview?filename=a.pkl", content=b"test"
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/v1/imports/preview?filename=a.csv", content=b"x\x00y"
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/v1/views", headers={"origin": "https://example.com"}, json={}
        ).status_code
        == 403
    )
    assert client.get("/api/v1/datasets/missing/days").status_code == 404


def test_midnight_global_normalization(client, monkeypatch):
    import multigas.api.routes as routes

    original = routes.ingest
    monkeypatch.setattr(
        routes, "ingest", lambda *a, **kw: original(*a, **kw, batch_size=2)
    )
    data = "TIMESTAMP,RECORD,Avg_SO2\n2026-01-01T23:59:00Z,1,1\n2026-01-02T00:00:00Z,2,2\n2026-01-02T00:00:00Z,3,9\n2026-01-02T00:03:00Z,4,4\n2026-01-02T00:04:00Z,5,5\n2026-01-04T00:00:00Z,6,6\n2026-01-04T00:01:00Z,7,7"
    identifier = import_dataset(client, data, units={"Avg_SO2": "ppm"})
    rows = client.post("/api/v1/rows", json={"dataset": identifier}).json()["rows"]
    assert [r["Avg_SO2"] for r in rows] == [1, 9, 5, 7]
    days = client.get(f"/api/v1/datasets/{identifier}/days").json()
    assert days[2]["records"] == 0


def test_units_and_nullable_coverage():
    df = pd.DataFrame(
        {"H2O": [2.0], "Avg_CO2_lowpass": [400.0]},
        index=pd.date_range("2026-01-01", periods=1),
    )
    result, provenance = prepare_panels(
        df, {"H2O": "%", "Avg_CO2_lowpass": "ppm"}, "calculated", ["h2o_co2"]
    )
    assert result["Avg_H2O_CO2_ratio"].iloc[0] == 50
    assert provenance["Avg_H2O_CO2_ratio"]["source"] == "calculated"
    with pytest.raises(Exception, match="Confirm"):
        prepare_panels(df, {}, "calculated", ["h2o_co2"])
    assert daily_manifest({"2026-01-01": 2}, "wx")[0]["completeness"] is None
    assert daily_manifest({"2026-01-01": 43200}, "2s")[0]["completeness"] == 100


def test_full_resolution_series_pages(client):
    index = pd.date_range("2026-01-01", periods=16001, freq="2s")
    data = "TIMESTAMP,RECORD,SO2\n" + "\n".join(
        f"{t.isoformat()},{i},{i}" for i, t in enumerate(index)
    )
    identifier = import_dataset(client, data, mode="2s", units={"SO2": "ppmv"})
    import pyarrow.ipc as ipc

    values = []
    for offset in (0, 8000, 16000):
        response = client.post(
            f"/api/v1/series?offset={offset}&limit=8000",
            json={"dataset": identifier, "channels": ["Avg_SO2"]},
        )
        assert response.status_code == 200, response.text
        table = ipc.open_stream(response.content).read_all()
        assert table.num_rows <= 8000
        values.extend(table.column("value").to_pylist())
    assert values == list(range(16001))
    response = client.post(
        "/api/v1/series/stream", json={"dataset": identifier, "channels": ["Avg_SO2"]}
    )
    assert response.status_code == 200
    assert response.headers["x-source-count"] == "16001"
    table = ipc.open_stream(response.content).read_all()
    assert table.num_rows == 16001
    assert table.column("Avg_SO2").to_pylist() == list(range(16001))


def test_2s_source_aliases_and_onboard_proportions():
    frame = pd.DataFrame(
        {
            "CO2_lowpass": [400.0],
            "SO2": [2.0],
            "H2S": [1.0],
            "H2O": [1000.0],
            "CO2/H2S_ratio_3min": [401.0],
            "SO2/S_total_3min": [66.7],
            "H2S/S_total_3min": [33.3],
        },
        index=pd.date_range("2026-01-01", periods=1),
    )
    resolved, provenance = prepare_panels(
        frame, {"SO2/S_total_3min": "%", "H2S/S_total_3min": "%"}
    )
    assert resolved["Avg_CO2_H2S_ratio"].iloc[0] == 401
    assert provenance["Avg_CO2_H2S_ratio"]["source"] == "onboard"
    assert resolved["Avg_SO2_proportion"].iloc[0] == 66.7


def test_upload_limit_and_persistent_views(client):
    client.app.state.upload_limit = 10
    assert (
        client.post(
            "/api/v1/imports/preview?filename=a.csv",
            content="TIMESTAMP,RECORD\n2026-01-01,1",
        ).status_code
        == 413
    )
    client.app.state.upload_limit = 5 * 1024**3
    identifier = import_dataset(client)
    response = client.post(
        "/api/v1/views",
        json={"name": "Persistent", "analysis": {"dataset": identifier}},
    )
    assert response.status_code == 200
    from multigas.utils.app_store import AppStore

    another = AppStore(ROOT)
    try:
        assert another.list("views")[0]["name"] == "Persistent"
    finally:
        another.close()


def test_cancellation_restart_and_staging_cleanup(client):
    from threading import Event
    from datetime import UTC, datetime, timedelta
    from multigas.utils.app_store import AppStore

    store = client.app.state.store
    started, release, should_not_run = Event(), Event(), Event()

    def blocker(job, work):
        started.set()
        release.wait(5)
        return {}

    first = store.submit("test", {}, blocker)
    assert started.wait(5)
    queued = store.submit("test", {}, lambda job, work: should_not_run.set())
    assert (
        client.post(f"/api/v1/jobs/{queued['id']}/cancel", json={}).status_code == 200
    )
    release.set()
    assert wait_job(client, first["id"])["status"] == "complete"
    assert wait_job(client, queued["id"])["status"] == "cancelled"
    assert not should_not_run.is_set()
    assert not (ROOT / "work" / queued["id"]).exists()
    store.put(
        "jobs", {"id": "interrupted", "status": "running", "spec": {}, "kind": "test"}
    )
    store.put(
        "staged",
        {
            "id": "expired",
            "created": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        },
    )
    (ROOT / "staged" / "expired").write_text("expired", encoding="utf-8")
    restarted = AppStore(ROOT)
    try:
        assert restarted.get("jobs", "interrupted")["status"] == "interrupted"
        assert not (ROOT / "staged" / "expired").exists()
    finally:
        restarted.close()


def test_environment_settings_and_explicit_overrides(monkeypatch):
    monkeypatch.setenv("MULTIGAS_APP_DIR", str(ROOT))
    monkeypatch.setenv("MULTIGAS_UPLOAD_LIMIT_BYTES", "1234")
    with TestClient(create_app()) as configured:
        assert configured.app.state.upload_limit == 1234
        assert configured.app.state.store.root == ROOT.resolve()
    try:
        monkeypatch.setenv("MULTIGAS_UPLOAD_LIMIT_BYTES", "invalid")
        assert create_app(ROOT, upload_limit=456).state.upload_limit == 456
        with pytest.raises(ValueError, match="positive integer"):
            create_app(ROOT)
        monkeypatch.setenv("MULTIGAS_DUCKDB_MEMORY_LIMIT", "64MiB")
        from multigas.utils.app_ingest import database

        connection = database()
        try:
            assert (
                connection.execute("SELECT current_setting('memory_limit')").fetchall()[
                    0
                ][0]
                == "64.0 MiB"
            )
        finally:
            connection.close()
    finally:
        shutil.rmtree(ROOT, ignore_errors=True)


@pytest.mark.parametrize("value", ["0", "-1", "bad"])
def test_invalid_upload_environment(value, monkeypatch):
    from multigas.utils.app_config import upload_limit_bytes

    monkeypatch.setenv("MULTIGAS_UPLOAD_LIMIT_BYTES", value)
    with pytest.raises(ValueError, match="positive integer"):
        upload_limit_bytes()


def test_dotenv_preserves_inherited_environment():
    import os
    import subprocess
    import sys

    path = Path(__file__).parent / "dashboard-env-test.env"
    path.write_text("MULTIGAS_APP_DIR=file-value\nENABLE_LOG=true\n", encoding="utf-8")
    script = (
        "import dotenv.main, os; "
        f"dotenv.main.find_dotenv=lambda *a, **kw: {str(path.resolve())!r}; "
        "import multigas; "
        "assert os.environ['MULTIGAS_APP_DIR']=='process-value'; "
        "assert os.environ['ENABLE_LOG']=='false'"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "MULTIGAS_APP_DIR": "process-value",
                "ENABLE_LOG": "false",
            },
        )
        assert result.returncode == 0, result.stderr
    finally:
        path.unlink(missing_ok=True)
