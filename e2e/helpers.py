from __future__ import annotations

import asyncio
from collections.abc import Mapping
import os
import shutil
import subprocess
from time import monotonic
from uuid import uuid4

import httpx
import pytest

OPENSEARCH_BASE_URL = "http://localhost:9200"
OPENSEARCH_INDEX = "anomaly-wiki-pages"
MINIO_HEALTH_URL = "http://localhost:9000/minio/health/live"


async def register_and_login(
    client: httpx.AsyncClient,
    *,
    requested_role: str = "Researcher",
) -> tuple[str, dict]:
    email = f"e2e-{uuid4()}@example.com"
    password = "testpassword123"

    register_response = await client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "role": requested_role,
        },
    )
    assert register_response.status_code == 201, register_response.text
    user = register_response.json()

    login_response = await client.post(
        "/auth/login",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    body = login_response.json()
    assert body["token_type"] == "bearer"
    return body["access_token"], user


async def create_published_page(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    *,
    slug_prefix: str = "e2e-page",
) -> dict:
    slug = f"{slug_prefix}-{uuid4().hex[:8]}"
    create_response = await client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": "Anomaly",
            "visibility": "Public",
            "title": "E2E Burner Anomaly",
            "summary": "A deterministic page created by the CI smoke test.",
            "content": "Initial field notes for the end-to-end smoke test.",
        },
    )
    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    page_id = created["page"]["id"]

    draft_response = await client.post(
        f"/pages/{page_id}/drafts",
        headers=auth_headers,
        json={
            "expected_page_version": created["page"]["version"],
            "title": "E2E Burner Anomaly Updated",
            "summary": "Updated summary from the CI smoke test.",
            "content": "Updated smoke-test content before publication.",
        },
    )
    assert draft_response.status_code == 201, draft_response.text
    draft = draft_response.json()

    publish_response = await client.post(
        f"/pages/{page_id}/publish",
        headers=auth_headers,
        json={
            "expected_page_version": draft["page"]["version"],
            "revision_id": draft["revision"]["id"],
        },
    )
    assert publish_response.status_code == 200, publish_response.text
    published = publish_response.json()
    published["e2e_slug"] = slug
    return published


