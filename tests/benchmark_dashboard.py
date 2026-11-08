"""Opt-in generated GB-scale import/figure benchmark; all artifacts stay here.

Run: uv run --extra api tests/benchmark_dashboard.py
"""

import hashlib
import json
import shutil
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import psutil

from multigas.api.schemas import AnalysisSpec, ExportSpec
from multigas.utils.app_export import export_artifact
from multigas.utils.app_ingest import csv_header, ingest
from multigas.utils.app_query import DatasetQuery
from multigas.utils.app_series import stream_series
from multigas.utils.app_store import AppStore, utc_now

HERE = Path(__file__).parent


def main():
    root = HERE / "benchmark-storage"
    store = AppStore(root)
    source = root / "staged" / "benchmark"
    columns = ["Avg_CO2_lowpass", "Avg_SO2", "Avg_H2S", "H2O"] + [
        f"channel_{i}" for i in range(28)
    ]
    if not source.exists():
        origin = datetime(2026, 1, 1)
        with source.open("w", newline="", encoding="utf-8") as file:
            file.write("TIMESTAMP,RECORD," + ",".join(columns) + "\n")
            for block in range(120):
                text = []
                for i in range(block * 10000, (block + 1) * 10000):
                    value = f"{1 + i % 1000}.123456789012345678901234"
                    text.append(
                        f"{(origin + timedelta(seconds=i)).isoformat()},{i},"
                        + ",".join([value] * 32)
                    )
                file.write("\n".join(text) + "\n")
    print(f"Generated {source.stat().st_size:,} bytes", flush=True)
    with source.open("rb") as file:
        checksum = hashlib.file_digest(file, "sha256").hexdigest()
    staged = {
        "id": "benchmark",
        "name": "benchmark.csv",
        "created": utc_now(),
        "checksum": checksum,
        "preview": csv_header(source),
    }
    store.put("staged", staged)
    process = psutil.Process()
    peak = [0]
    stop = threading.Event()

    def sample():
        while not stop.wait(0.1):
            peak[0] = max(peak[0], process.memory_info().rss)

    thread = threading.Thread(target=sample, daemon=True)
    thread.start()
    start = time.perf_counter()
    spec = {
        "station": "Generated GB benchmark",
        "timestamp": "TIMESTAMP",
        "mode": "1s",
        "units": {c: "ppm" for c in columns},
        "normalize": True,
    }
    job = store.submit(
        "import",
        {"staged": "benchmark", "import": spec},
        lambda job, work: ingest(store, staged, spec, job, work),
    )
    while store.get("jobs", job["id"])["status"] in {"queued", "running"}:
        time.sleep(0.2)
    result = store.get("jobs", job["id"])
    if result["status"] != "complete":
        raise RuntimeError(result)
    import_seconds = time.perf_counter() - start
    identifier = result["result"]["dataset"]
    query = DatasetQuery(store, AnalysisSpec(dataset=identifier))
    start = time.perf_counter()
    streamed_bytes = sum(len(chunk) for chunk in stream_series(query))
    series_seconds = time.perf_counter() - start
    export_spec = ExportSpec(
        dataset=identifier, kind="figure", ratio_source="calculated", dpi=100
    )
    start = time.perf_counter()
    job = store.submit(
        "export",
        export_spec.model_dump(),
        lambda job, work: export_artifact(store, export_spec, job, work),
    )
    # Check concurrent query responsiveness while figure work runs.
    health_samples = []
    while store.get("jobs", job["id"])["status"] in {"queued", "running"}:
        began = time.perf_counter()
        store.list("datasets")
        health_samples.append(time.perf_counter() - began)
        time.sleep(0.1)
    result = store.get("jobs", job["id"])
    if result["status"] != "complete":
        raise RuntimeError(result)
    export_seconds = time.perf_counter() - start
    stop.set()
    thread.join()
    report = {
        "generated_bytes": source.stat().st_size,
        "records": 1200000,
        "channels": 32,
        "import_seconds": round(import_seconds, 2),
        "series_seconds": round(series_seconds, 2),
        "figure_seconds": round(export_seconds, 2),
        "peak_rss_mib": round(peak[0] / 1024**2, 1),
        "max_concurrent_metadata_seconds": round(max(health_samples, default=0), 4),
        "series_stream_bytes": streamed_bytes,
        "plot_resolution": "full",
        "plot_kind": "scatter",
        "downsampling": False,
        "duckdb_memory_limit": "512MB",
        "batch_rows": 50000,
    }
    (HERE / "benchmark-results.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)
    store.close()
    shutil.rmtree(root)


if __name__ == "__main__":
    main()
