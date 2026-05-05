from __future__ import annotations

import os
from collections.abc import AsyncIterator

import httpx
import pytest

from helpers import register_and_login


GATEWAY_BASE_URL = os.getenv("E2E_GATEWAY_BASE_URL", "http://localhost:8000")


@pytest.fixture
async def gateway_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(base_url=GATEWAY_BASE_URL, timeout=30.0) as client:
        yield client


@pytest.fixture
async def researcher_token(gateway_client: httpx.AsyncClient) -> str:
    token, user = await register_and_login(gateway_client)
    assert user["role"] == "Researcher"
    return token


@pytest.fixture
def auth_headers(researcher_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {researcher_token}"}
