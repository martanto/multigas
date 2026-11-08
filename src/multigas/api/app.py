"""Local FastAPI factory, lifecycle, and optional frontend hosting."""

import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from multigas.api.routes import router
from multigas.core.exceptions import MultigasException
from multigas.utils.app_store import AppStore
from multigas.utils.app_config import upload_limit_bytes


def create_app(
    root: Path | str | None = None,
    upload_limit: int | None = None,
    static_dir: Path | str | None = None,
) -> FastAPI:
    """Create an independent single-user app, with one persistent job worker.

    Args:
        root (Path | str | None): Storage root; defaults to MULTIGAS_APP_DIR/output/app.
        upload_limit (int | None): Maximum bytes; otherwise environment or 5 GiB.
        static_dir (Path | str | None): Optional built frontend directory.

    Returns:
        FastAPI: Application for ``uvicorn multigas.api.app:create_app --factory``.

    Example:
        >>> app = create_app("output/app")
    """

    @asynccontextmanager
    async def lifespan(application):
        application.state.store = AppStore(
            Path(root or os.getenv("MULTIGAS_APP_DIR") or "output/app")
        )
        yield
        application.state.store.close()

    app = FastAPI(title="MultiGas local analysis", version="1.0.0", lifespan=lifespan)
    app.state.upload_limit = (
        upload_limit_bytes() if upload_limit is None else upload_limit
    )
    if app.state.upload_limit <= 0:
        raise ValueError("Upload limit must be positive")
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            from urllib.parse import urlparse

            parsed = urlparse(origin)
            if parsed.hostname not in {"localhost", "127.0.0.1"}:
                return JSONResponse(
                    {"detail": "Only local browser origins are accepted"},
                    status_code=403,
                )
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(KeyError)
    async def missing(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(ValueError)
    @app.exception_handler(MultigasException)
    async def invalid(request, exc):
        return JSONResponse({"detail": str(exc)}, status_code=422)

    app.include_router(router, prefix="/api/v1")
    frontend = static_dir or os.getenv("MULTIGAS_STATIC_DIR")
    if frontend:
        app.mount("/", StaticFiles(directory=str(frontend), html=True), name="frontend")
    return app
