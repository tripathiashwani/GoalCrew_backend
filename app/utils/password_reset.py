from datetime import datetime, timedelta, timezone
import jwt
import hashlib
from app.config import Config

config = Config()

ALGORITHM = "HS256"
RESET_TOKEN_EXP_MINUTES = 60


def create_password_reset_token(email: str) -> tuple[str, str]:
    """
    Returns:
        raw_token (sent via email)
        hashed_token (stored in DB)
    """
    payload = {
        "sub": email,
        "type": "password_reset",
        "exp": datetime.now(tz=timezone.utc) + timedelta(minutes=RESET_TOKEN_EXP_MINUTES),
        "iat": datetime.now(tz=timezone.utc),
    }

    raw_token = jwt.encode(payload, config.SECRET_KEY, algorithm=ALGORITHM)

    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

    return raw_token, hashed_token


def verify_password_reset_token(raw_token: str) -> str:
    try:
        payload = jwt.decode(
            raw_token,
            config.SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        if payload.get("type") != "password_reset":
            raise ValueError("Invalid token type")

        return payload["sub"]  # email

    except jwt.ExpiredSignatureError:
        raise ValueError("Reset token expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid reset token")
