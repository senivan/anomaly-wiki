import json
from collections.abc import Mapping
from typing import Any

import httpx
from fastapi import Request
from fastapi.responses import Response
from pydantic import AnyHttpUrl

from config import Settings
from errors import GatewayUpstreamResponseError

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


def _filtered_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS
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
) -> Response:
    transport = getattr(request.app.state, "upstream_transport", None)
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
            headers=_filtered_headers(request.headers),
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
