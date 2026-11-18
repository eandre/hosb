"""House of Soft Beasts community calendar.

The JSON API, under /api (see events.py, admin.py, share.py and
google_calendar.py), which the api gateway exposes. The frontend is the `web`
service in ../frontend, served from an origin of its own, which calls it
there. Routes for Encore alone, such as a cron job's, are under /internal,
which the gateway doesn't expose.

GET /api/health   liveness, no sign-in needed
GET /api/config   what the frontend needs to start: the Clerk publishable key
"""

import logging

import encore
from encore.logs import StructuredLogHandler
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

import admin
import events
import google_calendar
import share
from settings import settings

logging.basicConfig(level=logging.INFO, handlers=[StructuredLogHandler()])

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
app.include_router(share.router)
app.include_router(google_calendar.router)
app.include_router(google_calendar.internal)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def api_not_found(rest: str) -> None:
    raise HTTPException(status_code=404, detail="no such API route")


if __name__ == "__main__":
    # Serve where Encore assigns the service, on Encore's HTTP server: each
    # request is traced, and the service shuts down gracefully with Encore.
    encore.run(app)
