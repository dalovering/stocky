"""Admin: user and group management (CRUD, nested groups, barcodes, ID cards)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_unique_barcode, require_admin
from app.api.responses import pdf_response, xlsx_response
from app.core.db import get_session
from app.models import Event, Group, User, UserStatus
from app.schemas.group import GroupCreate, GroupRead, GroupTree, GroupUpdate
from app.schemas.imports import ImportResult
from app.schemas.inventory import EventRead, IdList
from app.schemas.user import UserBatchUpdate, UserCreate, UserDetail, UserRead, UserUpdate
from app.services import barcode as barcode_svc
from app.services import cards as cards_svc
from app.services import events as event_svc
from app.services import spreadsheet as spreadsheet_svc
from app.services.queries import group_names, user_filter_query
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
    # Block deleting a non-empty group: its parent_id / group_id foreign keys would otherwise
    # raise a DB error. Mirror the item-type guard and return a clean 409 instead.
    child_groups = await session.scalar(
        select(func.count()).select_from(Group).where(Group.parent_id == group_id)
    )
    members = await session.scalar(
        select(func.count()).select_from(User).where(User.group_id == group_id)
    )
    if child_groups or members:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Cannot delete a group that still has subgroups or members.",
        )
    await session.delete(group)
    await session.commit()


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
async def _unique_user_barcode(session: AsyncSession, proposed: str | None) -> str:
    return await ensure_unique_barcode(session, User, barcode_svc.USER_PREFIX, proposed)


@router.get("/users", response_model=list[UserRead])
async def list_users(
    group_id: uuid.UUID | None = None,
    q: str | None = None,
    status: Annotated[list[UserStatus] | None, Query()] = None,
    session: AsyncSession = Depends(get_session),
) -> list[UserRead]:
    users = list((await session.execute(user_filter_query(q, status, group_id))).scalars().all())

    groups = await group_names(session)
    out: list[UserRead] = []
    for user in users:
        out.append(
            UserRead(
                id=user.id,
                name=user.name,
                group_id=user.group_id,
                group_name=groups.get(user.group_id) if user.group_id else None,
                status=user.status,
                barcode=user.barcode,
                loan_count=await loan_count(session, user.id),
            )
        )
    return out


@router.post("/users", response_model=UserDetail, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, session: AsyncSession = Depends(get_session)) -> UserDetail:
    barcode = await _unique_user_barcode(session, body.barcode)
    user = User(name=body.name, group_id=body.group_id, status=body.status, barcode=barcode)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return await serialize_user_detail(session, user)


# ---------------------------------------------------------------------------
# Spreadsheet import/export and batch ops — all before `/users/{user_id}` so their literal
# path segments aren't parsed as a user id.
# ---------------------------------------------------------------------------
@router.get("/users.xlsx")
async def export_users(session: AsyncSession = Depends(get_session)) -> Response:
    return xlsx_response(await spreadsheet_svc.users_workbook(session), "stocky-users.xlsx")


@router.post("/users/import", response_model=ImportResult)
async def import_users(
    file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
) -> ImportResult:
    return await spreadsheet_svc.import_users(session, await file.read())


@router.post("/users/id-cards.pdf")
async def users_id_cards_pdf(
    body: IdList, session: AsyncSession = Depends(get_session)
) -> Response:
    """ID cards for a selection of users, one per page."""
    users = (
        list((await session.execute(select(User).where(User.id.in_(body.ids)))).scalars().all())
        if body.ids
        else []
    )
    users.sort(key=lambda u: u.name)
    pdf = cards_svc.render_per_page(
        cards_svc.ID_CARD, await cards_svc.build_user_cards(session, users)
    )
    return pdf_response(pdf, "stocky-id-cards.pdf")


@router.patch("/users/batch", response_model=list[UserRead])
async def batch_update_users(
    body: UserBatchUpdate, session: AsyncSession = Depends(get_session)
) -> list[UserRead]:
    data = body.patch.model_dump(exclude_unset=True)
    users = (
        list((await session.execute(select(User).where(User.id.in_(body.ids)))).scalars().all())
        if body.ids
        else []
    )
    for user in users:
        for field, value in data.items():
            setattr(user, field, value)
        session.add(user)
    await session.commit()

    groups = await group_names(session)
    out: list[UserRead] = []
    for user in users:
        out.append(
            UserRead(
                id=user.id,
                name=user.name,
                group_id=user.group_id,
                group_name=groups.get(user.group_id) if user.group_id else None,
                status=user.status,
                barcode=user.barcode,
                loan_count=await loan_count(session, user.id),
            )
        )
    return out


@router.post("/users/batch-delete", status_code=status.HTTP_204_NO_CONTENT)
async def batch_delete_users(body: IdList, session: AsyncSession = Depends(get_session)) -> None:
    if body.ids:
        # Drop user-only attendance rows and anonymize the rest of their history first.
        await event_svc.detach_user_history(session, body.ids)
        await session.execute(delete(User).where(User.id.in_(body.ids)))
        await session.commit()


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
    # Same as batch delete: drop attendance rows, anonymize item history, then delete.
    await event_svc.detach_user_history(session, [user.id])
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


@router.get("/users/{user_id}/id-card.pdf")
async def user_id_card_pdf(
    user_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """A single user ID card PDF, sized to the card."""
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
    (card,) = await cards_svc.build_user_cards(session, [user])
    return pdf_response(cards_svc.render_single(cards_svc.ID_CARD, card), "stocky-id-card.pdf")


@router.get("/groups/{group_id}/id-cards.pdf")
async def group_id_cards_pdf(
    group_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """ID cards for every user in a group, one per page."""
    users = list(
        (await session.execute(select(User).where(User.group_id == group_id).order_by(User.name)))
        .scalars()
        .all()
    )
    pdf = cards_svc.render_per_page(
        cards_svc.ID_CARD, await cards_svc.build_user_cards(session, users)
    )
    return pdf_response(pdf, "stocky-id-cards.pdf")
