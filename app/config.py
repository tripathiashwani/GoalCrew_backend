# app/config.py
from typing import List, ClassVar
from pathlib import Path
from typing import Any
from pydantic_settings import BaseSettings
from pydantic import AnyHttpUrl, SecretStr
from pydantic import field_validator


class Config(BaseSettings):
    DATABASE_URL: str
    FIREBASE_CREDENTIALS_PATH: str | None = None
    FIREBASE_CREDENTIALS_JSON: str | None = None
    FIREBASE_PROJECT_ID: str
    FCM_SERVER_KEY: SecretStr

    REDIS_URL: str | None = None
    CELERY_BROKER_URL: str | None = None

    BACKEND_CORS_ORIGINS: List[str] = []
    SECRET_KEY: str 

    # ✅ MARK AS ClassVar (not a pydantic field)    
    BASE_DIR: ClassVar[Path] = Path(__file__).resolve().parent.parent

    # ✅ uploads inside backend
    UPLOAD_DIR: ClassVar[Path] = BASE_DIR / "uploads" / "pods"
    SMTP_PORT:str
    # Required: Yes
    # Description: SMTP server port
    # Common ports: 587 (TLS), 465 (SSL)

    SMTP_HOST:str
    # Required: Yes
    # Description: SMTP server hostname
    # Example: smtp.gmail.com, smtp.office365.com

    SMTP_USER: str
    # Required: Yes
    # Description: SMTP server username/email

    SMTP_PASSWORD: str
    # Required: Yes
    # Description: SMTP server password or app-specific password

    EMAILS_FROM_EMAIL:str
    # Required: Yes
    # Description: Email address used as sender

    EMAILS_FROM_NAME :str
    FRONTEND_URL : str

    # Twilio SMS Service
    TWILIO_ACCOUNT_SID :str
    TWILIO_AUTH_TOKEN : str
    TWILIO_MESSAGING_SERVICE_SID :str
    GEMINI_API_KEY: str | None = None

    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_backend_cors_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value


# ensure upload dir exists at import time
Config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

config = Config()
