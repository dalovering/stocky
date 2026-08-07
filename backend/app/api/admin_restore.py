"""Admin: restore the database from a full-workbook backup.

One endpoint, two phases: without `apply` it returns the diff plan (the preview the UI
shows); with `apply=true` it recomputes the plan from the same uploaded bytes and
executes it in a single transaction. A plan with errors is returned as-is and is never
applied — all-or-nothing, unlike the per-row best-effort imports.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.schemas.restore import RestorePlan
from app.services import restore as restore_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:restore"], dependencies=[Depends(require_admin)]
)


@router.post("/restore", response_model=RestorePlan)
async def restore_database(
    file: UploadFile = File(...),
    apply: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> RestorePlan:
    """Diff an uploaded `database.xlsx` backup against the live database; apply on request.

    Restores everything the backup carries — users, groups, item types, items, the full
    event history, and settings. Never touches the admin password.
    """
    return await restore_svc.plan_restore(session, await file.read(), apply=apply)
