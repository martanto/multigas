"""Atomic, cached data/figure exports and reproducibility manifests."""

import json
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from importlib.metadata import version

from multigas.utils.analysis import CAVEAT, PANEL_MAP
from multigas.utils.app_query import DatasetQuery, utc_value
from multigas.utils.dataframe import to_datetime_index
from multigas.utils.app_ingest import quote


def export_artifact(store, spec, job: str, work: Path) -> dict:
    """Publish full-resolution CSV, ZIP, or scatter figures with a manifest."""
    query = DatasetQuery(store, spec)
    try:
        encoded = json.dumps(
            {
                "dataset_version": query.metadata["version"],
                "software": version("multigas"),
                "rendering_revision": "full-scatter-v1",
                "spec": spec.model_dump(),
            },
            sort_keys=True,
        ).encode()
        identifier = hashlib.sha256(encoded).hexdigest()
        try:
            existing = store.get("artifacts", identifier)
            if (store.root / "artifacts" / identifier / existing["filename"]).exists():
                return {"artifact": identifier, "cached": True}
        except KeyError:
            pass
        store.progress(job, 0.1, "Preparing full-resolution analysis")
        manifest = {
            "dataset": query.metadata,
            "software": {"multigas": version("multigas")},
            "specification": spec.model_dump(),
            "timezone": "UTC",
            "provenance": query.provenance,
            "caveat": CAVEAT,
            "filtered_records": query.count(),
            "reduction": None,
        }
        if spec.kind == "figure":
            from multigas.plot.plot_timeseries import plot_timeseries

            if spec.channels:
                raise ValueError(
                    "Figure exports use selected panels; clear the channel subset"
                )
            columns = list(
                dict.fromkeys(
                    c
                    for p in spec.panels or list(PANEL_MAP)
                    for c in PANEL_MAP[p].columns
                    if c in query.columns
                )
            )
            fields = ",".join(map(quote, ["__mg_time", *columns]))
            frame = to_datetime_index(
                query.connection.execute(
                    f"SELECT {fields} FROM ({query.sql}) ORDER BY __mg_time",
                    query.params,
                ).df(),
                "__mg_time",
                utc=True,
            )
            manifest["rendering"] = {
                "kind": "scatter",
                "resolution": "full",
                "downsampling": False,
                "source_records": len(frame),
                "finite_points": {c: int(frame[c].notna().sum()) for c in columns},
            }
            units = dict(query.metadata["units"])
            for c, provenance in query.provenance.items():
                units[c] = provenance.get("unit", units.get(c, "unconfirmed"))
            filename = f"multigas-summary.{spec.format}"
            store.progress(job, 0.4, "Rendering scientific panels")
            plot_timeseries(
                frame,
                work / filename,
                panels=spec.panels or None,
                units=units,
                width=spec.width,
                height=spec.height,
                dpi=spec.dpi,
                format=spec.format,
                y_limits=spec.y_limits,
            )
        else:
            fields = [
                "__mg_time AS TIMESTAMP",
                *[quote(c) for c in spec.channels or query.columns],
            ]
            sql = f"SELECT {','.join(fields)} FROM ({query.sql})"
            if spec.kind == "csv":
                filename = "observations.csv"
                query.connection.execute(
                    f"COPY ({sql} ORDER BY TIMESTAMP) TO ? (HEADER, DELIMITER ',')",
                    [*query.params, str(work / filename)],
                )
            else:
                filename = "daily-observations.zip"
                days = spec.days or [
                    d["date"] for d in query.metadata["manifest"] if d["records"]
                ]
                manifest["exported_days"] = days
                with ZipFile(work / filename, "w", ZIP_DEFLATED) as archive:
                    for index, day in enumerate(days):
                        utc_value(day)
                        if day not in {d["date"] for d in query.metadata["manifest"]}:
                            raise ValueError(f"Date outside dataset: {day}")
                        store.progress(
                            job,
                            0.2 + 0.6 * index / max(1, len(days)),
                            f"Exporting {day}",
                        )
                        target = work / f"{day}.csv"
                        query.connection.execute(
                            f"COPY (SELECT * FROM ({sql}) WHERE CAST(TIMESTAMP AS DATE)=CAST(? AS DATE) ORDER BY TIMESTAMP) TO ? (HEADER)",
                            [*query.params, day, str(target)],
                        )
                        archive.write(target, target.name)
                        target.unlink()
                    archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        store.check(job)
        with (work / filename).open("rb") as file:
            digest = hashlib.file_digest(file, "sha256").hexdigest()
        manifest["artifact_sha256"] = digest
        publication = work / "publication"
        publication.mkdir()
        (work / filename).replace(publication / filename)
        (publication / "manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        with store.lock:
            store.check(job)
            publication.replace(store.root / "artifacts" / identifier)
            store.put(
                "artifacts",
                {"id": identifier, "filename": filename, "checksum": digest},
            )
        return {"artifact": identifier, "cached": False}
    finally:
        query.close()
