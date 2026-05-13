"""
Cross-service integration tests for anomaly-wiki.

Each test wires the API Gateway to mock ASGI implementations of all downstream
services using httpx.ASGITransport.  No external infrastructure
(PostgreSQL, MinIO, OpenSearch, RabbitMQ) is required.

Run with:
    cd services/api-gateway
    pytest tests/test_cross_service_integration.py -v -s

The -s flag lets pytest print the inter-service communication log to the
terminal so you can follow each request hop.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from main import create_app
from security import jwk_from_public_numbers

# -- RSA key helpers -----------------------------------------------------------


def _generate_keypair():
    """Generate a fresh RSA-2048 keypair and return (private_key, jwk_dict)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    numbers = private_key.public_key().public_numbers()
    jwk = jwk_from_public_numbers(numbers.n, numbers.e, kid="test-key-1")
    return private_key, jwk


def _issue_token(
    private_key,
    *,
    role: str = "Researcher",
    email: str = "user@zone.ua",
    subject: str | None = None,
    expires_in: int = 300,
) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": subject or str(uuid4()),
            "email": email,
            "role": role,
            "aud": "fastapi-users:auth",
            "iat": now,
            "exp": now + timedelta(seconds=expires_in),
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key-1"},
    )


# -- mock cluster --------------------------------------------------------------