async def create_page(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    *,
    slug_prefix: str = "e2e-page",
    title: str = "E2E Page",
    content: str = "E2E page content.",
    summary: str = "",
    type_: str = "Anomaly",
    visibility: str = "Public",
) -> dict:
    slug = f"{slug_prefix}-{uuid4().hex[:8]}"
    response = await client.post(
        "/pages",
        headers=auth_headers,
        json={
            "slug": slug,
            "type": type_,
            "visibility": visibility,
            "title": title,
            "summary": summary,
            "content": content,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    body["e2e_slug"] = slug
    return body


async def create_draft_revision(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    page_state: dict,
    *,
    title: str,
    content: str,
    summary: str = "",
    parent_revision_id: str | None = None,
) -> dict:
    payload = {
        "expected_page_version": page_state["page"]["version"],
        "title": title,
        "summary": summary,
        "content": content,
    }
    if parent_revision_id is not None:
        payload["parent_revision_id"] = parent_revision_id

    response = await client.post(
        f"/pages/{page_state['page']['id']}/drafts",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    if "e2e_slug" in page_state:
        body["e2e_slug"] = page_state["e2e_slug"]
    return body


async def publish_revision(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    page_state: dict,
    *,
    revision_id: str | None = None,
) -> dict:
    response = await client.post(
        f"/pages/{page_state['page']['id']}/publish",
        headers=auth_headers,
        json={
            "expected_page_version": page_state["page"]["version"],
            "revision_id": revision_id or page_state["revision"]["id"],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    if "e2e_slug" in page_state:
        body["e2e_slug"] = page_state["e2e_slug"]
    return body


async def update_page_metadata(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    page_state: dict,
    *,
    tags: list[str] | None = None,
    classifications: list[str] | None = None,
    related_page_ids: list[str] | None = None,
    media_asset_ids: list[str] | None = None,
) -> dict:
    response = await client.put(
        f"/pages/{page_state['page']['id']}/metadata",
        headers=auth_headers,
        json={
            "expected_page_version": page_state["page"]["version"],
            "tags": tags or [],
            "classifications": classifications or [],
            "related_page_ids": related_page_ids or [],
            "media_asset_ids": media_asset_ids or [],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    if "e2e_slug" in page_state:
        body["e2e_slug"] = page_state["e2e_slug"]
    return body


async def transition_page_status(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    page_state: dict,
    *,
    status: str,
) -> dict:
    response = await client.post(
        f"/pages/{page_state['page']['id']}/status",
        headers=auth_headers,
        json={
            "expected_page_version": page_state["page"]["version"],
            "status": status,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    if "e2e_slug" in page_state:
        body["e2e_slug"] = page_state["e2e_slug"]
    return body


async def upload_media_asset(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    *,
    filename: str,
    payload: bytes,
    content_type: str | None = "text/plain",
) -> dict:
    file_value = (filename, payload) if content_type is None else (filename, payload, content_type)
    response = await client.post(
        "/media",
        headers=auth_headers,
        files={"file": file_value},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def download_media_asset(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    asset_id: str,
) -> bytes:
    download_response = await client.get(
        f"/media/{asset_id}/download-url",
        headers=auth_headers,
    )
    assert download_response.status_code == 200, download_response.text
    object_response = await client.get(download_response.json()["url"])
    assert object_response.status_code == 200, object_response.text
    return object_response.content


async def seed_search_document(
    document: dict,
    *,
    doc_id: str | None = None,
) -> str:
    doc_id = doc_id or document["page_id"]
    async with httpx.AsyncClient(base_url=OPENSEARCH_BASE_URL, timeout=20.0) as client:
        response = await client.put(f"/{OPENSEARCH_INDEX}/_doc/{doc_id}", json=document)
        assert response.status_code in {200, 201}, response.text
        refresh_response = await client.post(f"/{OPENSEARCH_INDEX}/_refresh")
        assert refresh_response.status_code == 200, refresh_response.text
    return doc_id


def search_document(
    *,
    page_id: str | None = None,
    slug: str | None = None,
    title: str = "E2E Seeded Burner",
    status: str = "Published",
    visibility: str = "Public",
    tags: list[str] | None = None,
    type_: str = "Anomaly",
    aliases: list[str] | None = None,
) -> dict:
    page_id = page_id or str(uuid4())
    slug = slug or f"e2e-search-{uuid4().hex[:8]}"
    return {
        "page_id": page_id,
        "slug": slug,
        "type": type_,
        "status": status,
        "visibility": visibility,
        "tags": tags or ["e2e"],
        "title": title,
        "summary": f"Search fixture for {title}",
        "content_text": f"{title} searchable content for the full E2E suite.",
        "aliases": aliases or [],
    }


async def wait_for_search_hit(
    client: httpx.AsyncClient,
    *,
    slug: str,
    q: str,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
) -> dict:
    deadline = monotonic() + timeout_seconds
    last_body: dict | None = None
    query_params = {"q": q, **dict(params or {})}

    while monotonic() <= deadline:
        response = await client.get("/search", headers=headers, params=query_params)
        assert response.status_code == 200, response.text
        last_body = response.json()
        for hit in last_body["hits"]:
            if hit["slug"] == slug:
                return hit
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Search hit for slug {slug} did not appear. Last body: {last_body}")


async def wait_for_search_absence(
    client: httpx.AsyncClient,
    *,
    slug: str,
    q: str,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_body: dict | None = None
    query_params = {"q": q, **dict(params or {})}

    while monotonic() <= deadline:
        response = await client.get("/search", headers=headers, params=query_params)
        assert response.status_code == 200, response.text
        last_body = response.json()
        if all(hit["slug"] != slug for hit in last_body["hits"]):
            return
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Search hit for slug {slug} still appeared. Last body: {last_body}")


def assert_gateway_error(response: httpx.Response, status_code: int, code: str) -> dict:
    assert response.status_code == status_code, response.text
    body = response.json()
    assert body["error"]["code"] == code
    return body


async def wait_for_gateway_ready(
    client: httpx.AsyncClient,
    *,
    timeout_seconds: float = 90.0,
    interval_seconds: float = 2.0,
) -> dict:
    deadline = monotonic() + timeout_seconds
    last_body: dict | None = None

    while monotonic() <= deadline:
        response = await client.get("/ready")
        if response.status_code == 200:
            body = response.json()
            if body["status"] == "ok":
                return body
            last_body = body
        else:
            try:
                last_body = response.json()
            except ValueError:
                last_body = {"body": response.text}
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Gateway did not become ready. Last body: {last_body}")


async def wait_for_gateway_degraded(
    client: httpx.AsyncClient,
    *,
    service_name: str,
    timeout_seconds: float = 60.0,
    interval_seconds: float = 2.0,
) -> dict:
    deadline = monotonic() + timeout_seconds
    last_body: dict | None = None

    while monotonic() <= deadline:
        response = await client.get("/ready")
        if response.status_code == 503:
            body = response.json()
            last_body = body
            service = body.get("services", {}).get(service_name)
            if body.get("status") == "degraded" and service and service.get("status") == "error":
                return body
        else:
            try:
                last_body = response.json()
            except ValueError:
                last_body = {"body": response.text}
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Gateway did not report {service_name} degraded. Last body: {last_body}")


async def wait_for_url_ok(
    url: str,
    *,
    timeout_seconds: float = 120.0,
    interval_seconds: float = 2.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_error: str | None = None

    async with httpx.AsyncClient(timeout=10.0) as client:
        while monotonic() <= deadline:
            try:
                response = await client.get(url)
                if 200 <= response.status_code < 300:
                    return
                last_error = f"{response.status_code}: {response.text}"
            except httpx.HTTPError as exc:
                last_error = repr(exc)
            await asyncio.sleep(interval_seconds)

    raise AssertionError(f"{url} did not become ready. Last error: {last_error}")


async def wait_for_search_available(
    client: httpx.AsyncClient,
    *,
    timeout_seconds: float = 120.0,
    interval_seconds: float = 2.0,
) -> None:
    deadline = monotonic() + timeout_seconds
    last_body: dict | str | None = None

    while monotonic() <= deadline:
        response = await client.get("/search", params={"q": "recovery"})
        if response.status_code == 200:
            return
        try:
            last_body = response.json()
        except ValueError:
            last_body = response.text
        await asyncio.sleep(interval_seconds)

    raise AssertionError(f"Search did not become available. Last body: {last_body}")


def _compose_env() -> dict[str, str]:
    if shutil.which("docker") is None:
        pytest.skip("Docker CLI is required for controlled outage E2E tests.")
    project_name = os.getenv("COMPOSE_PROJECT_NAME")
    internal_token = os.getenv("INTERNAL_TOKEN")
    if not project_name or not internal_token:
        pytest.skip("COMPOSE_PROJECT_NAME and INTERNAL_TOKEN are required for controlled outage E2E tests.")

    env = os.environ.copy()
    env["COMPOSE_PROJECT_NAME"] = project_name
    env["INTERNAL_TOKEN"] = internal_token
    return env


def _run_compose(*args: str) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["docker", "compose", *args],
            check=True,
            capture_output=True,
            text=True,
            env=_compose_env(),
            timeout=120,
        )
    except PermissionError as exc:
        pytest.skip(f"Docker daemon is not accessible: {exc}")
    except subprocess.CalledProcessError as exc:
        raise AssertionError(
            f"docker compose {' '.join(args)} failed with exit {exc.returncode}\n"
            f"stdout:\n{exc.stdout}\n\nstderr:\n{exc.stderr}"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(f"docker compose {' '.join(args)} timed out") from exc


def compose_stop(service: str) -> None:
    _run_compose("stop", service)


def compose_up(service: str) -> None:
    _run_compose("up", "-d", service)
