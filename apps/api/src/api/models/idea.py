"""Idea model for generated product concepts."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base

if TYPE_CHECKING:
    from api.models.workspace import Workspace


class IdeaStatus(str, Enum):
    """Idea processing status."""
    
    DRAFT = "draft"
    GENERATING = "generating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class Idea(Base):
    """Idea model for generated product concepts."""
    
    __tablename__ = "ideas"
    
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
    
    # Basic information
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Core concept
    uvp: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Unique Value Proposition
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    solution_approach: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Target market
    icps: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)  # Ideal Customer Profiles
    target_segments: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Product details
    mvp_features: Mapped[List[str]] = mapped_column(JSONB, default=list)
    roadmap: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    positioning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Business model
    tam_sam_som: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    unit_economics: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    pricing_model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Technical feasibility
    tech_stack: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    build_vs_buy: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    technical_risks: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # GTM strategy
    gtm_strategy: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    channels: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Risk assessment
    risks: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    compliance_notes: Mapped[List[str]] = mapped_column(JSONB, default=list)
    
    # Scoring
    attractiveness_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_breakdown: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Sources and citations
    sources: Mapped[List[str]] = mapped_column(JSONB, default=list)
    citations: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict)
    
    # Processing
    status: Mapped[IdeaStatus] = mapped_column(
        SQLEnum(IdeaStatus),
        nullable=False,
        default=IdeaStatus.DRAFT,
    )
    run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
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
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="ideas")
    
    def __repr__(self) -> str:
        return f"<Idea(id={self.id}, title='{self.title}', status={self.status})>"
