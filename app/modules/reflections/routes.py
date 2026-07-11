# app/modules/reflections/routes.py
from __future__ import annotations

from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session 

from app.db.models.user import User
from app.dependencies import get_current_user 
from fastapi import UploadFile, File

from . import schemas, service

router = APIRouter(prefix="/pods/{pod_id}/reflections", tags=["Reflections"])


@router.post("/{reflection_id}/attachments", response_model=schemas.ReflectionResponse)
async def upload_reflection_attachment(
    pod_id: UUID,
    reflection_id: UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.add_reflection_attachment(
        db=db,
        pod_id=pod_id,
        reflection_id=reflection_id,
        user=user,
        file=file,
    )


@router.post("", response_model=schemas.ReflectionResponse, status_code=201)
async def add_reflection(
    pod_id: UUID,
    payload: schemas.ReflectionUpsertRequest,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.add_reflection(
        db=db,
        pod_id=pod_id,
        user=user,
        reflection_date=payload.reflection_date,
        content=payload.content,
        mood=payload.mood,
        goals_payload=[g.model_dump() for g in payload.goals],
    )


@router.get("", response_model=schemas.ReflectionListResponse)
async def list_my_reflections(
    pod_id: UUID,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.list_my_reflections(db, pod_id, user, start=start, end=end)


@router.get("/by-date/{reflection_date}", response_model=schemas.ReflectionResponse)
async def get_my_reflection_by_date(
    pod_id: UUID,
    reflection_date: date,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.get_reflection_by_date(db, pod_id, user, reflection_date)


@router.get("/{reflection_id}", response_model=schemas.ReflectionResponse)
async def get_my_reflection(
    pod_id: UUID,
    reflection_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.get_reflection_by_id(db, pod_id, user, reflection_id)


@router.delete("/{reflection_id}")
async def delete_my_reflection(
    pod_id: UUID,
    reflection_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await service.delete_reflection(db, pod_id, user, reflection_id)
