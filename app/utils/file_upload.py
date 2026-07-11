import uuid
import time
from pathlib import Path
from fastapi import UploadFile, HTTPException

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

def save_reflection_attachment(
    pod_id: str,
    file: UploadFile,
    upload_root: Path,
) -> tuple[str, str]:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only images and GIFs are allowed",
        )

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{uuid.uuid4()}_{int(time.time())}.{ext}"

    pod_dir = upload_root / pod_id
    pod_dir.mkdir(parents=True, exist_ok=True)

    file_path = pod_dir / filename

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    file_url = f"/uploads/pods/{pod_id}/{filename}"
    file_type = "gif" if ext == "gif" else "image"

    return file_url, file_type

def save_user_avatar(
    user_id: str,
    file: UploadFile,
    upload_root: Path,
) -> tuple[str, str]:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Only images and GIFs are allowed",
        )

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{uuid.uuid4()}_{int(time.time())}.{ext}"

    avatar_dir = upload_root / user_id
    avatar_dir.mkdir(parents=True, exist_ok=True)

    file_path = avatar_dir / filename

    with file_path.open("wb") as buffer:
        buffer.write(file.file.read())

    file_url = f"/uploads/avatar/{user_id}/{filename}"
    file_type = "gif" if ext == "gif" else "image"

    return file_url, file_type
