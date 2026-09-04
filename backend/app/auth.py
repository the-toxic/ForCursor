from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import get_settings

PUBLIC_PATHS = {"/api/health", "/docs", "/openapi.json", "/redoc"}


class AccessKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method == "OPTIONS":
            return await call_next(request)
        path = request.url.path
        if path in PUBLIC_PATHS or not path.startswith("/api"):
            return await call_next(request)

        provided = request.headers.get("x-auth-key", "")
        expected = getattr(request.app.state, "auth_key", None) or get_settings().auth_key
        if provided != expected:
            return JSONResponse({"detail": "Нужен ключ доступа"}, status_code=401)
        return await call_next(request)
