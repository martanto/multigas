"""Thin versioned routes; all analysis and storage logic lives in utilities."""

import hashlib
from uuid import uuid4

from fastapi import Request, APIRouter, HTTPException
from fastapi.responses import Response, FileResponse, StreamingResponse

from multigas.api.schemas import SavedView, ExportSpec, ImportSpec, AnalysisSpec
from multigas.utils.analysis import panel_metadata
from multigas.core.exceptions import MultigasException
from multigas.utils.app_query import DatasetQuery
from multigas.utils.app_store import utc_now
from multigas.utils.app_export import export_artifact
from multigas.utils.app_ingest import ingest, csv_header
from multigas.utils.app_series import stream_series


router = APIRouter()


@router.get("/health")
def health():
    return {"status": "ok", "timezone": "UTC", "panels": panel_metadata()}


@router.get("/stations")
def stations(request: Request):
    return sorted({d["station"] for d in request.app.state.store.list("datasets")})


@router.get("/datasets")
def datasets(request: Request):
    return request.app.state.store.list("datasets")


@router.get("/datasets/{identifier}/days")
def days(identifier: str, request: Request):
    return request.app.state.store.get("datasets", identifier)["manifest"]


@router.post("/imports/preview")
async def preview(request: Request, filename: str = "upload.csv"):
    """Stream the raw text body without multipart's pre-buffering of large files."""
    from pathlib import PureWindowsPath

    name = PureWindowsPath(filename).name
    if not name.lower().endswith((".csv", ".dat", ".txt")):
        raise HTTPException(415, "Upload CSV or TOA5 text (.csv, .dat, .txt)")
    store = request.app.state.store
    store.cleanup_staged()
    identifier = uuid4().hex
    path = store.root / "staged" / identifier
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open("wb") as file:
            async for chunk in request.stream():
                size += len(chunk)
                if size > request.app.state.upload_limit:
                    raise HTTPException(413, "Upload exceeds the configured size limit")
                if b"\x00" in chunk:
                    raise HTTPException(415, "Binary files are not accepted")
                digest.update(chunk)
                file.write(chunk)
        if not size:
            raise ValueError("Choose a nonempty CSV or TOA5 file")
        result = {
            "id": identifier,
            "name": name,
            "size": size,
            "created": utc_now(),
            "checksum": digest.hexdigest(),
            "preview": csv_header(path),
        }
        return store.put("staged", result)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@router.post("/imports/{identifier}/confirm")
def confirm(identifier: str, spec: ImportSpec, request: Request):
    store = request.app.state.store
    staged = store.get("staged", identifier)
    job_spec = {"staged": identifier, "import": spec.model_dump()}
    return store.submit(
        "import",
        job_spec,
        lambda job, work: ingest(store, staged, spec.model_dump(), job, work),
    )


@router.get("/jobs")
def jobs(request: Request):
    return request.app.state.store.list("jobs")


@router.get("/jobs/{identifier}")
def job(identifier: str, request: Request):
    return request.app.state.store.get("jobs", identifier)


@router.post("/jobs/{identifier}/cancel")
def cancel(identifier: str, request: Request):
    store = request.app.state.store
    with store.lock:
        item = store.get("jobs", identifier)
        if item["status"] in {"queued", "running"}:
            item["status"] = "cancelling"
            store.put("jobs", item)
    return item


@router.post("/jobs/{identifier}/retry")
def retry(identifier: str, request: Request):
    store = request.app.state.store
    item = store.get("jobs", identifier)
    if item["status"] not in {"cancelled", "failed", "interrupted"}:
        raise ValueError("Only failed, cancelled, or interrupted jobs can be retried")
    if item["kind"] == "import":
        return confirm(
            item["spec"]["staged"], ImportSpec(**item["spec"]["import"]), request
        )
    return exports(ExportSpec(**item["spec"]), request)


@router.post("/statistics")
def statistics(spec: AnalysisSpec, request: Request):
    query = DatasetQuery(request.app.state.store, spec)
    try:
        return query.statistics()
    finally:
        query.close()


@router.post("/rows")
def rows(spec: AnalysisSpec, request: Request, offset: int = 0, limit: int = 50):
    if offset < 0 or not 1 <= limit <= 500:
        raise ValueError("Use a nonnegative offset and a page size between 1 and 500")
    query = DatasetQuery(request.app.state.store, spec)
    try:
        return {"rows": query.rows(offset, limit), "total": query.count()}
    finally:
        query.close()


@router.post("/series")
def series(spec: AnalysisSpec, request: Request, offset: int = 0, limit: int = 8000):
    import pyarrow as pa
    import pyarrow.ipc as ipc

    query = DatasetQuery(request.app.state.store, spec)
    try:
        data = query.series(offset=offset, limit=limit)
        records = [
            {
                "channel": s["channel"],
                "timestamp": p["timestamp"],
                "value": p["value"],
                "source_count": s["source_count"],
                "rendered_count": s["rendered_count"],
            }
            for s in data
            for p in s["points"]
        ]
        schema = pa.schema(
            [
                ("channel", pa.string()),
                ("timestamp", pa.string()),
                ("value", pa.float64()),
                ("source_count", pa.int64()),
                ("rendered_count", pa.int64()),
            ]
        )
        table = pa.Table.from_pylist(records, schema=schema)
        sink = pa.BufferOutputStream()
        with ipc.new_stream(sink, table.schema) as writer:
            writer.write_table(table)
        return Response(
            sink.getvalue().to_pybytes(),
            media_type="application/vnd.apache.arrow.stream",
        )
    finally:
        query.close()


@router.post("/series/stream")
def all_series(spec: AnalysisSpec, request: Request):
    """Stream every observation, using bounded Arrow batches rather than sampling."""
    query = DatasetQuery(request.app.state.store, spec)
    try:
        count = query.count()
    except Exception:
        query.close()
        raise
    return StreamingResponse(
        stream_series(query),
        media_type="application/vnd.apache.arrow.stream",
        headers={"X-Source-Count": str(count), "X-Plot-Resolution": "full"},
    )


@router.get("/views")
def views(request: Request):
    store = request.app.state.store
    result = store.list("views")
    for view in result:
        try:
            query = DatasetQuery(store, AnalysisSpec(**view["analysis"]))
            query.close()
            view["unavailable"] = None
        except (KeyError, ValueError, MultigasException) as exc:
            view["unavailable"] = str(exc)
    return result


@router.post("/views")
def save_view(spec: SavedView, request: Request):
    query = DatasetQuery(request.app.state.store, spec.analysis)
    query.close()
    if set(spec.arrangement) - {p["id"] for p in panel_metadata()}:
        raise ValueError("Unknown panel arrangement")
    return request.app.state.store.put(
        "views", {"id": uuid4().hex, **spec.model_dump()}
    )


@router.delete("/views/{identifier}")
def delete_view(identifier: str, request: Request):
    store = request.app.state.store
    store.get("views", identifier)
    store.delete("views", identifier)
    return {"deleted": identifier}


@router.post("/exports")
def exports(spec: ExportSpec, request: Request):
    store = request.app.state.store
    query = DatasetQuery(store, spec)
    query.close()
    return store.submit(
        "export",
        spec.model_dump(),
        lambda job, work: export_artifact(store, spec, job, work),
    )


@router.get("/downloads/{identifier}")
def download(identifier: str, request: Request, manifest: bool = False):
    store = request.app.state.store
    artifact = store.get("artifacts", identifier)
    filename = "manifest.json" if manifest else artifact["filename"]
    return FileResponse(
        store.root / "artifacts" / artifact["id"] / filename, filename=filename
    )
