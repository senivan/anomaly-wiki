from uuid import UUID

from pydantic import Field, field_validator
from fastapi_users import schemas
from shared.models import UserRole


class UserRead(schemas.BaseUser[UUID]):
    role: UserRole


class UserCreate(schemas.BaseUserCreate):
    password: str = Field(min_length=8)
    role: UserRole = UserRole.RESEARCHER

    @field_validator("role")
    @classmethod
    def force_self_registered_role(cls, role: UserRole) -> UserRole:
        return UserRole.RESEARCHER


class UserUpdate(schemas.BaseUserUpdate):
    pass