def build_mock_cluster(private_key, jwk: dict) -> FastAPI:
    """
    A single in-process ASGI app that mocks all downstream services.

    When ASGITransport is used, httpx ignores the Host header and routes
    only by path.  The gateway sends requests to four different base-URL
    values (auth / encyclopedia / media / search), but they all arrive here
    differentiated by path alone.

    The app stores in-memory state on app.state so individual tests can
    inspect or seed data after construction.
    """
    app = FastAPI(title="Mock Service Cluster")

    pages: dict[str, dict] = {}
    revisions: dict[str, dict] = {}
    assets: dict[str, dict] = {}
    search_index: list[dict] = []

    app.state.pages = pages
    app.state.revisions = revisions
    app.state.assets = assets
    app.state.search_index = search_index

    # -- researcher-auth-service -----------------------------------------------

    @app.get("/auth/jwks")
    async def auth_jwks() -> JSONResponse:
        print(f"\n    [auth-service] GET /auth/jwks  ->  1 RSA key (kid={jwk['kid']})")
        return JSONResponse({"keys": [jwk]})

    @app.post("/auth/register")
    async def auth_register(request: Request) -> JSONResponse:
        body = await request.json()
        user_id = str(uuid4())
        email = body.get("email", "unknown@zone.ua")
        print(f"\n    [auth-service] POST /auth/register  ->  created {email} ({user_id[:8]}...)")
        return JSONResponse(
            status_code=201,
            content={"id": user_id, "email": email, "is_active": True},
        )

    @app.post("/auth/login")
    async def auth_login(request: Request) -> JSONResponse:
        body = await request.json()
        email = body.get("username", "stalker@zone.ua")
        token = _issue_token(private_key, email=email, role="Researcher")
        print(f"\n    [auth-service] POST /auth/login  ->  issued JWT for {email}")
        return JSONResponse({"access_token": token, "token_type": "bearer"})

    # -- encyclopedia-service --------------------------------------------------

    @app.post("/pages")
    async def enc_create_page(request: Request) -> JSONResponse:
        body = await request.json()
        page_id = str(uuid4())
        rev_id = str(uuid4())
        author_id = request.headers.get("x-authenticated-user-id", str(uuid4()))
        source = request.headers.get("x-authenticated-source", "?")
        role = request.headers.get("x-authenticated-user-role", "?")
        now = datetime.now(timezone.utc).isoformat()
        revision = {
            "id": rev_id,
            "page_id": page_id,
            "parent_revision_id": None,
            "author_id": author_id,
            "title": body["title"],
            "summary": body.get("summary", ""),
            "content": body["content"],
            "created_at": now,
        }
        page = {
            "id": page_id,
            "slug": body["slug"],
            "type": body["type"],
            "status": "Draft",
            "visibility": body.get("visibility", "Internal"),
            "current_draft_revision_id": rev_id,
            "current_published_revision_id": None,
            "version": 1,
            "tags": [],
            "classifications": [],
            "related_page_ids": [],
            "media_asset_ids": [],
            "created_at": now,
            "updated_at": now,
        }
        pages[page_id] = page
        revisions[rev_id] = revision
        print(
            f"\n    [encyclopedia-service] POST /pages"
            f"  ->  created '{body['slug']}' (id={page_id[:8]}...)"
            f"  source={source} role={role}"
        )
        return JSONResponse(status_code=201, content={"page": page, "revision": revision})

    @app.get("/pages/{page_id}")
    async def enc_get_page(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": f"Page {page_id} not found"})
        draft_rev = revisions.get(page.get("current_draft_revision_id") or "")
        pub_rev = revisions.get(page.get("current_published_revision_id") or "")
        role = request.headers.get("x-authenticated-user-role", "?")
        print(
            f"\n    [encyclopedia-service] GET /pages/{page_id[:8]}..."
            f"  ->  '{page['slug']}' status={page['status']} role={role}"
        )
        return JSONResponse(
            {
                "page": page,
                "current_draft_revision": draft_rev,
                "current_published_revision": pub_rev,
            }
        )

    @app.post("/pages/{page_id}/drafts")
    async def enc_create_draft(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        body = await request.json()
        rev_id = str(uuid4())
        author_id = request.headers.get("x-authenticated-user-id", str(uuid4()))
        parent_id = body.get("parent_revision_id") or page["current_draft_revision_id"]
        now = datetime.now(timezone.utc).isoformat()
        revision = {
            "id": rev_id,
            "page_id": page_id,
            "parent_revision_id": parent_id,
            "author_id": author_id,
            "title": body["title"],
            "summary": body.get("summary", ""),
            "content": body["content"],
            "created_at": now,
        }
        revisions[rev_id] = revision
        page["current_draft_revision_id"] = rev_id
        page["version"] += 1
        print(
            f"\n    [encyclopedia-service] POST /pages/{page_id[:8]}.../drafts"
            f"  ->  rev={rev_id[:8]}... parent={str(parent_id or '')[:8]}..."
            f"  version={page['version']}"
        )
        return JSONResponse(status_code=201, content={"page": page, "revision": revision})

    @app.get("/pages/{page_id}/revisions")
    async def enc_list_revisions(page_id: str) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        page_revisions = [r for r in revisions.values() if r["page_id"] == page_id]
        print(
            f"\n    [encyclopedia-service] GET /pages/{page_id[:8]}.../revisions"
            f"  ->  {len(page_revisions)} revision(s)"
        )
        return JSONResponse({"page": page, "revisions": page_revisions})

    @app.get("/pages/{page_id}/revisions/{revision_id}")
    async def enc_get_revision(page_id: str, revision_id: str) -> JSONResponse:
        page = pages.get(page_id)
        revision = revisions.get(revision_id)
        if not page or not revision:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        lineage: list[dict] = []
        cur = revision.get("parent_revision_id")
        while cur and cur in revisions:
            lineage.append(revisions[cur])
            cur = revisions[cur].get("parent_revision_id")
        print(
            f"\n    [encyclopedia-service] GET .../{revision_id[:8]}..."
            f"  ->  lineage depth {len(lineage)}"
        )
        return JSONResponse({"page": page, "revision": revision, "lineage": lineage})

    @app.put("/pages/{page_id}/metadata")
    async def enc_update_metadata(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        body = await request.json()
        page["tags"] = body.get("tags", [])
        page["classifications"] = body.get("classifications", [])
        page["related_page_ids"] = body.get("related_page_ids", [])
        page["media_asset_ids"] = body.get("media_asset_ids", [])
        print(
            f"\n    [encyclopedia-service] PUT /pages/{page_id[:8]}.../metadata"
            f"  ->  tags={page['tags']} media_refs={len(page['media_asset_ids'])}"
        )
        return JSONResponse({"page": page})

    @app.post("/pages/{page_id}/publish")
    async def enc_publish(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        body = await request.json()
        rev_id = body.get("revision_id")
        role = request.headers.get("x-authenticated-user-role", "?")
        page["status"] = "Published"
        page["current_published_revision_id"] = rev_id
        print(
            f"\n    [encyclopedia-service] POST /pages/{page_id[:8]}.../publish"
            f"  ->  rev={str(rev_id or '')[:8]}... by role={role}"
        )
        return JSONResponse({"page": page})

    @app.post("/pages/{page_id}/revert")
    async def enc_revert(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        body = await request.json()
        target_rev_id = body.get("revision_id")
        target = revisions.get(target_rev_id or "")
        if not target:
            return JSONResponse(status_code=404, content={"detail": "Revision not found"})
        new_rev_id = str(uuid4())
        author_id = request.headers.get("x-authenticated-user-id", str(uuid4()))
        now = datetime.now(timezone.utc).isoformat()
        new_rev = {
            "id": new_rev_id,
            "page_id": page_id,
            "parent_revision_id": page["current_draft_revision_id"],
            "author_id": author_id,
            "title": target["title"],
            "summary": target["summary"],
            "content": target["content"],
            "created_at": now,
        }
        revisions[new_rev_id] = new_rev
        page["current_draft_revision_id"] = new_rev_id
        page["version"] += 1
        print(
            f"\n    [encyclopedia-service] POST /pages/{page_id[:8]}.../revert"
            f"  ->  new_rev={new_rev_id[:8]}... (copy of {str(target_rev_id or '')[:8]}...)"
        )
        return JSONResponse(status_code=201, content={"page": page, "revision": new_rev})

    @app.post("/pages/{page_id}/status")
    async def enc_status_transition(page_id: str, request: Request) -> JSONResponse:
        page = pages.get(page_id)
        if not page:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        body = await request.json()
        old_status = page["status"]
        page["status"] = body["status"]
        print(
            f"\n    [encyclopedia-service] POST /pages/{page_id[:8]}.../status"
            f"  ->  {old_status} -> {page['status']}"
        )
        return JSONResponse({"page": page})

    # -- media-service ---------------------------------------------------------

    @app.post("/media")
    async def media_upload(request: Request) -> JSONResponse:
        form = await request.form()
        file = form.get("file")
        asset_id = str(uuid4())
        uploader = request.headers.get("x-authenticated-user-id", "unknown")
        source = request.headers.get("x-authenticated-source", "?")
        now = datetime.now(timezone.utc).isoformat()
        filename = getattr(file, "filename", "upload.bin") if file else "upload.bin"
        content_type = (
            getattr(file, "content_type", "application/octet-stream") if file else "application/octet-stream"
        )
        data = await file.read() if file else b""
        import hashlib
        checksum = hashlib.sha256(data).hexdigest()
        asset = {
            "id": asset_id,
            "filename": filename,
            "mime_type": content_type,
            "storage_path": f"assets/{asset_id}/{filename}",
            "uploaded_by": uploader,
            "size_bytes": len(data),
            "checksum_sha256": checksum,
            "created_at": now,
            "updated_at": now,
        }
        assets[asset_id] = asset
        print(
            f"\n    [media-service] POST /media"
            f"  ->  '{filename}' ({len(data)} bytes, {content_type})"
            f"  asset_id={asset_id[:8]}...  source={source}"
        )
        return JSONResponse(status_code=201, content=asset)

    @app.get("/media/{asset_id}")
    async def media_get(asset_id: str, request: Request) -> JSONResponse:
        asset = assets.get(asset_id)
        if not asset:
            return JSONResponse(status_code=404, content={"detail": f"Asset {asset_id} not found"})
        role = request.headers.get("x-authenticated-user-role", "?")
        print(
            f"\n    [media-service] GET /media/{asset_id[:8]}..."
            f"  ->  '{asset['filename']}' ({asset['size_bytes']} bytes)"
            f"  role={role}"
        )
        return JSONResponse(asset)

    @app.get("/media/{asset_id}/download-url")
    async def media_download_url(asset_id: str, request: Request) -> JSONResponse:
        asset = assets.get(asset_id)
        if not asset:
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        signed_url = f"http://minio:9000/anomaly-wiki/{asset['storage_path']}?sig=mock-sig-{asset_id[:8]}"
        expires = 900
        print(
            f"\n    [media-service] GET /media/{asset_id[:8]}.../download-url"
            f"  ->  signed URL (TTL={expires}s)"
        )
        return JSONResponse({"asset_id": asset_id, "url": signed_url, "expires_in_seconds": expires})

    # -- search-service --------------------------------------------------------

    @app.get("/search")
    async def search_query(request: Request) -> JSONResponse:
        q = request.query_params.get("q", "").lower()
        source = request.headers.get("x-authenticated-source")
        role = request.headers.get("x-authenticated-user-role")
        auth_source = request.headers.get("x-authenticated-source")
        is_internal = auth_source == "api-gateway" and (role or "").lower() in {
            "researcher", "editor", "admin"
        }

        hits = [
            doc
            for doc in search_index
            if q in doc.get("title", "").lower() or q in doc.get("summary", "").lower()
        ]
        if not is_internal:
            hits = [h for h in hits if h.get("visibility") == "Public" and h.get("status") == "Published"]

        print(
            f"\n    [search-service] GET /search?q={q!r}"
            f"  ->  {len(hits)} hit(s)  internal={is_internal}  source={source} role={role}"
        )
        return JSONResponse({"total": len(hits), "hits": hits})

    @app.get("/search/suggest")
    async def search_suggest(request: Request) -> JSONResponse:
        q = request.query_params.get("q", "").lower()
        suggestions = [
            doc["title"]
            for doc in search_index
            if doc.get("title", "").lower().startswith(q)
        ][:5]
        print(
            f"\n    [search-service] GET /search/suggest?q={q!r}"
            f"  ->  {suggestions}"
        )
        return JSONResponse({"suggestions": suggestions})

    return app


# -- pytest fixtures -----------------------------------------------------------


@pytest.fixture
def keypair():
    return _generate_keypair()


@pytest.fixture
def cluster(keypair):
    private_key, jwk = keypair
    return build_mock_cluster(private_key, jwk)


@pytest.fixture
def gateway(cluster, keypair):
    _, jwk = keypair
    gw = create_app(upstream_transport=ASGITransport(app=cluster))
    gw.state.jwks_cache._keys = [jwk]
    gw.state.jwks_cache._expires_at = 10**12
    return gw


# -- tests ---------------------------------------------------------------------


async def test_gateway_fetches_jwks_from_auth_service_on_first_request(cluster, keypair):
    """
    Flow: Client -> Gateway -> Auth Service (JWKS fetch) -> Gateway validates token

    When the JWKS cache is empty the gateway fetches the public key from the
    auth service's /auth/jwks endpoint before validating any bearer token.
    After a successful fetch the cache is populated and subsequent requests
    skip the round-trip.
    """
    private_key, jwk = keypair
    user_id = str(uuid4())
    token = _issue_token(private_key, subject=user_id, role="Researcher")

    gw = create_app(upstream_transport=ASGITransport(app=cluster))
    assert gw.state.jwks_cache._keys == [], "cache must start empty"

    print("\n\n" + "=" * 70)
    print("TEST: Gateway fetches JWKS from Auth Service on first request")
    print("=" * 70)
    print(f"\n  Client has bearer token (sub={user_id[:8]}..., role=Researcher)")
    print("  Gateway JWKS cache: EMPTY -> must fetch from auth-service")

    async with AsyncClient(transport=ASGITransport(app=gw), base_url="http://test") as client:
        print("\n  [client] -> Gateway: GET /pages/<non-existent>  (first authenticated request)")
        resp = await client.get(
            "/pages/11111111-1111-1111-1111-111111111111",
            headers={"Authorization": f"Bearer {token}"},
        )

    print(f"\n  [client] <- Gateway: {resp.status_code}")
    assert len(gw.state.jwks_cache._keys) == 1, "cache must be populated after first request"
    print(f"  Gateway JWKS cache after request: {len(gw.state.jwks_cache._keys)} key(s)  [OK]")
    # 404 because the page doesn't exist in the mock store
    assert resp.status_code == 404
    print("  (404 is expected - page not found in mock encyclopedia store)")


async def test_registration_and_login_proxied_through_gateway(cluster, keypair):
    """
    Flow: Client -> Gateway -> Auth Service (register) -> Gateway -> Auth Service (login) -> JWT

    The gateway transparently proxies unauthenticated auth requests to the
    researcher-auth-service without attaching identity headers.
    """
    private_key, _ = keypair
    gw = create_app(upstream_transport=ASGITransport(app=cluster))

    print("\n\n" + "=" * 70)
    print("TEST: Registration and Login via Gateway -> Auth Service")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gw), base_url="http://test") as client:
        print("\n  [client] -> Gateway: POST /auth/register")
        reg = await client.post(
            "/auth/register",
            json={"email": "stalker@zone.ua", "password": "Electr0Zone!"},
        )
        print(f"  [client] <- Gateway <- auth-service: {reg.status_code}  {reg.json()}")
        assert reg.status_code == 201
        assert reg.json()["email"] == "stalker@zone.ua"

        print("\n  [client] -> Gateway: POST /auth/login")
        login = await client.post(
            "/auth/login",
            json={"username": "stalker@zone.ua", "password": "Electr0Zone!"},
        )
        print(f"  [client] <- Gateway <- auth-service: {login.status_code}")
        assert login.status_code == 200
        token = login.json()["access_token"]
        assert token
        print(f"  access_token (first 60 chars): {token[:60]}...")

    print("\n  Registration + login flow complete  [OK]")


async def test_page_creation_gateway_injects_identity_headers(gateway, cluster, keypair):
    """
    Flow: Client -> Gateway (JWT validation + header injection) -> Encyclopedia Service

    The gateway validates the bearer token, strips any client-supplied
    identity headers, injects correct X-Authenticated-* headers from the
    validated JWT claims, and forwards to the encyclopedia-service.
    """
    private_key, _ = keypair
    user_id = str(uuid4())
    token = _issue_token(
        private_key, subject=user_id, email="researcher@zone.ua", role="Researcher"
    )

    print("\n\n" + "=" * 70)
    print("TEST: Page Creation - Gateway Injects Identity Headers")
    print("=" * 70)
    print(f"\n  JWT claims: sub={user_id[:8]}... email=researcher@zone.ua role=Researcher")
    print("  Client also sends spoofed X-Authenticated-User-Id and X-Authenticated-User-Role")

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        print("\n  [client] -> Gateway: POST /pages  (with spoofed identity headers + valid JWT)")
        resp = await client.post(
            "/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Authenticated-User-Id": "00000000-0000-0000-0000-000000000000",
                "X-Authenticated-User-Role": "Admin",
                "X-Authenticated-Source": "evil-client",
            },
            json={
                "slug": "bloodsucker-den",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Bloodsucker Den",
                "summary": "Dangerous anomalous zone near Agroprom",
                "content": "# Bloodsucker Den\n\nHigh density of psi-active organisms...",
            },
        )

    print(f"\n  [client] <- Gateway <- encyclopedia-service: {resp.status_code}")
    assert resp.status_code == 201
    body = resp.json()

    stored_author = body["revision"]["author_id"]
    print(f"\n  encyclopedia-service received author_id = {stored_author}")
    assert stored_author == user_id, (
        f"author_id must come from JWT sub ({user_id[:8]}...), "
        f"not the spoofed header (00000000...)"
    )
    print("  Spoofed headers correctly replaced by JWT-derived values  [OK]")
    print(f"  Page created: slug={body['page']['slug']} status={body['page']['status']}")


async def test_full_editorial_lifecycle_draft_review_publish(gateway, cluster, keypair):
    """
    Flow:
      Researcher -> Gateway -> Encyclopedia: POST /pages (Draft)
      Researcher -> Gateway -> Encyclopedia: POST /pages/{id}/drafts (new revision)
      Researcher -> Gateway -> Encyclopedia: POST /pages/{id}/status -> Review
      Editor     -> Gateway -> Encyclopedia: POST /pages/{id}/publish -> Published
      Editor     -> Gateway -> Encyclopedia: GET  /pages/{id} (verify final state)

    This is the core editorial workflow described in MICROSERVICE_ARCH.md §3.
    """
    private_key, _ = keypair
    researcher_id = str(uuid4())
    editor_id = str(uuid4())
    researcher_token = _issue_token(
        private_key, subject=researcher_id, email="fox@zone.ua", role="Researcher"
    )
    editor_token = _issue_token(
        private_key, subject=editor_id, email="editor@zone.ua", role="Editor"
    )

    print("\n\n" + "=" * 70)
    print("TEST: Full Editorial Lifecycle  Draft -> Review -> Published")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:

        # -- Step 1: Researcher creates the initial draft ----------------------
        print("\n  STEP 1 - Researcher creates initial draft")
        print("  [researcher] -> Gateway: POST /pages")
        r1 = await client.post(
            "/pages",
            headers={"Authorization": f"Bearer {researcher_token}"},
            json={
                "slug": "electro-anomaly",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Electro Anomaly",
                "summary": "High-voltage discharge field",
                "content": "# Electro\n\nGenerates powerful electrical discharges.",
            },
        )
        assert r1.status_code == 201
        page_id = r1.json()["page"]["id"]
        page_version = r1.json()["page"]["version"]
        rev1_id = r1.json()["revision"]["id"]
        print(
            f"  [researcher] <- {r1.status_code}:"
            f" page={page_id[:8]}... v{page_version}"
            f" rev={rev1_id[:8]}... status=Draft"
        )

        # -- Step 2: Researcher creates an updated draft revision --------------
        print("\n  STEP 2 - Researcher refines the draft (new revision)")
        print(f"  [researcher] -> Gateway: POST /pages/{page_id[:8]}.../drafts")
        r2 = await client.post(
            f"/pages/{page_id}/drafts",
            headers={"Authorization": f"Bearer {researcher_token}"},
            json={
                "expected_page_version": page_version,
                "title": "Electro Anomaly (revised)",
                "summary": "High-voltage discharge field near Yantar",
                "content": "# Electro\n\nRevised: discharges detected near Yantar lab perimeter.",
                "parent_revision_id": rev1_id,
            },
        )
        assert r2.status_code == 201
        rev2_id = r2.json()["revision"]["id"]
        page_version = r2.json()["page"]["version"]
        print(
            f"  [researcher] <- {r2.status_code}:"
            f" new_rev={rev2_id[:8]}...  parent={rev1_id[:8]}...  v{page_version}"
        )

        # -- Step 3: Researcher submits for review -----------------------------
        print("\n  STEP 3 - Researcher submits page for editorial review")
        print(f"  [researcher] -> Gateway: POST /pages/{page_id[:8]}.../status  (-> Review)")
        r3 = await client.post(
            f"/pages/{page_id}/status",
            headers={"Authorization": f"Bearer {researcher_token}"},
            json={"expected_page_version": page_version, "status": "Review"},
        )
        assert r3.status_code == 200
        page_version = r3.json()["page"]["version"]
        print(
            f"  [researcher] <- {r3.status_code}:"
            f" status={r3.json()['page']['status']}  v{page_version}"
        )

        # -- Step 4: Editor publishes ------------------------------------------
        print("\n  STEP 4 - Editor publishes the page")
        print(f"  [editor] -> Gateway: POST /pages/{page_id[:8]}.../publish")
        r4 = await client.post(
            f"/pages/{page_id}/publish",
            headers={"Authorization": f"Bearer {editor_token}"},
            json={"expected_page_version": page_version, "revision_id": rev2_id},
        )
        assert r4.status_code == 200
        print(
            f"  [editor] <- {r4.status_code}:"
            f" status={r4.json()['page']['status']}"
            f" published_rev={str(r4.json()['page']['current_published_revision_id'] or '')[:8]}..."
        )
        assert r4.json()["page"]["status"] == "Published"

        # -- Step 5: Read final state ------------------------------------------
        print("\n  STEP 5 - Read the final page state")
        print(f"  [editor] -> Gateway: GET /pages/{page_id[:8]}...")
        r5 = await client.get(
            f"/pages/{page_id}",
            headers={"Authorization": f"Bearer {editor_token}"},
        )
        assert r5.status_code == 200
        final_page = r5.json()["page"]
        pub_rev = r5.json()["current_published_revision"]
        print(
            f"  [editor] <- {r5.status_code}:"
            f" slug={final_page['slug']}"
            f" status={final_page['status']}"
            f" published_rev_title={pub_rev['title'] if pub_rev else None}"
        )
        assert final_page["status"] == "Published"
        assert final_page["current_published_revision_id"] == rev2_id

    print("\n  Full editorial lifecycle complete  [OK]")


async def test_revision_history_linked_list_structure(gateway, cluster, keypair):
    """
    Flow: Create page + 2 more draft revisions -> list revisions -> inspect lineage

    Verifies that the encyclopedia-service maintains a Git-like linked list of
    revisions accessible through the gateway.
    """
    private_key, _ = keypair
    token = _issue_token(private_key, role="Researcher")

    print("\n\n" + "=" * 70)
    print("TEST: Revision History - Linked-List Structure via Gateway")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        r1 = await client.post(
            "/pages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": "burner-field",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Burner Field v1",
                "summary": "",
                "content": "# Burner v1",
            },
        )
        assert r1.status_code == 201
        page_id = r1.json()["page"]["id"]
        rev1_id = r1.json()["revision"]["id"]
        v = r1.json()["page"]["version"]
        print(f"\n  rev1 = {rev1_id[:8]}...  (initial, parent=None)  v{v}")

        r2 = await client.post(
            f"/pages/{page_id}/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "expected_page_version": v,
                "title": "Burner Field v2",
                "content": "# Burner v2",
                "parent_revision_id": rev1_id,
            },
        )
        assert r2.status_code == 201
        rev2_id = r2.json()["revision"]["id"]
        v = r2.json()["page"]["version"]
        print(f"  rev2 = {rev2_id[:8]}...  parent={rev1_id[:8]}...  v{v}")

        r3 = await client.post(
            f"/pages/{page_id}/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "expected_page_version": v,
                "title": "Burner Field v3",
                "content": "# Burner v3",
                "parent_revision_id": rev2_id,
            },
        )
        assert r3.status_code == 201
        rev3_id = r3.json()["revision"]["id"]
        v = r3.json()["page"]["version"]
        print(f"  rev3 = {rev3_id[:8]}...  parent={rev2_id[:8]}...  v{v}")

        print(f"\n  [client] -> Gateway: GET /pages/{page_id[:8]}.../revisions")
        list_resp = await client.get(
            f"/pages/{page_id}/revisions",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_resp.status_code == 200
        all_revs = {r["id"]: r for r in list_resp.json()["revisions"]}
        print(f"  [client] <- {list_resp.status_code}: {len(all_revs)} revision(s)")
        assert len(all_revs) == 3

        assert all_revs[rev1_id]["parent_revision_id"] is None
        assert all_revs[rev2_id]["parent_revision_id"] == rev1_id
        assert all_revs[rev3_id]["parent_revision_id"] == rev2_id

        print(
            f"\n  Linked list:  {rev3_id[:8]}... -> {rev2_id[:8]}... -> {rev1_id[:8]}... -> None"
        )
        print("  Revision lineage structure correct  [OK]")

        print(f"\n  [client] -> Gateway: GET /pages/{page_id[:8]}.../revisions/{rev3_id[:8]}...")
        detail = await client.get(
            f"/pages/{page_id}/revisions/{rev3_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        lineage = detail.json()["lineage"]
        print(f"  [client] <- {detail.status_code}: lineage has {len(lineage)} ancestor(s)")
        assert len(lineage) == 2
        print("  Revision detail + lineage returned correctly  [OK]")


async def test_revert_creates_new_revision_non_destructively(gateway, cluster, keypair):
    """
    Flow: Create page -> add revision -> revert to original -> check history

    Reverting must create a NEW revision with the old content; history is
    never mutated (non-destructive, per MICROSERVICE_ARCH.md §encyclopedia).
    """
    private_key, _ = keypair
    token = _issue_token(private_key, role="Editor")

    print("\n\n" + "=" * 70)
    print("TEST: Revert Creates New Revision (Non-Destructive)")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        r1 = await client.post(
            "/pages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": "whirligig",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Whirligig v1",
                "summary": "",
                "content": "# Whirligig\n\nOriginal content.",
            },
        )
        assert r1.status_code == 201
        page_id = r1.json()["page"]["id"]
        rev1_id = r1.json()["revision"]["id"]
        v = r1.json()["page"]["version"]
        print(f"\n  rev1={rev1_id[:8]}...  (original draft)  v{v}")

        r2 = await client.post(
            f"/pages/{page_id}/drafts",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "expected_page_version": v,
                "title": "Whirligig v2",
                "content": "# Whirligig\n\nModified content.",
                "parent_revision_id": rev1_id,
            },
        )
        assert r2.status_code == 201
        rev2_id = r2.json()["revision"]["id"]
        v = r2.json()["page"]["version"]
        print(f"  rev2={rev2_id[:8]}...  (modification)  v{v}")

        print(f"\n  [editor] -> Gateway: POST /pages/{page_id[:8]}.../revert  (to rev1)")
        rv = await client.post(
            f"/pages/{page_id}/revert",
            headers={"Authorization": f"Bearer {token}"},
            json={"expected_page_version": v, "revision_id": rev1_id},
        )
        assert rv.status_code == 201
        rev3_id = rv.json()["revision"]["id"]
        print(
            f"  [editor] <- {rv.status_code}:"
            f" new_rev={rev3_id[:8]}...  (copy of rev1's content)"
        )
        assert rev3_id not in {rev1_id, rev2_id}, "revert must produce a brand-new revision"

        list_resp = await client.get(
            f"/pages/{page_id}/revisions",
            headers={"Authorization": f"Bearer {token}"},
        )
        total = len(list_resp.json()["revisions"])
        print(f"  Total revisions after revert: {total}  (original 2 + revert = 3)")
        assert total == 3
    print("\n  Revert is non-destructive: original revisions preserved  [OK]")


