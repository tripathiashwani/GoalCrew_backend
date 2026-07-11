from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from app.utils.logger import get_logger

logger = get_logger("API")


def init_error_handlers(app: FastAPI):

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning({
            "path": request.url.path,
            "method": request.method,
            "status": exc.status_code,
            "detail": exc.detail,
        })
        return JSONResponse(
            {"detail": exc.detail},
            status_code=exc.status_code
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
        logger.error(f"Database error: {str(exc)}")
        return JSONResponse(
            {"detail": "Database error"},
            status_code=500
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled error: {repr(exc)}")
        return JSONResponse(
            {"detail": "Internal server error"},
            status_code=500
        )
