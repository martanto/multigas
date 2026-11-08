"""SQLite metadata and durable single-worker jobs for the optional application."""

import json
import shutil
import sqlite3
import threading
from uuid import uuid4
from pathlib import Path
from datetime import UTC, datetime, timedelta
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor


def utc_now() -> str:
    """Return an ISO UTC timestamp."""
    return datetime.now(UTC).isoformat()


class Cancelled(Exception):
    """Cooperative job cancellation signal (not a package error)."""


class AppStore:
    """Own generated paths, persistent documents, and one background worker."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        for directory in ("staged", "datasets", "artifacts", "work"):
            (self.root / directory).mkdir(exist_ok=True)
        self.db = self.root / "metadata.sqlite3"
        self.lock = threading.RLock()
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="multigas")
        with self.connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS documents (kind TEXT, id TEXT, body TEXT, PRIMARY KEY(kind,id))"
            )
        for job in self.list("jobs"):
            if job["status"] in {"running", "queued", "cancelling"}:
                job.update(
                    status="interrupted", error="Server restarted. Retry this job."
                )
                self.put("jobs", job)
        for path in (self.root / "work").iterdir():
            if path.is_dir():
                shutil.rmtree(path)
        self.cleanup_staged()

    @contextmanager
    def connect(self):
        """Open a short-lived SQLite transaction."""
        connection = sqlite3.connect(self.db, timeout=30)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def put(self, kind: str, body: dict) -> dict:
        """Atomically save a JSON document."""
        with self.lock, self.connect() as con:
            con.execute(
                "INSERT OR REPLACE INTO documents VALUES (?,?,?)",
                (kind, body["id"], json.dumps(body, allow_nan=False)),
            )
        return body

    def get(self, kind: str, identifier: str) -> dict:
        """Resolve an opaque identifier; never interpret it as a path."""
        with self.connect() as con:
            row = con.execute(
                "SELECT body FROM documents WHERE kind=? AND id=?", (kind, identifier)
            ).fetchone()
        if row is None:
            raise KeyError(f"Unknown {kind} identifier")
        return json.loads(row[0])

    def list(self, kind: str) -> list[dict]:
        """Return stored documents in insertion order."""
        with self.connect() as con:
            return [
                json.loads(r[0])
                for r in con.execute(
                    "SELECT body FROM documents WHERE kind=? ORDER BY rowid", (kind,)
                )
            ]

    def delete(self, kind: str, identifier: str) -> None:
        """Delete one metadata document."""
        with self.connect() as con:
            con.execute(
                "DELETE FROM documents WHERE kind=? AND id=?", (kind, identifier)
            )

    def cleanup_staged(self) -> None:
        """Remove abandoned staged uploads older than 24 hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        active = {
            j["spec"].get("staged")
            for j in self.list("jobs")
            if j["status"] in {"queued", "running", "cancelling"}
        }
        for staged in self.list("staged"):
            if (
                staged["id"] not in active
                and datetime.fromisoformat(staged["created"]) < cutoff
            ):
                (self.root / "staged" / staged["id"]).unlink(missing_ok=True)
                self.delete("staged", staged["id"])

    def check(self, identifier: str) -> None:
        """Raise a cooperative signal when cancellation was requested."""
        if self.get("jobs", identifier)["status"] == "cancelling":
            raise Cancelled()

    def progress(self, identifier: str, progress: float, message: str) -> None:
        """Persist progress without losing a concurrent cancellation request."""
        with self.lock:
            self.check(identifier)
            job = self.get("jobs", identifier)
            job.update(progress=progress, message=message)
            self.put("jobs", job)

    def submit(self, kind: str, spec: dict, operation) -> dict:
        """Queue one restart-visible job; publish its result only after success."""
        job = self.put(
            "jobs",
            {
                "id": uuid4().hex,
                "kind": kind,
                "spec": spec,
                "status": "queued",
                "progress": 0,
                "created": utc_now(),
            },
        )

        def run():
            identifier = job["id"]
            work = self.root / "work" / identifier
            work.mkdir(exist_ok=True)
            try:
                with self.lock:
                    self.check(identifier)
                    current = self.get("jobs", identifier)
                    current["status"] = "running"
                    self.put("jobs", current)
                result = operation(identifier, work)
                with self.lock:
                    current = self.get("jobs", identifier)
                    current.update(
                        status="complete",
                        result=result,
                        progress=1,
                        completed=utc_now(),
                        message="Dataset ready for analysis"
                        if kind == "import"
                        else "Export and reproducibility manifest ready",
                    )
                    self.put("jobs", current)
            except Cancelled:
                current = self.get("jobs", identifier)
                current.update(
                    status="cancelled", message="Cancelled; partial outputs removed"
                )
                self.put("jobs", current)
            except Exception as exc:
                current = self.get("jobs", identifier)
                current.update(status="failed", error=str(exc))
                self.put("jobs", current)
            finally:
                shutil.rmtree(work, ignore_errors=True)

        self.worker.submit(run)
        return job

    def close(self) -> None:
        """Cancel active jobs and finish cleanup on application shutdown."""
        with self.lock:
            for job in self.list("jobs"):
                if job["status"] in {"queued", "running"}:
                    job["status"] = "cancelling"
                    self.put("jobs", job)
        self.worker.shutdown(wait=True)
