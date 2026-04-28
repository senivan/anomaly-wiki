from uuid import UUID
from typing import Optional
from fastapi_users import schemas
from shared.models import UserRole

class UserRead(schemas.BaseUser[UUID]):
    role: UserRole

class UserCreate(schemas.BaseUserCreate):
    role: UserRole = UserRole.RESEARCHER

class UserUpdate(schemas.BaseUserUpdate):
    role: Optional[UserRole] = None