async def test_media_upload_metadata_and_signed_url(gateway, cluster, keypair):
    """
    Flow: Client -> Gateway -> Media Service  (upload -> get metadata -> signed URL)

    Verifies the full media lifecycle:
      1. POST /media  - upload a file, get an asset_id back
      2. GET /media/{asset_id}  - retrieve file metadata
      3. GET /media/{asset_id}/download-url  - get a signed download URL
    """
    private_key, _ = keypair
    user_id = str(uuid4())
    token = _issue_token(private_key, subject=user_id, role="Researcher")

    print("\n\n" + "=" * 70)
    print("TEST: Media Upload, Metadata, and Signed Download URL")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        print("\n  [researcher] -> Gateway: POST /media  (upload zone-map.jpg)")
        upload = await client.post(
            "/media",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("zone-map.jpg", b"\xff\xd8\xff" + b"\x00" * 100, "image/jpeg")},
        )
        print(f"  [researcher] <- Gateway <- media-service: {upload.status_code}")
        assert upload.status_code == 201
        asset_id = upload.json()["id"]
        print(
            f"  asset_id={asset_id[:8]}..."
            f"  filename={upload.json()['filename']}"
            f"  size={upload.json()['size_bytes']} bytes"
            f"  checksum={upload.json()['checksum_sha256'][:16]}..."
        )

        print(f"\n  [researcher] -> Gateway: GET /media/{asset_id[:8]}...")
        meta = await client.get(
            f"/media/{asset_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"  [researcher] <- Gateway <- media-service: {meta.status_code}  {meta.json()}")
        assert meta.status_code == 200
        assert meta.json()["id"] == asset_id
        assert meta.json()["mime_type"] == "image/jpeg"

        print(f"\n  [researcher] -> Gateway: GET /media/{asset_id[:8]}.../download-url")
        url_resp = await client.get(
            f"/media/{asset_id}/download-url",
            headers={"Authorization": f"Bearer {token}"},
        )
        print(f"  [researcher] <- Gateway <- media-service: {url_resp.status_code}")
        assert url_resp.status_code == 200
        signed_url = url_resp.json()["url"]
        print(f"  signed URL: {signed_url}")
        assert "minio" in signed_url
        assert asset_id[:8] in signed_url

    print("\n  Media lifecycle complete  [OK]")


async def test_media_asset_linked_to_encyclopedia_page(gateway, cluster, keypair):
    """
    Flow: Upload media -> link asset ID to encyclopedia page metadata

    After uploading a file to media-service, a researcher attaches the
    returned asset_id to a page via encyclopedia-service's metadata endpoint.
    The two services remain decoupled - encyclopedia only stores a reference.
    """
    private_key, _ = keypair
    token = _issue_token(private_key, role="Researcher")

    print("\n\n" + "=" * 70)
    print("TEST: Media Asset Linked to Encyclopedia Page")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        print("\n  STEP 1 - Create page")
        r_page = await client.post(
            "/pages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": "psy-field",
                "type": "Anomaly",
                "visibility": "Internal",
                "title": "Psy Field",
                "summary": "Psychotropic anomaly",
                "content": "# Psy Field\n\nCauses hallucinations.",
            },
        )
        assert r_page.status_code == 201
        page_id = r_page.json()["page"]["id"]
        page_version = r_page.json()["page"]["version"]
        print(f"  Created page {page_id[:8]}...  v{page_version}")

        print("\n  STEP 2 - Upload photo to media-service")
        upload = await client.post(
            "/media",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("psy-field-photo.png", b"PNG\x00" * 50, "image/png")},
        )
        assert upload.status_code == 201
        asset_id = upload.json()["id"]
        print(f"  Uploaded asset {asset_id[:8]}...  ({upload.json()['size_bytes']} bytes)")

        print("\n  STEP 3 - Attach asset to page via metadata endpoint")
        print(f"  [researcher] -> Gateway: PUT /pages/{page_id[:8]}.../metadata")
        meta = await client.put(
            f"/pages/{page_id}/metadata",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "expected_page_version": page_version,
                "tags": ["anomaly", "psy", "brain-scorcher"],
                "classifications": ["highly-dangerous"],
                "related_page_ids": [],
                "media_asset_ids": [asset_id],
            },
        )
        assert meta.status_code == 200
        updated_page = meta.json()["page"]
        print(
            f"  [researcher] <- {meta.status_code}:"
            f" tags={updated_page['tags']}"
            f" media_asset_ids=[{updated_page['media_asset_ids'][0][:8]}...]"
        )
        assert asset_id in updated_page["media_asset_ids"]

    print("\n  Encyclopedia holds reference to media asset (services decoupled)  [OK]")


