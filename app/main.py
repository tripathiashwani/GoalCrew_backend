from fastapi import FastAPI, Request, status
from fastapi.concurrency import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import Config
from app.core.error_handlers import init_error_handlers
from app.firebase.auth import FirebaseAuthMiddleware
from app.firebase.firebase_init import initialize_firebase
from app.db.session import async_session

from app.modules.events.dispatcher import dispatcher
from app.modules.notifications.service import NotificationService
from app.modules.users.routes import router as users_router
from app.modules.goals.routes import router as goals_router
from app.modules.reflections.routes import router as reflections_router
from app.modules.pods.routes import router as pods_router
from app.modules.notifications.routes import router as notifications_router
from app.modules.analytics.routes import router as analytics_router
from app.modules.pod_updates.routes import router as pod_updates
from app.modules.reflections_comments.routes import router as reflection_comments_router
from app.modules.reflections_likes.routes import router as reflection_likes_router
from app.modules.pod_stats.routes import router as pod_stats_router
from app.modules.user_preferences.routes import router as user_preference_router
from app.modules.admin.routes import router as admin_router
from app.modules.log_module.routes import router as log_router
from app.modules.chatbot.routes import router as chatbot_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🔹 STARTUP
    init_error_handlers(app)
    initialize_firebase()

    async def notification_handler(event):
        async with async_session() as db:
            svc = NotificationService(db)
            await svc.handle_event(event)

    dispatcher.register(notification_handler)

    yield  # ---- application runs here ----

    # 🔹 SHUTDOWN (optional cleanup)

app = FastAPI(title="GoalCrew Backend", version="0.1.0", lifespan=lifespan,)

API_V1_PREFIX = "/api/v1"

# Load config
config = Config()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in config.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Firebase auth middleware
app.add_middleware(FirebaseAuthMiddleware)

# Register routers
app.include_router(pods_router, prefix=API_V1_PREFIX)
app.include_router(goals_router, prefix=API_V1_PREFIX)
app.include_router(users_router, prefix=API_V1_PREFIX)
app.include_router(reflections_router, prefix=API_V1_PREFIX)
app.include_router(pod_updates, prefix=API_V1_PREFIX)
app.include_router(reflection_comments_router,prefix=API_V1_PREFIX)
app.include_router(reflection_likes_router,prefix=API_V1_PREFIX)
app.include_router(pod_stats_router,prefix=API_V1_PREFIX)
app.include_router(user_preference_router,prefix=API_V1_PREFIX)
app.include_router(notifications_router,prefix=API_V1_PREFIX)
app.include_router(admin_router,prefix=API_V1_PREFIX)
app.include_router(log_router,prefix=API_V1_PREFIX)
app.include_router(chatbot_router, prefix=API_V1_PREFIX)


# @app.exception_handler(status.HTTP_401_UNAUTHORIZED)
# async def unauthorized_exception_handler(request: Request, exc) -> JSONResponse:
#     return JSONResponse(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         content={"detail": "Unauthorized"},
#     )


# @app.exception_handler(status.HTTP_403_FORBIDDEN)
# async def forbidden_exception_handler(request: Request, exc) -> JSONResponse:
#     return JSONResponse(
#         status_code=status.HTTP_403_FORBIDDEN,
#         content={"detail": "Forbidden"},
#     )


@app.exception_handler(status.HTTP_404_NOT_FOUND)
async def not_found_exception_handler(request: Request, exc) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"detail": "Not Found"},
    )

app.mount(
    "/uploads",
    StaticFiles(directory=config.BASE_DIR / "uploads"),
    name="uploads",
)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, log_level="info")
