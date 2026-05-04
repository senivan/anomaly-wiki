import json
from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import Response
from pydantic import AnyHttpUrl

from config import Settings
from errors import GatewayUpstreamResponseError
from errors import REQUEST_ID_HEADER
from security import AuthContext

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

DOWNSTREAM_AUTH_USER_ID_HEADER = "X-Authenticated-User-Id"
DOWNSTREAM_AUTH_USER_EMAIL_HEADER = "X-Authenticated-User-Email"
DOWNSTREAM_AUTH_USER_ROLE_HEADER = "X-Authenticated-User-Role"
DOWNSTREAM_AUTH_SOURCE_HEADER = "X-Authenticated-Source"

PROTECTED_FORWARD_STRIP_HEADERS = {
    "authorization",
    DOWNSTREAM_AUTH_USER_ID_HEADER.lower(),
    DOWNSTREAM_AUTH_USER_EMAIL_HEADER.lower(),
    DOWNSTREAM_AUTH_USER_ROLE_HEADER.lower(),
    DOWNSTREAM_AUTH_SOURCE_HEADER.lower(),
    "x-internal-token",
}


def _filtered_headers(
    headers: Mapping[str, str],
    *,
    extra_excluded: set[str] | None = None,
) -> dict[str, str]:
    excluded = HOP_BY_HOP_HEADERS | (extra_excluded or set())
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in excluded
    }


def _error_body(response: httpx.Response) -> Any:
    if not response.content:
        return None
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    try:
        return json.loads(response.text)
    except json.JSONDecodeError:
        return response.text


async def forward_request(
    request: Request,
    *,
    service: str,
    upstream_base_url: AnyHttpUrl,
    upstream_path: str,
    settings: Settings,
    forwarded_headers: Mapping[str, str] | None = None,
    excluded_headers: set[str] | None = None,
) -> Response:
    transport = getattr(request.app.state, "upstream_transport", None)
    request_headers = _filtered_headers(
        request.headers,
        extra_excluded=excluded_headers,
    )
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        request_headers[REQUEST_ID_HEADER] = request_id
    if forwarded_headers:
        request_headers.update(dict(forwarded_headers))

    async with httpx.AsyncClient(
        base_url=str(upstream_base_url),
        timeout=settings.upstream_timeout_seconds,
        transport=transport,
        follow_redirects=False,
    ) as client:
        upstream_response = await client.request(
            method=request.method,
            url=upstream_path,
            params=request.query_params,
            content=await request.body(),
            headers=request_headers,
        )

    response_headers = _filtered_headers(upstream_response.headers)
    if upstream_response.status_code >= 400:
        raise GatewayUpstreamResponseError(
            service=service,
            status_code=upstream_response.status_code,
            body=_error_body(upstream_response),
            headers=response_headers,
        )

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


def build_authenticated_forward_headers(auth: AuthContext) -> dict[str, str]:
    headers = {
        DOWNSTREAM_AUTH_USER_ID_HEADER: auth.subject,
        DOWNSTREAM_AUTH_SOURCE_HEADER: "api-gateway",
    }
    if auth.email:
        headers[DOWNSTREAM_AUTH_USER_EMAIL_HEADER] = auth.email
    if auth.role:
        headers[DOWNSTREAM_AUTH_USER_ROLE_HEADER] = auth.role
    return headers


async def forward_authenticated_request(
    request: Request,
    *,
    auth: AuthContext,
    service: str,
    upstream_base_url: AnyHttpUrl,
    upstream_path: str,
    settings: Settings,
) -> Response:
    return await forward_request(
        request,
        service=service,
        upstream_base_url=upstream_base_url,
        upstream_path=upstream_path,
        settings=settings,
        forwarded_headers=build_authenticated_forward_headers(auth),
        excluded_headers=PROTECTED_FORWARD_STRIP_HEADERS,
    )
