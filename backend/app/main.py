"""Stocky API entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    admin_attendance,
    admin_export,
    admin_history,
    admin_inventory,
    admin_settings,
    admin_users,
    auth,
    inventory,
    kiosk,
    labels,
    printing,
)
from app.core.config import settings

app = FastAPI(
    title="Stocky API",
    description="Classroom inventory management.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin_users.router)
app.include_router(admin_inventory.router)
app.include_router(admin_history.router)
app.include_router(admin_settings.router)
app.include_router(admin_export.router)
app.include_router(admin_attendance.router)
app.include_router(kiosk.router)
app.include_router(inventory.router)
app.include_router(labels.router)
app.include_router(printing.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
