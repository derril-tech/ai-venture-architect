"""Report model for exports and generated documents."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

if TYPE_CHECKING:
    from api.models.workspace import Workspace


class ReportType(str, Enum):
    """Report type enumeration."""
    
    MARKET_INTELLIGENCE = "market_intelligence"
    PRODUCT_BRIEF = "product_brief"
    INVESTOR_DECK = "investor_deck"
    COMPETITOR_ANALYSIS = "competitor_analysis"
    TREND_DIGEST = "trend_digest"


class ReportFormat(str, Enum):
    """Report format enumeration."""
    
    PDF = "pdf"
    HTML = "html"
    JSON = "json"
    CSV = "csv"
    NOTION = "notion"


class ReportStatus(str, Enum):
    """Report generation status."""
    
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class Report(Base):
    """Report model for exports and generated documents."""
    
    __tablename__ = "reports"
    
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
    
    # Report metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_type: Mapped[ReportType] = mapped_column(
        SQLEnum(ReportType),
        nullable=False,
    )
    format: Mapped[ReportFormat] = mapped_column(
        SQLEnum(ReportFormat),
        nullable=False,
    )
    
    # Content and configuration
    config: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    content: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # File storage
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(nullable=True)
    signed_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    signed_url_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Processing
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus),
        nullable=False,
        default=ReportStatus.PENDING,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
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
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    
    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="reports")
    
    def __repr__(self) -> str:
        return f"<Report(id={self.id}, title='{self.title}', type={self.report_type}, status={self.status})>"
