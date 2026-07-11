from fastapi import APIRouter, Depends , HTTPException,Query
from sqlalchemy.orm import Session
from typing import Literal, Optional

from typing import List
from uuid import UUID

from app.db.session import get_session
from fastapi import Query
from .schemas import AdminUserOut
from app.modules.admin.schemas import AdminPodOut, AdminCommentOut, AdminActivityOut, AdminGoalOut, AdminActivityResponse, AdminCheckinOut, PaginatedReflectionCommentsResponse, GoalDetailResponse
from .service import AdminService
from app.utils.logger import get_logger
from app.dependencies import get_current_user, admin_user_required
logger = get_logger("AdminRoutes")


router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=List[AdminUserOut])
async def list_admin_users(current_user=Depends(admin_user_required),db: Session = Depends(get_session)):
    try:
       logger.info("list admin uses called")
       
       return  await AdminService.get_users(db)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    


@router.delete("/users/delete/{user_id}")
async def delete_user(user_id: UUID,current_user=Depends(admin_user_required),db: Session = Depends(get_session)):
    try:
       logger.info(f"delete user called to delete user_id:{user_id}")
       
       return  await AdminService.delete_user(user_id,db)
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/pods/{pod_id}/goals", response_model=list[AdminGoalOut])
async def get_pod_goals(
    pod_id: UUID,
    user_id: Optional[UUID] = Query(None),
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session)
):
    logger.info(f"get pod goals called with pod_id:{pod_id} and user_id :{user_id}")
    return await AdminService.get_pod_goals(db, pod_id,user_id)



@router.get("/pods", response_model=List[AdminPodOut])
async def list_admin_pods(user_id: Optional[UUID] = None,current_user=Depends(admin_user_required),db: Session = Depends(get_session)):
    logger.info("admin pods called")
    return await AdminService.get_pods(user_id,db)

@router.get("/comments", response_model=List[AdminCommentOut])
async def list_admin_comments(
    user_id: Optional[UUID] = None,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session),
    limit: int = Query(200, ge=1, le=1000), 
):
    logger.info("admin comments called")
    logger.info(f"Query params: user_id={user_id}, limit={limit}")
    return await AdminService.get_comments(db, limit=limit, user_id=user_id)



@router.get("/activity", response_model=AdminActivityResponse)
async def list_admin_activity(
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session),
    limit: int = Query(200, ge=1, le=1000),
):
    logger.info(f"list_admin_activity api called")
    return await AdminService.get_activity_logs(db, limit)





@router.delete("/comments/{comment_id}")
async def delete_comment(
    comment_id: UUID,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session)
):
    try:
        logger.info(f"delete comment called comment_id:{comment_id}")
        return await AdminService.delete_comment(comment_id,db)
    except Exception as e:
        logger.info(f"Error while deleting comment :{str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    



@router.delete("/activity/{activity_id}")
async def delete_activity_log(
    activity_id: UUID,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session)
):
    try:
        logger.info(f"delete activity log called activity_id:{activity_id}")
        return await AdminService.delete_activity(activity_id,db)

    except Exception as e:
        logger.error(f"failed to delete activity log: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    



@router.delete("/goals/{goal_id}")
async def delete_goal(
    goal_id: UUID,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session)
):
    try:
        logger.info(f"delete goal called goal_id:{goal_id}")
        return await AdminService.delete_goal(goal_id,db)
    except Exception as e:
        logger.error(f"failed to delete goal : {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    

@router.get("/pods/{pod_id}/checkins", response_model=List[AdminCheckinOut])
async def list_admin_checkins(
    pod_id: UUID,
    user_id: Optional[UUID] = None,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session),
    limit: int = Query(500, ge=1, le=2000),
):
    logger.info(f"admin checkins called for pod_id:{pod_id} user_id:{user_id}")
    return await AdminService.get_checkins(
        db=db,
        pod_id=pod_id,
        user_id=user_id,
        limit=limit,
    )


@router.delete("/checkins/{reflection_id}")
async def delete_admin_checkin(
    reflection_id: UUID,
    current_user=Depends(admin_user_required),
    db: Session = Depends(get_session),
):
    logger.info(f"admin delete checkin called reflection_id:{reflection_id}")

    return await AdminService.delete_checkin(db, reflection_id)





@router.get(
    "/checkin/comments",
    response_model=PaginatedReflectionCommentsResponse,
)
async def list_comments(
    reflection_id: UUID,
    session: Session = Depends(get_session),
    user= Depends(admin_user_required),
):
    
    return await AdminService.list_comments(
        session,
        reflection_id,
    )





@router.get("/pods/{pod_id}/goals/{goal_id}", response_model=GoalDetailResponse)
async def get_goal(
    pod_id: UUID,
    goal_id: UUID,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    return await AdminService.get_goal(session, pod_id, goal_id, user)



@router.get("/goals/{goal_id}", response_model=GoalDetailResponse)
async def get_goal_without_pod(
    goal_id: UUID,
    session: Session = Depends(get_session),
    user=Depends(get_current_user),
):
    return await AdminService.get_goal(session, None, goal_id, user)






@router.delete("/pods/delete/{pod_id}")
async def delete_pod(
    pod_id: UUID,
    db: Session = Depends(get_session),
    user=Depends(admin_user_required),
):
    try:
        

        await AdminService.delete_pod(db, pod_id, user)
        return {"message": "Pod deleted successfully"}
    
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"{str(e)}",
        )




@router.post("/pod/{pod_id}/leave/{user_id}")
async def leave_pod(
    pod_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_session),
    user=Depends(admin_user_required),
):
    try:

        await AdminService.leave_pod(db, pod_id, user_id)
        return {"message": "User have left the pod"}
    
    except Exception as e:
        raise HTTPException(
                status_code=400,
                detail=f"{str(e)}",
            )