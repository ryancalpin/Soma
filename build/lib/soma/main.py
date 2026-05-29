"""FastAPI application: mounts the API and serves the built frontend."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .api import routes_assets, routes_jobs, routes_upload

app = FastAPI(title="Soma", version="0.1.0")

app.include_router(routes_upload.router)
app.include_router(routes_jobs.router)
app.include_router(routes_assets.router)


@app.on_event("startup")
def _startup() -> None:
    config.ensure_dirs()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


# Serve the built frontend if present; otherwise a helpful placeholder.
if config.STATIC_DIR.exists() and (config.STATIC_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(config.STATIC_DIR), html=True), name="static")
else:

    @app.get("/", response_class=HTMLResponse)
    def _placeholder() -> str:
        return (
            "<h1>Soma backend is running</h1>"
            "<p>The frontend has not been built yet. Run "
            "<code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>.</p>"
        )
