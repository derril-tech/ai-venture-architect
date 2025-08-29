"""Tests for hybrid search service."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch, AsyncMock
from uuid import uuid4

from api.services.search import HybridSearchService


class TestHybridSearchService:
    """Test cases for HybridSearchService."""
    
    @pytest_asyncio.fixture
    async def search_service(self):
        """Create search service instance."""
        service = HybridSearchService()
        # Mock external dependencies
        service.opensearch_client = Mock()
        service.embedding_model = Mock()
        service.reranker = Mock()
        service._initialized = True
        return service
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test service initialization."""
        service = HybridSearchService()
        assert not service._initialized
        
        # Mock dependencies for initialization
        with patch('api.services.search.AsyncOpenSearch') as mock_opensearch, \
             patch('api.services.search.SentenceTransformer') as mock_transformer, \
             patch('api.services.search.CrossEncoder') as mock_encoder:
            
            mock_opensearch.return_value.indices.exists = AsyncMock(return_value=False)
            mock_opensearch.return_value.indices.create = AsyncMock()
            
            await service.initialize()
            
            assert service._initialized
            assert service.opensearch_client is not None
            assert service.embedding_model is not None
            assert service.reranker is not None
    
    @pytest.mark.asyncio
    async def test_bm25_search(self, search_service):
        """Test BM25 text search."""
        workspace_id = uuid4()
        query = "AI machine learning"
        
        # Mock OpenSearch response
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_score": 1.5,
                        "_source": {
                            "signal_id": "signal-1",
                            "title": "AI ML Platform",
                            "content": "Advanced machine learning platform",
                            "source": "tech_blog",
                            "entities": {"industries": ["ai_ml"]}
                        }
                    }
                ]
            }
        }
        
        search_service.opensearch_client.search = AsyncMock(return_value=mock_response)
        
        results = await search_service._bm25_search(workspace_id, query, None, 10)
        
        assert len(results) == 1
        assert results[0]["signal_id"] == "signal-1"
        assert results[0]["method"] == "bm25"
        assert results[0]["score"] == 1.5
    
    @pytest.mark.asyncio
    async def test_vector_search(self, search_service):
        """Test vector similarity search."""
        workspace_id = uuid4()
        query = "fintech innovation"
        
        # Mock embedding generation
        search_service.embedding_model.encode.return_value = [0.1, 0.2, 0.3]
        
        # Mock OpenSearch response
        mock_response = {
            "hits": {
                "hits": [
                    {
                        "_score": 0.95,
                        "_source": {
                            "signal_id": "signal-2",
                            "title": "Fintech Startup",
                            "content": "Innovative financial technology solution",
                            "source": "startup_news",
                            "entities": {"industries": ["fintech"]}
                        }
                    }
                ]
            }
        }
        
        search_service.opensearch_client.search = AsyncMock(return_value=mock_response)
        
        results = await search_service._vector_search(workspace_id, query, None, 10)
        
        assert len(results) == 1
        assert results[0]["signal_id"] == "signal-2"
        assert results[0]["method"] == "vector"
        assert results[0]["score"] == 0.95
    
    def test_combine_results(self, search_service):
        """Test combining BM25 and vector search results."""
        bm25_results = [
            {"signal_id": "signal-1", "score": 1.5, "title": "AI Platform", "method": "bm25"},
            {"signal_id": "signal-2", "score": 1.2, "title": "ML Tool", "method": "bm25"}
        ]
        
        vector_results = [
            {"signal_id": "signal-2", "score": 0.95, "title": "ML Tool", "method": "vector"},
            {"signal_id": "signal-3", "score": 0.87, "title": "Data Analytics", "method": "vector"}
        ]
        
        weights = {"bm25": 0.4, "vector": 0.4, "rerank": 0.2}
        
        combined = search_service._combine_results(bm25_results, vector_results, weights)
        
        # Should have 3 unique results
        assert len(combined) == 3
        
        # signal-2 should have both scores
        signal_2 = next(r for r in combined if r["signal_id"] == "signal-2")
        assert signal_2["method"] == "hybrid"
        assert signal_2["bm25_score"] > 0
        assert signal_2["vector_score"] > 0
        
        # Results should be sorted by combined score
        assert combined[0]["combined_score"] >= combined[1]["combined_score"]
    
    @pytest.mark.asyncio
    async def test_rerank_results(self, search_service):
        """Test cross-encoder reranking."""
        query = "AI startup funding"
        results = [
            {
                "signal_id": "signal-1",
                "title": "AI Startup Raises $10M",
                "content": "Artificial intelligence startup secures funding",
                "combined_score": 0.8
            },
            {
                "signal_id": "signal-2", 
                "title": "Machine Learning Platform",
                "content": "New ML platform for developers",
                "combined_score": 0.7
            }
        ]
        
        # Mock reranker predictions
        search_service.reranker.predict.return_value = [0.9, 0.6]
        
        reranked = await search_service._rerank_results(query, results)
        
        assert len(reranked) == 2
        assert reranked[0]["rerank_score"] == 0.9
        assert reranked[1]["rerank_score"] == 0.6
        
        # Should be sorted by final score
        assert reranked[0]["final_score"] >= reranked[1]["final_score"]
    
    @pytest.mark.asyncio
    async def test_search_trends(self, search_service):
        """Test trend search functionality."""
        workspace_id = uuid4()
        query = "AI trends"
        
        # Mock the main search method
        mock_results = [
            {
                "id": "signal-1",
                "title": "AI Trend Analysis",
                "content": "Latest trends in artificial intelligence",
                "created_at": "2024-01-15T10:00:00Z",
                "search_score": 0.9
            }
        ]
        
        with patch.object(search_service, 'search', return_value=mock_results):
            results = await search_service.search_trends(workspace_id, query, 30, 10)
            
            assert len(results) == 1
            assert "trend_indicators" in results[0]
            assert "recency_score" in results[0]["trend_indicators"]
    
    @pytest.mark.asyncio
    async def test_search_whitespace(self, search_service):
        """Test whitespace opportunity search."""
        workspace_id = uuid4()
        industry = "fintech"
        
        # Mock search results for gap queries
        mock_results = [
            {
                "id": "signal-1",
                "title": "Fintech Problems",
                "content": "Major challenges in financial technology sector",
                "search_score": 0.8
            }
        ]
        
        with patch.object(search_service, 'search', return_value=mock_results):
            results = await search_service.search_whitespace(workspace_id, industry, 20)
            
            assert len(results) <= 20
            for result in results:
                assert "whitespace_indicators" in result
                assert "problem_keywords" in result["whitespace_indicators"]
                assert "solution_gap_score" in result["whitespace_indicators"]
    
    def test_extract_problem_keywords(self, search_service):
        """Test problem keyword extraction."""
        content = "This is a major problem in the industry. Users struggle with the lack of good solutions."
        
        keywords = search_service._extract_problem_keywords(content)
        
        assert "problem" in keywords
        assert "struggle" in keywords
        assert "lack" in keywords
    
    def test_calculate_solution_gap_score(self, search_service):
        """Test solution gap score calculation."""
        content_with_gaps = "No solution exists for this problem. There's a gap in the market."
        content_without_gaps = "Many solutions are available. The market is well served."
        
        score_with_gaps = search_service._calculate_solution_gap_score(content_with_gaps)
        score_without_gaps = search_service._calculate_solution_gap_score(content_without_gaps)
        
        assert score_with_gaps > score_without_gaps
        assert 0 <= score_with_gaps <= 1
        assert 0 <= score_without_gaps <= 1
    
    def test_calculate_recency_score(self, search_service):
        """Test recency score calculation."""
        from datetime import datetime, timezone
        
        # Recent date
        recent_date = datetime.now(timezone.utc).isoformat()
        recent_score = search_service._calculate_recency_score(recent_date)
        
        # Old date
        old_date = "2020-01-01T00:00:00Z"
        old_score = search_service._calculate_recency_score(old_date)
        
        assert recent_score > old_score
        assert 0 <= recent_score <= 1
        assert 0 <= old_score <= 1
    
    @pytest.mark.asyncio
    async def test_index_signal(self, search_service):
        """Test signal indexing."""
        from api.models.signal import Signal
        from uuid import uuid4
        
        signal = Signal(
            id=uuid4(),
            workspace_id=uuid4(),
            source="test_source",
            title="Test Signal",
            content="This is test content for indexing",
            url="https://example.com/test"
        )
        
        # Mock embedding generation
        search_service.embedding_model.encode.return_value = [0.1, 0.2, 0.3]
        
        # Mock OpenSearch indexing
        search_service.opensearch_client.index = AsyncMock()
        
        await search_service.index_signal(signal)
        
        # Verify indexing was called
        search_service.opensearch_client.index.assert_called_once()
        call_args = search_service.opensearch_client.index.call_args
        
        assert call_args[1]["index"] == "signals"
        assert call_args[1]["id"] == str(signal.id)
        assert "embedding" in call_args[1]["body"]
