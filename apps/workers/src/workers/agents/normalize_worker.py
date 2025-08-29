"""Normalization worker for processing and enriching signals."""

import re
from typing import Any, Dict, List, Optional
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from workers.core.worker import BaseWorker
from workers.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Database setup
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class NormalizeWorker(BaseWorker):
    """Worker for normalizing and enriching signal data."""
    
    def __init__(self, nats_client):
        super().__init__(nats_client, "signals.normalize")
        
        # Industry categories (simplified NAICS mapping)
        self.industry_keywords = {
            "software": ["software", "app", "platform", "saas", "api", "cloud"],
            "ai_ml": ["ai", "artificial intelligence", "machine learning", "ml", "deep learning", "neural", "llm"],
            "fintech": ["fintech", "finance", "banking", "payment", "crypto", "blockchain", "trading"],
            "healthcare": ["health", "medical", "healthcare", "biotech", "pharma", "telemedicine"],
            "ecommerce": ["ecommerce", "e-commerce", "retail", "marketplace", "shopping", "commerce"],
            "gaming": ["game", "gaming", "esports", "vr", "ar", "metaverse"],
            "education": ["education", "learning", "edtech", "training", "course", "university"],
            "productivity": ["productivity", "workflow", "automation", "collaboration", "project management"],
            "security": ["security", "cybersecurity", "privacy", "encryption", "auth"],
            "iot": ["iot", "internet of things", "smart home", "connected", "sensor"],
        }
        
        # Monetization models
        self.monetization_keywords = {
            "subscription": ["subscription", "monthly", "annual", "recurring", "saas"],
            "freemium": ["freemium", "free tier", "premium", "upgrade"],
            "marketplace": ["marketplace", "commission", "transaction fee", "percentage"],
            "advertising": ["ads", "advertising", "sponsored", "revenue share"],
            "one_time": ["one-time", "purchase", "buy", "license"],
            "usage_based": ["usage", "pay-as-you-go", "metered", "consumption"],
        }
    
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process normalization request."""
        workspace_id = payload.get("workspace_id")
        signal_data = payload.get("signal_data")
        
        if not workspace_id or not signal_data:
            raise ValueError("Missing required fields: workspace_id, signal_data")
        
        logger.info("Starting signal normalization")
        
        try:
            # Normalize the signal data
            normalized_data = await self._normalize_signal(signal_data)
            
            # Extract entities
            entities = await self._extract_entities(normalized_data)
            
            # Update signal in database
            await self._update_signal(workspace_id, signal_data, normalized_data, entities)
            
            logger.info("Signal normalization completed")
            
            return {
                "status": "completed",
                "workspace_id": workspace_id,
                "entities": entities,
                "normalized_data": normalized_data,
            }
            
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            return {
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(e),
            }
    
    async def _normalize_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize signal data."""
        normalized = signal_data.copy()
        
        # Clean and normalize text
        content = signal_data.get("content", "")
        title = signal_data.get("title", "")
        
        # Remove extra whitespace and normalize
        content = re.sub(r'\s+', ' ', content).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Extract key phrases and clean content
        normalized["content"] = content
        normalized["title"] = title
        normalized["word_count"] = len(content.split())
        
        # Normalize URL
        url = signal_data.get("url", "")
        if url:
            # Clean tracking parameters
            normalized["clean_url"] = self._clean_url(url)
        
        return normalized
    
    async def _extract_entities(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities from signal data."""
        content = signal_data.get("content", "").lower()
        title = signal_data.get("title", "").lower()
        full_text = f"{title} {content}"
        
        entities = {
            "industries": [],
            "monetization_models": [],
            "technologies": [],
            "companies": [],
            "products": [],
        }
        
        # Extract industries
        for industry, keywords in self.industry_keywords.items():
            if any(keyword in full_text for keyword in keywords):
                entities["industries"].append(industry)
        
        # Extract monetization models
        for model, keywords in self.monetization_keywords.items():
            if any(keyword in full_text for keyword in keywords):
                entities["monetization_models"].append(model)
        
        # Extract technologies (simplified)
        tech_patterns = [
            r'\b(python|javascript|react|vue|angular|node\.?js|django|flask|fastapi)\b',
            r'\b(aws|azure|gcp|kubernetes|docker|terraform)\b',
            r'\b(postgresql|mysql|mongodb|redis|elasticsearch)\b',
            r'\b(openai|anthropic|hugging\s?face|tensorflow|pytorch)\b',
        ]
        
        for pattern in tech_patterns:
            matches = re.findall(pattern, full_text, re.IGNORECASE)
            entities["technologies"].extend(matches)
        
        # Extract company names (simplified - look for capitalized words)
        company_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        potential_companies = re.findall(company_pattern, signal_data.get("content", ""))
        
        # Filter out common words
        common_words = {"The", "This", "That", "With", "For", "And", "But", "Or"}
        companies = [comp for comp in potential_companies if comp not in common_words]
        entities["companies"] = companies[:5]  # Limit to top 5
        
        # Remove duplicates
        for key in entities:
            if isinstance(entities[key], list):
                entities[key] = list(set(entities[key]))
        
        return entities
    
    def _clean_url(self, url: str) -> str:
        """Clean tracking parameters from URL."""
        # Remove common tracking parameters
        tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'ref', 'source', 'campaign'
        ]
        
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)
        
        # Remove tracking parameters
        clean_params = {k: v for k, v in query_params.items() 
                       if k.lower() not in tracking_params}
        
        clean_query = urlencode(clean_params, doseq=True)
        clean_parsed = parsed._replace(query=clean_query)
        
        return urlunparse(clean_parsed)
    
    async def _update_signal(
        self, 
        workspace_id: str, 
        original_data: Dict[str, Any], 
        normalized_data: Dict[str, Any], 
        entities: Dict[str, Any]
    ):
        """Update signal in database with normalized data."""
        async with AsyncSessionLocal() as session:
            try:
                from api.models.signal import Signal
                from sqlalchemy import select
                from uuid import UUID
                
                # Find the signal by URL or content (simplified lookup)
                url = original_data.get("url")
                title = original_data.get("title")
                
                query = select(Signal).where(
                    Signal.workspace_id == UUID(workspace_id)
                )
                
                if url:
                    query = query.where(Signal.url == url)
                elif title:
                    query = query.where(Signal.title == title)
                else:
                    # Fallback to content matching
                    query = query.where(Signal.content.contains(original_data.get("content", "")[:100]))
                
                result = await session.execute(query)
                signal = result.scalar_one_or_none()
                
                if signal:
                    # Update with normalized data
                    signal.entities = entities
                    signal.metadata.update(normalized_data.get("metadata", {}))
                    signal.processed_at = datetime.utcnow()
                    
                    await session.commit()
                    logger.debug(f"Updated signal: {signal.id}")
                else:
                    logger.warning("Signal not found for normalization update")
                
            except Exception as e:
                logger.error(f"Error updating signal: {e}")
                await session.rollback()
                raise
