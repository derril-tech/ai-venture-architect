"""Ingestion worker for collecting data from various sources."""

import asyncio
from typing import Any, Dict
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from workers.core.worker import BaseWorker
from workers.core.config import get_settings
from workers.connectors.product_hunt import ProductHuntConnector
from workers.connectors.github import GitHubConnector
from workers.connectors.rss import RSSConnector

logger = structlog.get_logger()
settings = get_settings()

# Database setup
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class IngestWorker(BaseWorker):
    """Worker for ingesting data from external sources."""
    
    def __init__(self, nats_client):
        super().__init__(nats_client, "signals.ingest")
        self.connectors = {
            "product_hunt": ProductHuntConnector(),
            "github": GitHubConnector(),
            "rss": RSSConnector(),
        }
    
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process ingestion request."""
        source = payload.get("source")
        workspace_id = payload.get("workspace_id")
        config = payload.get("config", {})
        
        if not source or not workspace_id:
            raise ValueError("Missing required fields: source, workspace_id")
        
        if source not in self.connectors:
            raise ValueError(f"Unknown source: {source}")
        
        logger.info(f"Starting ingestion for source: {source}")
        
        connector = self.connectors[source]
        ingested_count = 0
        
        try:
            async with connector:
                async for signal_data in connector.fetch_data(**config):
                    await self._store_signal(workspace_id, source, signal_data)
                    ingested_count += 1
                    
                    # Publish normalization task
                    await self._publish_normalize_task(workspace_id, signal_data)
            
            logger.info(f"Ingestion completed: {ingested_count} signals from {source}")
            
            return {
                "status": "completed",
                "source": source,
                "workspace_id": workspace_id,
                "ingested_count": ingested_count,
            }
            
        except Exception as e:
            logger.error(f"Ingestion failed for {source}: {e}")
            return {
                "status": "failed",
                "source": source,
                "workspace_id": workspace_id,
                "error": str(e),
            }
    
    async def _store_signal(self, workspace_id: str, source: str, signal_data: Dict[str, Any]):
        """Store signal in database."""
        async with AsyncSessionLocal() as session:
            try:
                # Import here to avoid circular imports
                from api.models.signal import Signal
                from datetime import datetime
                from uuid import UUID
                
                signal = Signal(
                    workspace_id=UUID(workspace_id),
                    source=source,
                    source_id=signal_data.get("id"),
                    url=signal_data.get("url"),
                    title=signal_data.get("title"),
                    content=signal_data.get("content", ""),
                    summary=signal_data.get("summary"),
                    metadata=signal_data.get("metadata", {}),
                    published_at=datetime.fromisoformat(signal_data["published_at"]) if signal_data.get("published_at") else None,
                )
                
                session.add(signal)
                await session.commit()
                
                logger.debug(f"Stored signal: {signal.id}")
                
            except Exception as e:
                logger.error(f"Error storing signal: {e}")
                await session.rollback()
                raise
    
    async def _publish_normalize_task(self, workspace_id: str, signal_data: Dict[str, Any]):
        """Publish normalization task for the signal."""
        import json
        
        task_data = {
            "workspace_id": workspace_id,
            "signal_data": signal_data,
            "task_id": str(uuid4()),
        }
        
        await self.nats.publish(
            "signals.normalize",
            json.dumps(task_data).encode()
        )
