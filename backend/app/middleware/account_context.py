from uuid import UUID
import contextvars
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger

# Context variable for current request's account ID
_account_id_ctx_var = contextvars.ContextVar("account_id", default=None)


def set_account_id(account_id: UUID):
    _account_id_ctx_var.set(account_id)


def get_account_id() -> UUID:
    account_id = _account_id_ctx_var.get()
    if account_id is None:
        raise RuntimeError("account_id not set in context")
    return account_id


class AccountContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:

            logger.debug(f"[middleware] request url: {request.url}")
            if (
                "/webhooks" in request.url.path
                or "/me" in request.url.path
                or "/auth" in request.url.path
            ):
                return await call_next(request)

            account_id_header = request.headers.get("X-Account-ID")

            if not account_id_header:
                logger.warning("[middleware] Missing X-Account-ID header")
                return JSONResponse(
                    {"detail": "Missing X-Account-ID header"}, status_code=401
                )

            try:
                account_id = UUID(account_id_header)
                set_account_id(account_id)
                logger.debug(f"[middleware] Account ID set: {account_id}")
            except ValueError:
                logger.warning("[middleware] Invalid X-Account-ID format")
                return JSONResponse(
                    {"detail": "Invalid X-Account-ID format"}, status_code=400
                )

            response = await call_next(request)
            return response

        except Exception as e:
            logger.exception("[middleware] Unexpected error in account context")
            return JSONResponse(
                {"detail": f"Failed to initialize account context: {str(e)}"},
                status_code=500,
            )
