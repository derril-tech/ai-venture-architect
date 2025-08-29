"""Workspace model."""

from datetime import datetime
from typing import TYPE_CHECKING, List
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

if TYPE_CHECKING:
    from api.models.user import UserWorkspace
    from api.models.signal import Signal
    from api.models.idea import Idea
    from api.models.report import Report


class Workspace(Base):
    """Workspace model for multi-tenancy."""
    
    __tablename__ = "workspaces"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    
    # Relationships
    user_workspaces: Mapped[List["UserWorkspace"]] = relationship(
        "UserWorkspace",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    signals: Mapped[List["Signal"]] = relationship(
        "Signal",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    ideas: Mapped[List["Idea"]] = relationship(
        "Idea",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="workspace",
        cascade="all, delete-orphan",
    )
    
    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name='{self.name}', slug='{self.slug}')>"
