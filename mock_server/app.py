"""FastAPI entrypoint for the UTM campus backend (UKB + Facility Booking) on SurrealDB."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from mock_server.db import define_schema, wait_for_db
from mock_server.routers import facility, ukb
from mock_server.seed import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_db()
    define_schema()
    seed()
    yield


app = FastAPI(
    title="MAiCampus Mock Backend",
    description=(
        "Mock UTM services for MAiCampus: the University Knowledge Base (UKB) and the "
        "Facility Booking API, backed by SurrealDB (graph enrollments + records). Seeded with a "
        "UTM / Malaysian dataset anchored to the assignment's FOL scenario "
        "(MECS0033 · Darwin · Mon 09:00-11:00 · Room N28)."
    ),
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(ukb.router)
app.include_router(facility.router)


@app.get("/", tags=["health"])
def health() -> dict:
    return {"status": "ok", "service": "maicampus-mock-backend"}
