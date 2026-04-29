from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

REQUEST_ID_HEADER = "X-Request-ID"


class GatewayUpstreamResponseError(Exception):
    def __init__(
        self,
        *,
        service: str,
        status_code: int,
        body: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.service = service
        self.status_code = status_code
        self.body = body
        self.headers = dict(headers or {})
        super().__init__(f"{service} returned status {status_code}")


def get_request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": get_request_id(request),
        }
    }
    if details:
        payload["error"]["details"] = dict(details)
    return JSONResponse(status_code=status_code, content=payload, headers=dict(headers or {}))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(httpx.TimeoutException)
    async def handle_timeout(request: Request, exc: httpx.TimeoutException) -> JSONResponse:
        return error_response(
            request,
            status_code=504,
            code="upstream_timeout",
            message="Upstream request timed out.",
            details={"reason": str(exc) or exc.__class__.__name__},
        )

    @app.exception_handler(httpx.ConnectError)
    async def handle_connect_error(request: Request, exc: httpx.ConnectError) -> JSONResponse:
        return error_response(
            request,
            status_code=503,
            code="upstream_unavailable",
            message="Upstream service is unavailable.",
            details={"reason": str(exc) or exc.__class__.__name__},
        )

    @app.exception_handler(httpx.RequestError)
    async def handle_request_error(request: Request, exc: httpx.RequestError) -> JSONResponse:
        return error_response(
            request,
            status_code=502,
            code="upstream_request_error",
            message="Gateway failed to reach the upstream service.",
            details={"reason": str(exc) or exc.__class__.__name__},
        )

    @app.exception_handler(GatewayUpstreamResponseError)
    async def handle_upstream_response_error(
        request: Request,
        exc: GatewayUpstreamResponseError,
    ) -> JSONResponse:
        code = "upstream_client_error" if 400 <= exc.status_code < 500 else "upstream_server_error"
        details: dict[str, Any] = {
            "service": exc.service,
            "upstream_status": exc.status_code,
        }
        if exc.body is not None:
            details["upstream_body"] = exc.body
        return error_response(
            request,
            status_code=exc.status_code,
            code=code,
            message="Upstream service returned an error response.",
            details=details,
            headers=exc.headers,
        )
