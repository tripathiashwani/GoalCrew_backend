import firebase_admin
from firebase_admin import credentials
import json
from pathlib import Path
from app.config import config
from app.utils.logger import get_logger

logger = get_logger("Firebase_service")


def _load_firebase_certificate() -> credentials.Certificate:
    if config.FIREBASE_CREDENTIALS_JSON:
        return credentials.Certificate(json.loads(config.FIREBASE_CREDENTIALS_JSON))

    if config.FIREBASE_CREDENTIALS_PATH:
        credentials_path = Path(config.FIREBASE_CREDENTIALS_PATH)
        return credentials.Certificate(str(credentials_path))

    raise ValueError("Set FIREBASE_CREDENTIALS_JSON in the environment")

def initialize_firebase() -> None:
    if firebase_admin._apps:
        return  # already initialized
    try:
        cred = _load_firebase_certificate()
        firebase_admin.initialize_app(
            cred,
            {
                "projectId": config.FIREBASE_PROJECT_ID
            }
        )
        logger.info("Firebase Admin SDK initialized.")

    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {e}")
        raise
