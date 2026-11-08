"""Explicit local-file staging for command-line examples (never exposed as a path API)."""

import hashlib
from uuid import uuid4
from pathlib import Path

from multigas.utils.app_store import utc_now
from multigas.utils.app_config import upload_limit_bytes
from multigas.utils.app_ingest import csv_header


def stage_local_file(store, source: Path) -> dict:
    """Copy an explicitly selected text file in bounded blocks and return a preview.

    Args:
        store (AppStore): Local application storage.
        source (Path): User-selected local CSV/TOA5 file.

    Returns:
        dict: Persistent staged preview and checksum.

    Raises:
        ValueError: If the source is unsupported or exceeds the configured limit.

    Example:
        >>> staged = stage_local_file(store, Path("station.dat"))
    """
    if source.suffix.lower() not in {".dat", ".csv", ".txt"}:
        raise ValueError("Select a CSV or TOA5 text file")
    if source.stat().st_size > upload_limit_bytes():
        raise ValueError("Source exceeds the configured upload size limit")
    identifier = uuid4().hex
    target = store.root / "staged" / identifier
    digest = hashlib.sha256()
    try:
        with source.open("rb") as original, target.open("wb") as staged:
            while chunk := original.read(1024**2):
                if b"\x00" in chunk:
                    raise ValueError("Binary files are not accepted")
                digest.update(chunk)
                staged.write(chunk)
        return store.put(
            "staged",
            {
                "id": identifier,
                "name": source.name,
                "created": utc_now(),
                "size": target.stat().st_size,
                "checksum": digest.hexdigest(),
                "preview": csv_header(target),
            },
        )
    except Exception:
        target.unlink(missing_ok=True)
        raise