async def test_search_public_vs_authenticated_visibility(gateway, cluster, keypair):
    """
    Flow: Unauthenticated search (public only) vs authenticated search (internal)

    Per the architecture, search-service uses the X-Authenticated-Source and
    X-Authenticated-User-Role headers forwarded by the gateway to determine
    whether to include Internal/Draft content in results.
    """
    private_key, _ = keypair
    researcher_token = _issue_token(private_key, role="Researcher")

    # Seed the mock search index with one public and one internal document
    cluster.state.search_index.extend(
        [
            {
                "page_id": str(uuid4()),
                "slug": "electro-zone",
                "type": "Anomaly",
                "status": "Published",
                "visibility": "Public",
                "title": "Electro Zone",
                "summary": "High-voltage anomaly visible from outside the cordon",
            },
            {
                "page_id": str(uuid4()),
                "slug": "military-stash",
                "type": "Location",
                "status": "Draft",
                "visibility": "Internal",
                "title": "Military Stash (classified)",
                "summary": "Classified military cache location",
            },
        ]
    )

    print("\n\n" + "=" * 70)
    print("TEST: Search - Public vs Authenticated Visibility")
    print("=" * 70)
    print(f"\n  Index seeded with 2 documents:"
          f"\n    * Electro Zone     (Published / Public)"
          f"\n    * Military Stash   (Draft / Internal)")

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        # Unauthenticated public search
        print("\n  [public] -> Gateway: GET /search?q=zone  (no token)")
        pub = await client.get("/search?q=zone")
        print(f"  [public] <- Gateway <- search-service: {pub.status_code}"
              f"  total={pub.json()['total']}")
        assert pub.status_code == 200
        assert pub.json()["total"] == 1
        assert pub.json()["hits"][0]["slug"] == "electro-zone"
        print("  Only published+public result returned  [OK]")

        # Unauthenticated search for internal doc - should return nothing
        print("\n  [public] -> Gateway: GET /search?q=stash  (no token)")
        pub2 = await client.get("/search?q=stash")
        print(f"  [public] <- {pub2.status_code}  total={pub2.json()['total']}")
        assert pub2.json()["total"] == 0
        print("  Internal document hidden from unauthenticated search  [OK]")

        # Authenticated search - researcher can see internal content
        print("\n  [researcher] -> Gateway: GET /search?q=stash  (with JWT role=Researcher)")
        auth = await client.get(
            "/search?q=stash",
            headers={"Authorization": f"Bearer {researcher_token}"},
        )
        print(f"  [researcher] <- {auth.status_code}  total={auth.json()['total']}")
        assert auth.status_code == 200
        assert auth.json()["total"] == 1
        print("  Internal document visible to authenticated researcher  [OK]")

        # Autocomplete suggest
        print("\n  [researcher] -> Gateway: GET /search/suggest?q=ele")
        suggest = await client.get(
            "/search/suggest?q=ele",
            headers={"Authorization": f"Bearer {researcher_token}"},
        )
        print(f"  [researcher] <- {suggest.status_code}  suggestions={suggest.json()['suggestions']}")
        assert suggest.status_code == 200
        assert "Electro Zone" in suggest.json()["suggestions"]

    print("\n  Search public/internal visibility enforced  [OK]")


