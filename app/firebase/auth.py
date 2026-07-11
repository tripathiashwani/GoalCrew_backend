from os import path
import typing
import firebase_admin
from firebase_admin import auth
from fastapi import Request, status
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

from app.utils.logger import get_logger

logger = get_logger("Firebase_service")

PUBLIC_PATHS = {
    "/api/v1/users/login",
    "/api/v1/users/register",
    "/api/v1/users/auth/verify-email",
    "/api/v1/users/reset-password",
    "/api/v1/users/forgot-password",
    "/api/v1/users/resend-verification-email",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/uploads"
}


class FirebaseUser(typing.TypedDict):
    uid: str
    email: str | None
    name: str | None


class FirebaseAuthMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        # 🔍 DEBUG: log incoming request path
        logger.info(f"[FirebaseMiddleware] Incoming path: {path}")

        # ✅ Skip Firebase auth for public routes
        if any(path.startswith(p) for p in PUBLIC_PATHS):
            logger.info(f"[FirebaseMiddleware] Skipping auth for public route: {path}")
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        auth_header = request.headers.get("authorization")

        # 🔍 DEBUG: log presence of auth header
        logger.info(
            f"[FirebaseMiddleware] Authorization header present: {bool(auth_header)}"
        )

        if not auth_header or not auth_header.startswith("Bearer "):
            logger.warning("[FirebaseMiddleware] Missing or invalid Authorization header")
            response = JSONResponse(
                {"detail": "Not authenticated"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            await response(scope, receive, send)
            return

        token = auth_header.replace("Bearer ", "").strip()

        try:
            decoded = auth.verify_id_token(token, app=firebase_admin.get_app())

            # 🔍 DEBUG: log decoded token (SAFE fields only)
            logger.info(
                "[FirebaseMiddleware] Firebase token decoded successfully",
                extra={
                    "uid": decoded.get("uid"),
                    "email": decoded.get("email"),
                    "issuer": decoded.get("iss"),
                    "audience": decoded.get("aud"),
                    "auth_time": decoded.get("auth_time"),
                    "exp": decoded.get("exp"),
                },
            )

            scope.setdefault("state", {})
            scope["state"]["current_user"] = {
                "uid": decoded.get("uid"),
                "email": decoded.get("email"),
                "name": decoded.get("name"),
            }


        except Exception as e:
            logger.warning(f"[FirebaseMiddleware] Token verification failed: {e}")
            response = JSONResponse(
                {"detail": "Invalid or expired token"},
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
