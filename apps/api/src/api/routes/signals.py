"""Signal management endpoints."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db

router = APIRouter()


class SignalResponse(BaseModel):
    """Signal response model."""
    id: UUID
    workspace_id: UUID
    source: str
    title: Optional[str]
    content: str
    url: Optional[str]
    published_at: Optional[str]
    created_at: str


class SignalListResponse(BaseModel):
    """Signal list response model."""
    signals: List[SignalResponse]
    total: int
    page: int
    per_page: int


class IngestRequest(BaseModel):
    """Signal ingestion request model."""
    source: str
    url: Optional[str] = None
    content: str
    title: Optional[str] = None
    metadata: dict = {}


@router.get("", response_model=SignalListResponse)
async def list_signals(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List signals with pagination and filtering."""
    # TODO: Implement signal listing logic
    return SignalListResponse(
        signals=[],
        total=0,
        page=page,
        per_page=per_page,
    )


@router.post("/ingest")
async def ingest_signal(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
):
    """Ingest a new signal."""
    # TODO: Implement signal ingestion logic
    return {"message": "Signal ingested successfully", "signal_id": "dummy_id"}


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(
    signal_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific signal."""
    # TODO: Implement signal retrieval logic
    raise NotImplementedError("Signal retrieval not yet implemented")
