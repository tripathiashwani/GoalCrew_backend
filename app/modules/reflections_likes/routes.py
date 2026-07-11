# reflection_reactions/routes.py

from fastapi import APIRouter, Body, Depends
from uuid import UUID
from app.db.session import get_session
from app.dependencies import get_current_user
from app.modules.reflections_likes.schemas import (
    ReactionRemovePayload,
    ReflectionReactionCreate,
    ReflectionReactionSummary,
)
from app.modules.reflections_likes import services as service

router = APIRouter(
    prefix="/pods/{pod_id}/reflections/{reflection_id}/reactions",
    tags=["Reflection Reactions"],
)

@router.get("", response_model=ReflectionReactionSummary)
async def list_reactions(
    pod_id: UUID,
    reflection_id: UUID,
    session=Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.list_reactions(session, pod_id, reflection_id, user)

@router.post("", response_model=ReflectionReactionSummary)
async def toggle_reaction(
    pod_id: UUID,
    reflection_id: UUID,
    payload: ReflectionReactionCreate,
    session=Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.toggle_reaction(
        session, pod_id, reflection_id, user, payload.reaction
    )

@router.delete("", response_model=ReflectionReactionSummary)
async def remove_reaction(
    pod_id: UUID,
    reflection_id: UUID,
    payload: ReactionRemovePayload = Body(...), 
    session=Depends(get_session),
    user=Depends(get_current_user),
):
    return await service.remove_reaction(
        session, pod_id, reflection_id, user, payload.reaction,
    )