async def test_search_is_accessible_without_authentication(gateway, cluster, keypair):
    """
    The /search and /search/suggest endpoints must be accessible without a
    JWT token (unlike all other routes).  Public readers can search without
    registering.
    """
    cluster.state.search_index.append(
        {
            "page_id": str(uuid4()),
            "slug": "artifact-compass",
            "type": "Artifact",
            "status": "Published",
            "visibility": "Public",
            "title": "Compass Artifact",
            "summary": "Navigation artifact found in the Zone",
        }
    )

    print("\n\n" + "=" * 70)
    print("TEST: Search Accessible Without Authentication (Public Routes)")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gateway), base_url="http://test") as client:
        print("\n  [public reader] -> Gateway: GET /search?q=compass  (no token)")
        resp = await client.get("/search?q=compass")
        print(f"  [public reader] <- {resp.status_code}  total={resp.json()['total']}")
        assert resp.status_code == 200

        print("\n  [public reader] -> Gateway: GET /search/suggest?q=com  (no token)")
        resp2 = await client.get("/search/suggest?q=com")
        print(f"  [public reader] <- {resp2.status_code}  suggestions={resp2.json()['suggestions']}")
        assert resp2.status_code == 200

    print("\n  /search and /search/suggest accessible without auth  [OK]")


