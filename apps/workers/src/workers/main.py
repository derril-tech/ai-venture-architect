"""Worker entry point."""

import asyncio
import logging
from typing import Dict, Type

import structlog
from nats.aio.client import Client as NATS

from workers.core.config import get_settings
from workers.core.worker import BaseWorker
from workers.agents.ingest_worker import IngestWorker
from workers.agents.normalize_worker import NormalizeWorker
from workers.agents.trend_worker import TrendWorker
from workers.agents.ideation_worker import IdeationWorker

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Worker registry
WORKERS: Dict[str, Type[BaseWorker]] = {
    "ingest": IngestWorker,
    "normalize": NormalizeWorker,
    "trend": TrendWorker,
    "ideation": IdeationWorker,
}


async def main():
    """Main worker entry point."""
    settings = get_settings()
    
    logger.info("Starting AI Venture Architect Workers")
    
    # Connect to NATS
    nc = NATS()
    await nc.connect(settings.nats_url)
    
    # Start workers
    workers = []
    for worker_name, worker_class in WORKERS.items():
        worker = worker_class(nc)
        workers.append(worker)
        await worker.start()
        logger.info(f"Started {worker_name} worker")
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down workers")
        
        # Stop workers
        for worker in workers:
            await worker.stop()
        
        # Close NATS connection
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
