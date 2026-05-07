from __future__ import annotations

import httpx
from uuid import uuid4

from helpers import register_and_login


async def test_self_registration_cannot_claim_admin_role(
    gateway_client: httpx.AsyncClient,
) -> None:
    token, user = await register_and_login(gateway_client, requested_role="Admin")

    assert token
    assert user["role"] == "Researcher"


async def test_researcher_role_can_use_current_protected_content_flow(
    gateway_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    response = await gateway_client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": f"e2e-role-researcher-{uuid4().hex[:8]}",
            "type": "Anomaly",
            "visibility": "Public",
            "title": "Researcher Role E2E",
            "content": "Current policy allows authenticated researchers to create pages.",
        },
    )

    assert response.status_code in {201, 409}, response.text
