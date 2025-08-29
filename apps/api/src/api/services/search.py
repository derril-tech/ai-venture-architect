"""Hybrid search service combining BM25, vector search, and cross-encoder reranking."""

import asyncio
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import numpy as np
import structlog
from opensearchpy import AsyncOpenSearch
from sentence_transformers import SentenceTransformer, CrossEncoder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, and_, or_
from sqlalchemy.orm import selectinload

from api.core.config import get_settings
from api.core.database import get_db
from api.models.signal import Signal
from api.models.workspace import Workspace

logger = structlog.get_logger()
settings = get_settings()


class HybridSearchService:
    """Hybrid search service combining multiple retrieval methods."""
    
    def __init__(self):
        self.opensearch_client: Optional[AsyncOpenSearch] = None
        self.embedding_model: Optional[SentenceTransformer] = None
        self.reranker: Optional[CrossEncoder] = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize search components."""
        if self._initialized:
            return
        
        try:
            # Initialize OpenSearch client
            self.opensearch_client = AsyncOpenSearch(
                hosts=[settings.opensearch_url],
                use_ssl=False,
                verify_certs=False,
                timeout=30,
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Initialize cross-encoder for reranking
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
            
            # Create OpenSearch index if it doesn't exist
            await self._ensure_index_exists()
            
            self._initialized = True
            logger.info("Hybrid search service initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize search service: {e}")
            raise
    
    async def _ensure_index_exists(self):
        """Ensure OpenSearch index exists with proper mapping."""
        index_name = "signals"
        
        if not await self.opensearch_client.indices.exists(index=index_name):
            mapping = {
                "mappings": {
                    "properties": {
                        "signal_id": {"type": "keyword"},
                        "workspace_id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "standard",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "standard"
                        },
                        "source": {"type": "keyword"},
                        "url": {"type": "keyword"},
                        "entities": {
                            "type": "object",
                            "properties": {
                                "industries": {"type": "keyword"},
                                "technologies": {"type": "keyword"},
                                "companies": {"type": "keyword"},
                                "monetization_models": {"type": "keyword"}
                            }
                        },
                        "created_at": {"type": "date"},
                        "published_at": {"type": "date"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": 384  # all-MiniLM-L6-v2 dimension
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 0,
                    "analysis": {
                        "analyzer": {
                            "standard": {
                                "type": "standard",
                                "stopwords": "_english_"
                            }
                        }
                    }
                }
            }
            
            await self.opensearch_client.indices.create(
                index=index_name,
                body=mapping
            )
            logger.info(f"Created OpenSearch index: {index_name}")
    
    async def index_signal(self, signal: Signal):
        """Index a signal for search."""
        if not self._initialized:
            await self.initialize()
        
        try:
            # Generate embedding
            text_content = f"{signal.title or ''} {signal.content}"
            embedding = self.embedding_model.encode(text_content).tolist()
            
            # Prepare document
            doc = {
                "signal_id": str(signal.id),
                "workspace_id": str(signal.workspace_id),
                "title": signal.title or "",
                "content": signal.content,
                "source": signal.source,
                "url": signal.url,
                "entities": signal.entities or {},
                "created_at": signal.created_at.isoformat(),
                "published_at": signal.published_at.isoformat() if signal.published_at else None,
                "embedding": embedding
            }
            
            # Index document
            await self.opensearch_client.index(
                index="signals",
                id=str(signal.id),
                body=doc
            )
            
            logger.debug(f"Indexed signal: {signal.id}")
            
        except Exception as e:
            logger.error(f"Failed to index signal {signal.id}: {e}")
            raise
    
    async def search(
        self,
        workspace_id: UUID,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        hybrid_weights: Optional[Dict[str, float]] = None
    ) -> List[Dict[str, Any]]:
        """Perform hybrid search combining BM25, vector search, and reranking."""
        if not self._initialized:
            await self.initialize()
        
        # Default hybrid weights
        if hybrid_weights is None:
            hybrid_weights = {
                "bm25": 0.4,
                "vector": 0.4,
                "rerank": 0.2
            }
        
        try:
            # Step 1: BM25 search
            bm25_results = await self._bm25_search(workspace_id, query, filters, limit * 2)
            
            # Step 2: Vector search
            vector_results = await self._vector_search(workspace_id, query, filters, limit * 2)
            
            # Step 3: Combine and deduplicate results
            combined_results = self._combine_results(
                bm25_results, 
                vector_results, 
                hybrid_weights
            )
            
            # Step 4: Cross-encoder reranking
            reranked_results = await self._rerank_results(query, combined_results[:limit * 2])
            
            # Step 5: Get full signal data from database
            final_results = await self._enrich_results(reranked_results[:limit])
            
            return final_results
            
        except Exception as e:
            logger.error(f"Hybrid search failed: {e}")
            return []
    
    async def _bm25_search(
        self,
        workspace_id: UUID,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Perform BM25 text search."""
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"workspace_id": str(workspace_id)}},
                        {
                            "multi_match": {
                                "query": query,
                                "fields": ["title^2", "content"],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        }
                    ]
                }
            },
            "size": limit,
            "_source": ["signal_id", "title", "content", "source", "entities"]
        }
        
        # Add filters
        if filters:
            filter_clauses = []
            
            if "sources" in filters:
                filter_clauses.append({"terms": {"source": filters["sources"]}})
            
            if "industries" in filters:
                filter_clauses.append({"terms": {"entities.industries": filters["industries"]}})
            
            if "date_range" in filters:
                date_filter = {"range": {"created_at": {}}}
                if "from" in filters["date_range"]:
                    date_filter["range"]["created_at"]["gte"] = filters["date_range"]["from"]
                if "to" in filters["date_range"]:
                    date_filter["range"]["created_at"]["lte"] = filters["date_range"]["to"]
                filter_clauses.append(date_filter)
            
            if filter_clauses:
                search_body["query"]["bool"]["filter"] = filter_clauses
        
        try:
            response = await self.opensearch_client.search(
                index="signals",
                body=search_body
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                results.append({
                    "signal_id": hit["_source"]["signal_id"],
                    "score": hit["_score"],
                    "method": "bm25",
                    "title": hit["_source"]["title"],
                    "content": hit["_source"]["content"][:200] + "...",
                    "source": hit["_source"]["source"],
                    "entities": hit["_source"]["entities"]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"BM25 search failed: {e}")
            return []
    
    async def _vector_search(
        self,
        workspace_id: UUID,
        query: str,
        filters: Optional[Dict[str, Any]],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Perform vector similarity search."""
        # Generate query embedding
        query_embedding = self.embedding_model.encode(query).tolist()
        
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {"term": {"workspace_id": str(workspace_id)}},
                        {
                            "knn": {
                                "embedding": {
                                    "vector": query_embedding,
                                    "k": limit
                                }
                            }
                        }
                    ]
                }
            },
            "size": limit,
            "_source": ["signal_id", "title", "content", "source", "entities"]
        }
        
        # Add filters (same as BM25)
        if filters:
            filter_clauses = []
            
            if "sources" in filters:
                filter_clauses.append({"terms": {"source": filters["sources"]}})
            
            if "industries" in filters:
                filter_clauses.append({"terms": {"entities.industries": filters["industries"]}})
            
            if "date_range" in filters:
                date_filter = {"range": {"created_at": {}}}
                if "from" in filters["date_range"]:
                    date_filter["range"]["created_at"]["gte"] = filters["date_range"]["from"]
                if "to" in filters["date_range"]:
                    date_filter["range"]["created_at"]["lte"] = filters["date_range"]["to"]
                filter_clauses.append(date_filter)
            
            if filter_clauses:
                search_body["query"]["bool"]["filter"] = filter_clauses
        
        try:
            response = await self.opensearch_client.search(
                index="signals",
                body=search_body
            )
            
            results = []
            for hit in response["hits"]["hits"]:
                results.append({
                    "signal_id": hit["_source"]["signal_id"],
                    "score": hit["_score"],
                    "method": "vector",
                    "title": hit["_source"]["title"],
                    "content": hit["_source"]["content"][:200] + "...",
                    "source": hit["_source"]["source"],
                    "entities": hit["_source"]["entities"]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _combine_results(
        self,
        bm25_results: List[Dict[str, Any]],
        vector_results: List[Dict[str, Any]],
        weights: Dict[str, float]
    ) -> List[Dict[str, Any]]:
        """Combine BM25 and vector search results with weighted scoring."""
        # Create a map of signal_id to combined result
        combined = {}
        
        # Normalize scores to 0-1 range
        if bm25_results:
            max_bm25_score = max(r["score"] for r in bm25_results)
            for result in bm25_results:
                signal_id = result["signal_id"]
                normalized_score = result["score"] / max_bm25_score if max_bm25_score > 0 else 0
                
                combined[signal_id] = {
                    **result,
                    "bm25_score": normalized_score,
                    "vector_score": 0,
                    "combined_score": normalized_score * weights["bm25"]
                }
        
        if vector_results:
            max_vector_score = max(r["score"] for r in vector_results)
            for result in vector_results:
                signal_id = result["signal_id"]
                normalized_score = result["score"] / max_vector_score if max_vector_score > 0 else 0
                
                if signal_id in combined:
                    # Update existing result
                    combined[signal_id]["vector_score"] = normalized_score
                    combined[signal_id]["combined_score"] += normalized_score * weights["vector"]
                    combined[signal_id]["method"] = "hybrid"
                else:
                    # New result from vector search only
                    combined[signal_id] = {
                        **result,
                        "bm25_score": 0,
                        "vector_score": normalized_score,
                        "combined_score": normalized_score * weights["vector"],
                        "method": "vector"
                    }
        
        # Sort by combined score
        results = list(combined.values())
        results.sort(key=lambda x: x["combined_score"], reverse=True)
        
        return results
    
    async def _rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Rerank results using cross-encoder."""
        if not results or not self.reranker:
            return results
        
        try:
            # Prepare query-document pairs for cross-encoder
            pairs = []
            for result in results:
                doc_text = f"{result['title']} {result['content']}"
                pairs.append([query, doc_text])
            
            # Get reranking scores
            rerank_scores = self.reranker.predict(pairs)
            
            # Update results with rerank scores
            for i, result in enumerate(results):
                result["rerank_score"] = float(rerank_scores[i])
                # Combine with existing score
                result["final_score"] = (
                    result["combined_score"] * 0.7 + 
                    result["rerank_score"] * 0.3
                )
            
            # Sort by final score
            results.sort(key=lambda x: x["final_score"], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Reranking failed: {e}")
            # Return original results if reranking fails
            return results
    
    async def _enrich_results(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Enrich results with full signal data from database."""
        if not results:
            return []
        
        signal_ids = [UUID(r["signal_id"]) for r in results]
        
        # Get full signal data
        async with AsyncSession(bind=None) as session:  # This needs proper session handling
            query = select(Signal).where(Signal.id.in_(signal_ids))
            result = await session.execute(query)
            signals = result.scalars().all()
            
            # Create lookup map
            signal_map = {str(s.id): s for s in signals}
            
            # Enrich results
            enriched_results = []
            for result in results:
                signal_id = result["signal_id"]
                if signal_id in signal_map:
                    signal = signal_map[signal_id]
                    enriched_results.append({
                        "id": signal_id,
                        "title": signal.title,
                        "content": signal.content,
                        "source": signal.source,
                        "url": signal.url,
                        "entities": signal.entities or {},
                        "metadata": signal.metadata or {},
                        "created_at": signal.created_at.isoformat(),
                        "published_at": signal.published_at.isoformat() if signal.published_at else None,
                        "search_score": result["final_score"],
                        "search_method": result["method"],
                        "score_breakdown": {
                            "bm25": result.get("bm25_score", 0),
                            "vector": result.get("vector_score", 0),
                            "rerank": result.get("rerank_score", 0),
                            "combined": result.get("combined_score", 0),
                            "final": result["final_score"]
                        }
                    })
            
            return enriched_results
    
    async def search_trends(
        self,
        workspace_id: UUID,
        query: str,
        time_window_days: int = 30,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search for trending topics and patterns."""
        filters = {
            "date_range": {
                "from": f"now-{time_window_days}d"
            }
        }
        
        results = await self.search(workspace_id, query, filters, limit)
        
        # Add trend analysis
        for result in results:
            # Simple trend indicators (in production, use more sophisticated analysis)
            result["trend_indicators"] = {
                "recency_score": self._calculate_recency_score(result["created_at"]),
                "source_diversity": len(set(r["source"] for r in results[:5])),
                "entity_overlap": len(result["entities"].get("industries", [])),
            }
        
        return results
    
    def _calculate_recency_score(self, created_at: str) -> float:
        """Calculate recency score (0-1, higher = more recent)."""
        from datetime import datetime, timezone
        
        try:
            created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            days_old = (now - created_date).days
            
            # Exponential decay: score = e^(-days/7)
            import math
            return math.exp(-days_old / 7.0)
        except Exception:
            return 0.0
    
    async def search_whitespace(
        self,
        workspace_id: UUID,
        industry: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search for whitespace opportunities in a specific industry."""
        # Search for signals in the industry
        filters = {
            "industries": [industry]
        }
        
        # Use broad queries to find gaps
        gap_queries = [
            f"problems in {industry}",
            f"challenges {industry}",
            f"missing {industry}",
            f"need {industry}",
            f"frustration {industry}",
            f"wish {industry} had"
        ]
        
        all_results = []
        for query in gap_queries:
            results = await self.search(workspace_id, query, filters, limit // len(gap_queries))
            all_results.extend(results)
        
        # Deduplicate and analyze for whitespace patterns
        seen_ids = set()
        unique_results = []
        for result in all_results:
            if result["id"] not in seen_ids:
                seen_ids.add(result["id"])
                unique_results.append(result)
        
        # Add whitespace analysis
        for result in unique_results:
            result["whitespace_indicators"] = {
                "problem_keywords": self._extract_problem_keywords(result["content"]),
                "solution_gap_score": self._calculate_solution_gap_score(result["content"]),
                "market_need_strength": result["search_score"]
            }
        
        return unique_results[:limit]
    
    def _extract_problem_keywords(self, content: str) -> List[str]:
        """Extract problem-indicating keywords from content."""
        problem_keywords = [
            "problem", "issue", "challenge", "difficulty", "struggle",
            "frustration", "pain", "missing", "lack", "need", "want",
            "wish", "hope", "better", "improve", "fix", "solve"
        ]
        
        content_lower = content.lower()
        found_keywords = [kw for kw in problem_keywords if kw in content_lower]
        return found_keywords
    
    def _calculate_solution_gap_score(self, content: str) -> float:
        """Calculate how much the content indicates a solution gap."""
        gap_indicators = [
            "no solution", "doesn't exist", "missing", "gap in market",
            "nobody does", "wish there was", "need something", "looking for"
        ]
        
        content_lower = content.lower()
        gap_count = sum(1 for indicator in gap_indicators if indicator in content_lower)
        
        return min(gap_count / len(gap_indicators), 1.0)


# Global search service instance
search_service = HybridSearchService()
