"""Admin: user and group management (CRUD, nested groups, barcodes, ID cards)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_session
from app.models import Event, Group, User
from app.schemas.group import GroupCreate, GroupRead, GroupTree, GroupUpdate
from app.schemas.inventory import EventRead
from app.schemas.user import UserCreate, UserDetail, UserRead, UserUpdate
from app.services import barcode as barcode_svc
from app.services.serialize import loan_count, serialize_event, serialize_user_detail

router = APIRouter(prefix="/api/admin", tags=["admin:users"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------
@router.get("/groups", response_model=list[GroupRead])
async def list_groups(session: AsyncSession = Depends(get_session)) -> list[Group]:
    result = await session.execute(select(Group).order_by(Group.name))
    return list(result.scalars().all())


@router.get("/groups/tree", response_model=list[GroupTree])
async def group_tree(session: AsyncSession = Depends(get_session)) -> list[GroupTree]:
    groups = list((await session.execute(select(Group))).scalars().all())
    counts = dict(
        (await session.execute(select(User.group_id, func.count()).group_by(User.group_id))).all()
    )
    nodes = {
        g.id: GroupTree(
            id=g.id,
            name=g.name,
            parent_id=g.parent_id,
            permissions=g.permissions,
            user_count=int(counts.get(g.id, 0)),
        )
        for g in groups
    }
    roots: list[GroupTree] = []
    for node in nodes.values():
        if node.parent_id and node.parent_id in nodes:
            nodes[node.parent_id].children.append(node)
        else:
            roots.append(node)
    return sorted(roots, key=lambda n: n.name)


@router.post("/groups", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
async def create_group(body: GroupCreate, session: AsyncSession = Depends(get_session)) -> Group:
    group = Group(**body.model_dump())
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


@router.patch("/groups/{group_id}", response_model=GroupRead)
async def update_group(
    group_id: uuid.UUID, body: GroupUpdate, session: AsyncSession = Depends(get_session)
) -> Group:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found.")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(group, field, value)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return group


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(group_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    group = await session.get(Group, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found.")
    await session.delete(group)
    await session.commit()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def _unique_user_barcode(session: AsyncSession, proposed: str | None) -> str:
    if proposed:
        existing = await session.execute(select(User).where(User.barcode == proposed))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Barcode already in use.")
        return proposed
    # Generate until unique.
    for _ in range(10):
        code = barcode_svc.generate_user_code()
        existing = await session.execute(select(User).where(User.barcode == code))
        if existing.scalar_one_or_none() is None:
            return code
    raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Could not allocate a barcode.")


@router.get("/users", response_model=list[UserRead])
async def list_users(
    group_id: uuid.UUID | None = None,
    q: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[UserRead]:
    stmt = select(User)
    if group_id is not None:
        stmt = stmt.where(User.group_id == group_id)
    if q:
        stmt = stmt.where(User.name.ilike(f"%{q}%"))
    users = list((await session.execute(stmt.order_by(User.name))).scalars().all())

    groups = {g.id: g.name for g in (await session.execute(select(Group))).scalars().all()}
    out: list[UserRead] = []
    for user in users:
        out.append(
            UserRead(
                id=user.id,
                name=user.name,
                group_id=user.group_id,
                group_name=groups.get(user.group_id) if user.group_id else None,
                barcode=user.barcode,
                loan_count=await loan_count(session, user.id),
            )
        )
    return out


@router.post("/users", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_session)) -> UserDetail:
    barcode = await _unique_user_barcode(session, body.barcode)
    user = User(name=body.name, group_id=body.group_id, barcode=barcode)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return await serialize_user_detail(session, user)


@router.get("/users/{user_id}", response_model=UserDetail)
async def get_user(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return await serialize_user_detail(session, user)


@router.patch("/users/{user_id}", response_model=UserDetail)
async def update_user(
    user_id: uuid.UUID, body: UserUpdate, session: AsyncSession = Depends(get_session)
) -> UserDetail:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    data = body.model_dump(exclude_unset=True)
    if "barcode" in data and data["barcode"] and data["barcode"] != user.barcode:
        data["barcode"] = await _unique_user_barcode(session, data["barcode"])
    for field, value in data.items():
        setattr(user, field, value)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return await serialize_user_detail(session, user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    await session.delete(user)
    await session.commit()


@router.post("/users/{user_id}/barcode", response_model=UserDetail)
async def regenerate_barcode(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> UserDetail:
    """Generate and assign a fresh barcode to the user."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    user.barcode = await _unique_user_barcode(session, None)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return await serialize_user_detail(session, user)


@router.get("/users/{user_id}/events", response_model=list[EventRead])
async def user_events(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> list[EventRead]:
    result = await session.execute(
        select(Event).where(Event.user_id == user_id).order_by(Event.created_at.desc())
    )
    return [await serialize_event(session, e) for e in result.scalars().all()]


@router.get("/users/{user_id}/barcode.svg")
async def user_barcode_svg(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    return Response(content=barcode_svc.render_svg(user.barcode), media_type="image/svg+xml")
