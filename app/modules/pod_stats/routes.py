from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.dependencies import get_current_user
from app.db.models.user import User
from app.modules.pod_stats.schema import PodStatsResponse
from app.modules.pod_stats.service import get_pod_stats, get_pod_contribution_heatmap

router = APIRouter(
    prefix="/pods/{pod_id}/stats",
    tags=["Pod Stats"],
)


@router.get(
    "",
    response_model=PodStatsResponse,
)
async def fetch_pod_stats(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Dashboard statistics:
    - Personal progress
    - Pod health
    """
    return await get_pod_stats(
        db=db,
        pod_id=pod_id,
        user=user,
    )











from .schema import PodContributionHeatmapResponse, HeatmapDay

# app/modules/pod_stats/routes.py

@router.get(
    "/contribution-heatmap",
    response_model=PodContributionHeatmapResponse,
)
async def pod_contribution_heatmap(
    pod_id: UUID,
    db: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    return await get_pod_contribution_heatmap(
        db=db,
        pod_id=pod_id,
        user=user,
    )


# @router.get(
#     "/contribution-heatmap",
#     response_model=PodContributionHeatmapResponse,
# )
# async def pod_contribution_heatmap(
#     pod_id: UUID,
#     db: AsyncSession = Depends(get_session),
#     user=Depends(get_current_user),
# ):
#     days = await get_pod_contribution_heatmap(
#         db=db,
#         pod_id=pod_id,
#         user_id=user.id,
#     )

#     return {
#         "pod_id": str(pod_id),
#         "days": days,
#     }
