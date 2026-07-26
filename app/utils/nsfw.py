from fastapi import FastAPI, UploadFile, File
from nudenet import NudeDetector
from PIL import Image
import shutil
from fastapi import HTTPException

import os
from app.utils.logger import get_logger
logger = get_logger("AddReflectionAttachmentService")



CRITICAL_CLASSES = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}

HIGH_RISK_CLASSES = {
    "FEMALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
}

MODERATE_CLASSES = {
    "BELLY_EXPOSED",
    "ARMPITS_EXPOSED",
}

CRITICAL_THRESHOLD = 0.50
HIGH_RISK_THRESHOLD = 0.65
MODERATE_THRESHOLD = 0.90





async def check_nsfw(file):
    path = f"uploads/{file.filename}"

    try:
        detector = NudeDetector()
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Rewind for later use
        await file.seek(0)

        detections = detector.detect(path)

        logger.info(f"NSFW detections: {detections}")

        for item in detections:
            cls = item["class"]
            score = item["score"]

            if cls in CRITICAL_CLASSES and score >= CRITICAL_THRESHOLD:
                raise HTTPException(
                    status_code=400,
                    detail="NSFW content detected."
                )

            if cls in HIGH_RISK_CLASSES and score >= HIGH_RISK_THRESHOLD:
                raise HTTPException(
                    status_code=400,
                    detail="NSFW content detected."
                )

            if cls in MODERATE_CLASSES and score >= MODERATE_THRESHOLD:
                raise HTTPException(
                    status_code=400,
                    detail="NSFW content detected."
                )

        return True

    finally:
        if os.path.exists(path):
            os.remove(path)