from uuid import UUID

from fastapi_users import schemas
from shared.models import UserRole


class UserRead(schemas.BaseUser[UUID]):
    role: UserRole


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    role: UserRole | None = None
