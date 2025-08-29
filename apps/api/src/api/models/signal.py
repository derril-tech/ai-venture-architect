"""Signal model for market data ingestion."""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

if TYPE_CHECKING:
    from api.models.workspace import Workspace


class Signal(Base):
    """Signal model for ingested market data."""
    
    __tablename__ = "signals"
    
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    workspace_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Source information
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "product_hunt", "github"
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Content
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Metadata
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Entity information (extracted)
    entities: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Embeddings (stored as array in JSONB for now, will move to pgvector)
    embedding: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    
    # Processing status
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
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
    
    # Source timestamp (when the signal was originally published)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="signals")
    
    def __repr__(self) -> str:
        return f"<Signal(id={self.id}, source='{self.source}', workspace_id={self.workspace_id})>"
