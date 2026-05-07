from __future__ import annotations

from uuid import uuid4

import httpx

from helpers import register_and_login


async def test_auth_register_login_jwks_and_duplicate_email_contract(
    gateway_client: httpx.AsyncClient,
) -> None:
    email = f"e2e-auth-{uuid4().hex}@example.com"
    password = "testpassword123"

    register_response = await gateway_client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "Researcher",
        },
    )
    assert register_response.status_code == 201, register_response.text
    user = register_response.json()
    assert user["email"] == email
    assert user["role"] == "Researcher"
    assert "password" not in user
    assert "hashed_password" not in user

    duplicate_response = await gateway_client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": "Researcher",
        },
    )
    assert duplicate_response.status_code in {400, 409}, duplicate_response.text

    bad_login_response = await gateway_client.post(
        "/auth/login",
        data={"username": email, "password": "wrong-password"},
    )
    assert bad_login_response.status_code == 401, bad_login_response.text

    login_response = await gateway_client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    token_body = login_response.json()
    assert token_body["token_type"] == "bearer"
    assert token_body["access_token"]

    jwks_response = await gateway_client.get("/auth/jwks")
    assert jwks_response.status_code == 200, jwks_response.text
    jwks = jwks_response.json()
    assert "keys" in jwks
    assert jwks["keys"]


async def test_invalid_registration_payloads_are_rejected(
    gateway_client: httpx.AsyncClient,
) -> None:
    cases = [
        {},
        {"email": "not-an-email", "password": "testpassword123", "role": "Researcher"},
        {"email": f"e2e-{uuid4().hex}@example.com", "password": "x", "role": "Researcher"},
        {"email": f"e2e-{uuid4().hex}@example.com", "password": "testpassword123", "role": "DefinitelyNotARole"},
    ]

    for payload in cases:
        response = await gateway_client.post("/auth/register", json=payload)
        assert response.status_code in {400, 422}, response.text


async def test_token_allows_protected_read_and_invalidates_none_of_the_spoofed_headers(
    gateway_client: httpx.AsyncClient,
) -> None:
    token, user = await register_and_login(gateway_client)
    assert user["role"] == "Researcher"

    response = await gateway_client.get(
        "/search",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Authenticated-Source": "api-gateway",
            "X-Authenticated-User-Role": "Admin",
            "X-Internal-Token": "client-should-not-control-this",
        },
        params={"q": "anything"},
    )

    assert response.status_code == 200, response.text