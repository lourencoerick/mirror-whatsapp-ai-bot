from uuid import UUID
import contextvars
from fastapi import Request, Header, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger


# Context variable for current request's user ID
_user_id_ctx_var = contextvars.ContextVar("user_id", default=None)


def set_user_id(user_id: UUID):
    _user_id_ctx_var.set(user_id)


def get_user_id() -> UUID:
    user_id = _user_id_ctx_var.get()
    if user_id is None:
        raise RuntimeError("user_id not set in context")
    return user_id


class UserContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            user_id_header = request.headers.get("X-User-ID")

            if not user_id_header:
                logger.warning("[middleware] Missing X-User-ID header")
                return JSONResponse(
                    {"detail": "Missing X-User-ID header"}, status_code=401
                )

            try:
                user_id = UUID(user_id_header)
                set_user_id(user_id)
                logger.debug(f"[middleware] User ID set: {user_id}")
            except ValueError:
                logger.warning("[middleware] Invalid X-User-ID format")
                return JSONResponse(
                    {"detail": "Invalid X-User-ID format"}, status_code=400
                )

            response = await call_next(request)
            return response

        except Exception as e:
            logger.exception("[middleware] Unexpected error in user context")
            return JSONResponse(
                {"detail": f"Failed to initialize user context: {str(e)}"},
                status_code=500,
            )


def get_user_id_from_header(x_user_id: str = Header(...)) -> UUID:
    try:
        return UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid X-User-ID format")