async def test_all_protected_routes_require_bearer_token(cluster):
    """
    Conformance test: every protected route must return HTTP 401 with
    error.code == 'missing_bearer_token' when no Authorization header is sent.
    """
    gw = create_app(upstream_transport=ASGITransport(app=cluster))
    page_id = "11111111-1111-1111-1111-111111111111"
    asset_id = "22222222-2222-2222-2222-222222222222"

    protected = [
        ("GET",  f"/pages/{page_id}",                   "read page"),
        ("GET",  f"/pages/{page_id}/revisions",          "list revisions"),
        ("GET",  f"/pages/{page_id}/revisions/{page_id}", "get revision"),
        ("POST", "/pages",                               "create page"),
        ("POST", f"/pages/{page_id}/drafts",             "create draft"),
        ("PUT",  f"/pages/{page_id}/metadata",           "update metadata"),
        ("POST", f"/pages/{page_id}/publish",            "publish page"),
        ("POST", f"/pages/{page_id}/revert",             "revert revision"),
        ("POST", f"/pages/{page_id}/status",             "status transition"),
        ("POST", "/media",                               "upload media"),
        ("GET",  f"/media/{asset_id}",                  "get media metadata"),
        ("GET",  f"/media/{asset_id}/download-url",     "get download URL"),
    ]

    print("\n\n" + "=" * 70)
    print("TEST: All Protected Routes Reject Requests Without Bearer Token")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gw), base_url="http://test") as client:
        for method, path, label in protected:
            resp = await client.request(method, path)
            status = resp.status_code
            code = resp.json().get("error", {}).get("code", "?")
            mark = "[OK]" if status == 401 else "[FAIL] FAIL"
            print(f"  {mark}  {method:4}  {path:<55}  ->  {status}  ({code})")
            assert status == 401, (
                f"{label}: expected 401, got {status}"
            )
            assert code == "missing_bearer_token", (
                f"{label}: expected missing_bearer_token, got {code}"
            )

    print(f"\n  All {len(protected)} protected routes enforce authentication  [OK]")


