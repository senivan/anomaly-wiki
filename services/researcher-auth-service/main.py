import base64
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi_users import FastAPIUsers
from cryptography.hazmat.primitives import serialization
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import engine, get_async_session
from models import Base, User
from schemas import UserRead, UserCreate, UserUpdate
from auth.manager import get_user_manager
from auth.backend import auth_backend
from auth.keys import load_keys
from shared.models import UserRole

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Researcher Auth Service",
    description="Identity and Access Management for Researchers",
    version="0.1.0",
    lifespan=lifespan,
)

fastapi_users = FastAPIUsers[User, uuid.UUID](
    get_user_manager,
    [auth_backend],
)

app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Admin endpoints (called only via api-gateway Admin-only proxy) ──────────

class UserListItem(BaseModel):
    id: uuid.UUID
    email: str
    role: UserRole
    is_active: bool

class RoleUpdateRequest(BaseModel):
    role: UserRole


@app.get("/admin/users", response_model=list[UserListItem])
async def list_users(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(User).order_by(User.email))
    return [
        UserListItem(id=u.id, email=u.email, role=u.role, is_active=u.is_active)
        for u in result.scalars().all()
    ]


@app.patch("/admin/users/{user_id}/role", response_model=UserListItem)
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdateRequest,
    session: AsyncSession = Depends(get_async_session),
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    user.role = payload.role
    await session.commit()
    await session.refresh(user)
    return UserListItem(id=user.id, email=user.email, role=user.role, is_active=user.is_active)


@app.get("/auth/jwks")
async def get_jwks():
    _, public_pem = load_keys()
    public_key = serialization.load_pem_public_key(public_pem.encode())
    numbers = public_key.public_numbers()
    
    def b64url(n: int):
        b = n.to_bytes((n.bit_length() + 7) // 8, byteorder='big')
        return base64.urlsafe_b64encode(b).decode('utf-8').rstrip('=')

    return {
        "keys": [
            {
                "kty": "RSA",
                "alg": "RS256",
                "use": "sig",
                "kid": "default",
                "n": b64url(numbers.n),
                "e": b64url(numbers.e),
            }
        ]
    }
