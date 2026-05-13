from datetime import datetime
from sqlalchemy import Enum, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from shared.models import UserRole

class Base(DeclarativeBase):
    pass

class User(SQLAlchemyBaseUserTableUUID, Base):
    role: Mapped[UserRole] = mapped_column(
        Enum(*[r.value for r in UserRole], name="userrole"),
        default=UserRole.RESEARCHER,
        server_default=UserRole.RESEARCHER.value,
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False
    )
    last_login: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        nullable=True
    )