async def test_gateway_strips_spoofed_identity_headers(gateway, cluster, keypair):
    """
    Conformance test (API Gateway Forwarding Contract §Header Contract):

    The gateway must strip any X-Authenticated-* and Authorization headers
    that arrive from the client and replace them with values derived
    exclusively from the validated JWT claims.

    An attacker sending a forged X-Authenticated-User-Id must not be able to
    impersonate another user at the downstream service.
    """
    private_key, _ = keypair
    real_user_id = str(uuid4())
    token = _issue_token(
        private_key,
        subject=real_user_id,
        email="real-user@zone.ua",
        role="Researcher",
    )

    received: dict = {}

    # Wire a custom intercept app that records what the gateway actually sends
    intercept = FastAPI()

    @intercept.get("/auth/jwks")
    async def jwks_pass() -> JSONResponse:
        return JSONResponse({"keys": [keypair[1]]})

    @intercept.post("/pages")
    async def capture(request: Request) -> JSONResponse:
        received["user_id"] = request.headers.get("x-authenticated-user-id")
        received["role"] = request.headers.get("x-authenticated-user-role")
        received["source"] = request.headers.get("x-authenticated-source")
        received["authorization"] = request.headers.get("authorization")
        received["x_internal_token"] = request.headers.get("x-internal-token")
        return JSONResponse(
            status_code=201,
            content={
                "page": {"id": str(uuid4()), "slug": "test", "status": "Draft"},
                "revision": {"id": str(uuid4()), "author_id": received["user_id"]},
            },
        )

    intercept_gw = create_app(upstream_transport=ASGITransport(app=intercept))
    intercept_gw.state.jwks_cache._keys = [keypair[1]]
    intercept_gw.state.jwks_cache._expires_at = 10**12

    print("\n\n" + "=" * 70)
    print("TEST: Gateway Strips Spoofed Identity Headers (Forwarding Contract)")
    print("=" * 70)
    print(f"\n  Legitimate JWT: sub={real_user_id[:8]}...  role=Researcher")
    print("  Client sends spoofed headers alongside the valid token:")
    print("    X-Authenticated-User-Id   = 00000000-...  (attacker's target)")
    print("    X-Authenticated-User-Role = Admin       (privilege escalation attempt)")
    print("    X-Authenticated-Source    = evil-client (bypass attempt)")
    print("    X-Internal-Token          = leaked-tok  (internal token injection)")

    async with AsyncClient(transport=ASGITransport(app=intercept_gw), base_url="http://test") as client:
        resp = await client.post(
            "/pages",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Authenticated-User-Id": "00000000-0000-0000-0000-000000000000",
                "X-Authenticated-User-Role": "Admin",
                "X-Authenticated-Source": "evil-client",
                "X-Internal-Token": "leaked-token",
            },
            json={
                "slug": "test-slug",
                "type": "Article",
                "visibility": "Internal",
                "title": "T",
                "content": "C",
            },
        )
    assert resp.status_code == 201

    print("\n  What downstream encyclopedia-service actually received:")
    print(f"    X-Authenticated-User-Id   = {received['user_id']}")
    print(f"    X-Authenticated-User-Role = {received['role']}")
    print(f"    X-Authenticated-Source    = {received['source']}")
    print(f"    Authorization             = {received['authorization']}")
    print(f"    X-Internal-Token          = {received['x_internal_token']}")

    assert received["user_id"] == real_user_id, (
        f"downstream user_id must be from JWT ({real_user_id[:8]}...), not spoofed (00000000...)"
    )
    assert received["role"] == "Researcher", (
        "downstream role must be from JWT (Researcher), not spoofed (Admin)"
    )
    assert received["source"] == "api-gateway", (
        "downstream source must be set by gateway, not client"
    )
    assert received["authorization"] is None, (
        "Authorization header must be stripped before forwarding"
    )
    assert received["x_internal_token"] is None, (
        "X-Internal-Token must be stripped to prevent internal token injection"
    )

    print("\n  All spoofed headers were replaced or stripped by gateway  [OK]")


