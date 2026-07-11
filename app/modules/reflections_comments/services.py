from uuid import UUID
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.db.models.reflection_comments import ReflectionComment
from app.db.models.reflections import Reflection
from app.db.models.user import User
from app.modules.events.dispatcher import dispatcher
from app.modules.events.schemas import DomainEvent
from app.modules.notifications.constants import NotificationType
from app.modules.pod_updates.service import _ensure_active_member
from app.utils.logger import get_logger
exception_logger=get_logger("Exceptions_logs")
logger=get_logger("Reflection_comments")


async def list_comments(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    user: User,
    *,
    page: int = 1,
    page_size: int = 20,
    order: str = "asc",
):
    try:
        logger.info(f"trying to list comments with reflection id:{reflection_id} and user:{user}")
        await _ensure_active_member(db, pod_id, user.id)

        reflection = await db.get(Reflection, reflection_id)
        if not reflection or reflection.pod_id != pod_id:
            raise HTTPException(status_code=404, detail="Reflection not found")

        offset = (page - 1) * page_size

        # ---- ORDER BY (date + time) ----
        order_expr = (
            ReflectionComment.created_at.asc()
            if order == "asc"
            else ReflectionComment.created_at.desc()
        )

        # ---- TOTAL COUNT ----
        total_stmt = (
            select(func.count(ReflectionComment.id))
            .where(ReflectionComment.reflection_id == reflection_id)
        )
        total = (await db.execute(total_stmt)).scalar_one()

        # ---- MAIN QUERY ----
        stmt = (
            select(
                ReflectionComment,
                User.id.label("u_id"),
                User.name.label("u_name"),
                User.profile_photo_url.label("u_profile_photo_url")
            )
            .join(User, User.id == ReflectionComment.user_id)
            .where(ReflectionComment.reflection_id == reflection_id)
            .order_by(order_expr, ReflectionComment.id.asc())  # stable ordering
            .offset(offset)
            .limit(page_size)
        )

        rows = (await db.execute(stmt)).all()

        items = [
            {
                "id": c.id,
                "reflection_id": c.reflection_id,
                "content": c.content,
                "created_at": c.created_at,
                "user": {
                    "id": u_id,
                    "username": u_name,
                    "profile_photo_url":u_profile_photo_url
                },
            }
            for c, u_id, u_name ,u_profile_photo_url in rows
        ]

        return {
            "page": page,
            "page_size": page_size,
            "total": int(total),
            "items": items,
        }
    
    except Exception as e:
        exception_logger.exception(f"Error while list_comments {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def add_comment(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    user: User,
    content: str,
):
    try:
        logger.info(f"add comment service called in reflection :{reflection_id} having content :{content}")
        await _ensure_active_member(db, pod_id, user.id)
        emit_event = False  
        reflection = await db.get(Reflection, reflection_id)
        if not reflection or reflection.pod_id != pod_id:
            raise HTTPException(status_code=404, detail="Reflection not found")

        comment = ReflectionComment(
            reflection_id=reflection_id,
            user_id=user.id,
            content=content,
        )
        emit_event = True  
        db.add(comment)
        await db.commit()
        await db.refresh(comment)
        # Emit event AFTER commit
        if emit_event:
            await dispatcher.emit(
                DomainEvent(
                    type=NotificationType.REFLECTION_COMMENT,
                    actor_id=user.id,
                    pod_id=pod_id,
                    entity_type="reflection",
                    entity_id=reflection.id,
                    context={
                        "reflection_owner_id": reflection.user_id,
                        "actor_name": user.name or "Someone",
                        "details":content,
                        "target_ids":[comment.id]
                    },
                )
            )

        return {
            "id": comment.id,
            "reflection_id": comment.reflection_id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user": {
                "id": user.id,
                "username": user.name,
            },
        }
    
    except Exception as e:
        exception_logger.exception(f"Error while add_comment {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )


async def update_comment(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    comment_id: UUID,
    user: User,
    content: str,
):
    try:
        await _ensure_active_member(db, pod_id, user.id)

        comment = await db.get(ReflectionComment, comment_id)
        if not comment or comment.reflection_id != reflection_id:
            raise HTTPException(status_code=404, detail="Comment not found")

        if comment.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not allowed")

        comment.content = content
        await db.commit()
        await db.refresh(comment)

        return {
            "id": comment.id,
            "reflection_id": comment.reflection_id,
            "content": comment.content,
            "created_at": comment.created_at,
            "user": {
                "id": user.id,
                "username": user.name,
            },
        }
    except Exception as e:
        exception_logger.exception(f"Error while update_comment {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )

async def delete_comment(
    db: AsyncSession,
    pod_id: UUID,
    reflection_id: UUID,
    comment_id: UUID,
    user: User,
):
    try:

        await _ensure_active_member(db, pod_id, user.id)

        comment = await db.get(ReflectionComment, comment_id)
        if not comment or comment.reflection_id != reflection_id:
            raise HTTPException(status_code=404, detail="Comment not found")

        if comment.user_id != user.id:
            raise HTTPException(status_code=403, detail="Not allowed")

        await db.delete(comment)
        await db.commit()

        return {"success": True}
    
    except Exception as e:
        exception_logger.exception(f"Error while add_comment {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )
