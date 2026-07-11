import firebase_admin
from firebase_admin import credentials
from app.config import config
from app.utils.logger import get_logger

logger = get_logger("Firebase_service")

def initialize_firebase() -> None:
    if firebase_admin._apps:
        return  # already initialized
    try:
        cred = credentials.Certificate(config.FIREBASE_CREDENTIALS_PATH)
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
