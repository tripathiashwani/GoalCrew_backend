from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import shutil
import tempfile
from datetime import datetime
from app.dependencies import get_current_user
from app.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/logs", tags=["Logs"])

LOG_DIR = Path("logs")


@router.get("/download")
async def download_logs(session: AsyncSession = Depends(get_session),user=Depends(get_current_user)):

    if not LOG_DIR.exists():
        raise HTTPException(status_code=404, detail="Logs folder not found")

    # temporary zip file
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_path = Path(tempfile.gettempdir()) / f"logs_{timestamp}"

    shutil.make_archive(str(zip_path), "zip", LOG_DIR)

    return FileResponse(
        path=f"{zip_path}.zip",
        filename="logs.zip",
        media_type="application/zip"
    )