async def test_gateway_normalises_upstream_error_responses(cluster, keypair):
    """
    When a downstream service returns an error status code the gateway must
    surface a structured JSON error body rather than forwarding a raw upstream
    response.
    """
    private_key, jwk = keypair
    error_app = FastAPI()

    @error_app.post("/pages")
    async def always_503() -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "database unreachable"})

    @error_app.get("/auth/jwks")
    async def jwks() -> JSONResponse:
        return JSONResponse({"keys": [jwk]})

    gw = create_app(upstream_transport=ASGITransport(app=error_app))
    gw.state.jwks_cache._keys = [jwk]
    gw.state.jwks_cache._expires_at = 10**12
    token = _issue_token(private_key)

    print("\n\n" + "=" * 70)
    print("TEST: Gateway Normalises Upstream Error Responses")
    print("=" * 70)

    async with AsyncClient(transport=ASGITransport(app=gw), base_url="http://test") as client:
        print("\n  encyclopedia-service returns 503")
        print("  [client] -> Gateway: POST /pages")
        resp = await client.post(
            "/pages",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": "x", "type": "Article", "visibility": "Public",
                  "title": "X", "content": "C"},
        )
        print(f"  [client] <- Gateway: {resp.status_code}  {resp.json()}")

    assert resp.status_code == 503
    error = resp.json().get("error", {})
    assert error.get("code") == "upstream_server_error"
    assert error.get("details", {}).get("service") == "encyclopedia-service"
    print("\n  Gateway wrapped upstream error in structured error body  [OK]")
