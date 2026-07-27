import logging
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.db.models.user import User
from app.modules.reports.service import reports_service
from app.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/pod/{pod_id}/pdf", response_class=Response)
async def download_pod_report_pdf(
    pod_id: UUID,
    start_date: date = Query(...),
    end_date: date = Query(...),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    """
    Generate and download a PDF report of Pod member performance 
    between start_date and end_date.
    """
    logger.info(f"User {user.id} requested PDF report for pod {pod_id} from {start_date} to {end_date}")
    try:
        pdf_bytes = await reports_service.generate_pod_report_pdf(
            db=session,
            pod_id=pod_id,
            user=user,
            start_date=start_date,
            end_date=end_date
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=Pod_Report_{pod_id}.pdf"}
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error generating PDF report: {e}")
        raise HTTPException(status_code=500, detail="Could not generate PDF report")
