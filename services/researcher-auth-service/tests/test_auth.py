import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from auth.keys import load_keys

@pytest.mark.asyncio
async def test_healthcheck(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_jwks(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/auth/jwks")
    
    assert response.status_code == 200
    data = response.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    assert data["keys"][0]["kty"] == "RSA"
    assert data["keys"][0]["alg"] == "RS256"
    assert data["keys"][0]["kid"] == "default"
    assert "n" in data["keys"][0]
    assert "e" in data["keys"][0]

@pytest.mark.asyncio
async def test_register_and_login(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register a new researcher
        email = f"test-{uuid.uuid4()}@example.com"
        password = "testpassword123"
        register_payload = {
            "email": email,
            "password": password,
            "is_active": True,
            "is_superuser": False,
            "is_verified": False,
            "role": "Researcher"
        }
        
        register_response = await ac.post("/auth/register", json=register_payload)
        assert register_response.status_code == 201, register_response.text
        
        # 2. Login to get JWT
        login_data = {
            "username": email,
            "password": password
        }
        login_response = await ac.post("/auth/login", data=login_data)
        assert login_response.status_code == 200, login_response.text
        
        token_data = login_response.json()
        assert "access_token" in token_data
        token = token_data["access_token"]
        assert token_data["token_type"] == "bearer"
        
        # 2b. Decode and verify token claims
        import jwt
        _, public_pem = load_keys()
        # Default audience in fastapi-users JWTStrategy is "fastapi-users:auth"
        decoded_token = jwt.decode(token, public_pem, algorithms=["RS256"], audience="fastapi-users:auth")
        assert decoded_token["role"] == "Researcher"
        assert decoded_token["email"] == email
        
        # 3. Verify /users/me
        me_response = await ac.get("/users/me", headers={"Authorization": f"Bearer {token}"})
        assert me_response.status_code == 200
        user_data = me_response.json()
        assert user_data["email"] == email
        assert user_data["role"] == "Researcher"
        assert user_data["is_active"] is True


@pytest.mark.asyncio
async def test_register_ignores_privileged_role_input(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        email = f"test-{uuid.uuid4()}@example.com"
        register_payload = {
            "email": email,
            "password": "testpassword123",
            "role": "Admin",
        }

        register_response = await ac.post("/auth/register", json=register_payload)
        assert register_response.status_code == 201, register_response.text
        assert register_response.json()["role"] == "Researcher"


@pytest.mark.asyncio
async def test_users_me_cannot_self_promote(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        email = f"test-{uuid.uuid4()}@example.com"
        password = "testpassword123"

        register_response = await ac.post(
            "/auth/register",
            json={"email": email, "password": password},
        )
        assert register_response.status_code == 201, register_response.text

        login_response = await ac.post(
            "/auth/login",
            data={"username": email, "password": password},
        )
        assert login_response.status_code == 200, login_response.text
        token = login_response.json()["access_token"]

        update_response = await ac.patch(
            "/users/me",
            json={"role": "Admin"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert update_response.status_code == 200, update_response.text
        assert update_response.json()["role"] == "Researcher"
