"""Admin: the attendance report behind the Attendance tab."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.schemas.attendance import AttendanceReport, Timeframe
from app.services import attendance as attendance_svc

router = APIRouter(
    prefix="/api/admin", tags=["admin:attendance"], dependencies=[Depends(require_admin)]
)


@router.get("/attendance", response_model=AttendanceReport)
async def attendance(
    timeframe: Timeframe = "today", session: AsyncSession = Depends(get_session)
) -> AttendanceReport:
    """Per-group scheduled days with Present/Absent per direct member, entirely server-computed."""
    return await attendance_svc.attendance_report(session, timeframe)
