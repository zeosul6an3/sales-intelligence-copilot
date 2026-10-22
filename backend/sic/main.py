"""FastAPI application: the API under /api and the built dashboard at /."""

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from sic import __version__
from sic.api import datasets, uploads
from sic.config import FRONTEND_DIST, get_settings


def check_ollama(ollama_url: str, timeout_s: float = 2.0) -> dict:
    """Report whether the local Ollama server answers. Never raises."""
    try:
        response = httpx.get(f"{ollama_url}/api/version", timeout=timeout_s)
        response.raise_for_status()
        return {"reachable": True, "version": response.json().get("version")}
    except (httpx.HTTPError, ValueError) as exc:
        return {"reachable": False, "error": type(exc).__name__}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Sales Intelligence Copilot", version=__version__)

    @app.get("/api/health")
    def health() -> dict:
        return {
            "status": "ok",
            "app_version": __version__,
            "ollama": check_ollama(settings.ollama_url),
        }

    app.include_router(datasets.router)
    app.include_router(uploads.router)

    # Serve the compiled React dashboard if it has been built. API routes are
    # registered first, so /api/... is never shadowed by the static files.
    if FRONTEND_DIST.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="dashboard")

    return app


app = create_app()
