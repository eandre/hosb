"""House of Soft Beasts community calendar.

One FastAPI app serves both the JSON API under /api (see events.py) and the
React frontend, built from ../frontend into ./static, at every other path.

GET /api/health   liveness, no sign-in needed
GET /api/config   what the frontend needs to start: the Clerk publishable key
"""

import logging
from pathlib import Path

import encore
from encore.logs import StructuredLogHandler
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

import admin
import events
from settings import settings

logging.basicConfig(level=logging.INFO, handlers=[StructuredLogHandler()])

STATIC_DIR = (Path(__file__).parent / "static").resolve()
INDEX = STATIC_DIR / "index.html"

app = FastAPI(
    title="House of Soft Beasts",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


class PublicConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)
    clerk_publishable_key: str


@app.get("/api/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.get("/api/config")
async def public_config() -> PublicConfig:
    return PublicConfig(clerk_publishable_key=settings.value.clerk_publishable_key)


app.include_router(events.router)
app.include_router(admin.router)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def api_not_found(rest: str) -> None:
    raise HTTPException(status_code=404, detail="no such API route")


NOT_BUILT = """<!doctype html><meta charset="utf-8"><title>House of Soft Beasts</title>
<p>The frontend has not been built. Run <code>bun run build</code> in
<code>frontend/</code>, or <code>bun run dev</code> there for development.</p>"""


@app.get("/{path:path}", include_in_schema=False)
async def frontend(path: str):
    """A file of the built frontend, or its index.html for the app's own
    routes (/events/12), which the frontend's router handles."""
    if path:
        file = (STATIC_DIR / path).resolve()
        if file.is_relative_to(STATIC_DIR) and file.is_file():
            # Vite's bundles have hashed names: cacheable forever.
            immutable = path.startswith("assets/")
            headers = (
                {"Cache-Control": "public, max-age=31536000, immutable"} if immutable else None
            )
            return FileResponse(file, headers=headers)
        if path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="no such file")
    if not INDEX.is_file():
        return HTMLResponse(NOT_BUILT, status_code=503)
    return FileResponse(INDEX, headers={"Cache-Control": "no-cache"})


if __name__ == "__main__":
    # Serve where Encore assigns the service, on Encore's HTTP server: each
    # request is traced, and the service shuts down gracefully with Encore.
    encore.run(app)
