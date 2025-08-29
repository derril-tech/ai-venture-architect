"""Base worker class."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import structlog
from nats.aio.client import Client as NATS
from nats.aio.msg import Msg

logger = structlog.get_logger()


class BaseWorker(ABC):
    """Base class for all workers."""
    
    def __init__(self, nats_client: NATS, subject: str):
        self.nats = nats_client
        self.subject = subject
        self.subscription = None
        self.running = False
    
    async def start(self):
        """Start the worker."""
        self.running = True
        self.subscription = await self.nats.subscribe(
            self.subject,
            cb=self._handle_message,
            queue="workers"
        )
        logger.info(f"Worker started for subject: {self.subject}")
    
    async def stop(self):
        """Stop the worker."""
        self.running = False
        if self.subscription:
            await self.subscription.unsubscribe()
        logger.info(f"Worker stopped for subject: {self.subject}")
    
    async def _handle_message(self, msg: Msg):
        """Handle incoming NATS message."""
        try:
            # Parse message data
            data = msg.data.decode() if msg.data else "{}"
            import json
            payload = json.loads(data)
            
            logger.info(
                "Processing message",
                subject=msg.subject,
                reply=msg.reply,
                payload_keys=list(payload.keys()) if isinstance(payload, dict) else None
            )
            
            # Process the message
            result = await self.process_message(payload)
            
            # Send reply if requested
            if msg.reply:
                reply_data = json.dumps(result).encode()
                await self.nats.publish(msg.reply, reply_data)
            
            logger.info("Message processed successfully", subject=msg.subject)
            
        except Exception as e:
            logger.error(
                "Error processing message",
                subject=msg.subject,
                error=str(e),
                exc_info=True
            )
            
            # Send error reply if requested
            if msg.reply:
                error_data = json.dumps({
                    "error": str(e),
                    "type": type(e).__name__
                }).encode()
                await self.nats.publish(msg.reply, error_data)
    
    @abstractmethod
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message payload.
        
        Args:
            payload: The message payload
            
        Returns:
            Result dictionary
        """
        pass
