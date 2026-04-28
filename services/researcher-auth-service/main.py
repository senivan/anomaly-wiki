import base64
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_users import FastAPIUsers
from cryptography.hazmat.primitives import serialization

from db import engine
from models import Base, User
from schemas import UserRead, UserCreate, UserUpdate
from auth.manager import get_user_manager
from auth.backend import auth_backend
from auth.keys import load_keys

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
