"""Search endpoints for hybrid search functionality."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.auth import get_current_workspace
from api.services.search import search_service
from api.models.user import UserWorkspace

router = APIRouter()


class SearchRequest(BaseModel):
    """Search request model."""
    query: str = Field(..., min_length=1, max_length=500)
    filters: Optional[Dict[str, Any]] = None
    limit: int = Field(default=20, ge=1, le=100)
    hybrid_weights: Optional[Dict[str, float]] = None


class SearchResponse(BaseModel):
    """Search response model."""
    results: List[Dict[str, Any]]
    total_results: int
    query: str
    search_time_ms: float
    method: str = "hybrid"


class TrendSearchRequest(BaseModel):
    """Trend search request model."""
    query: str = Field(..., min_length=1, max_length=500)
    time_window_days: int = Field(default=30, ge=1, le=365)
    limit: int = Field(default=10, ge=1, le=50)


class WhitespaceSearchRequest(BaseModel):
    """Whitespace search request model."""
    industry: str = Field(..., min_length=1, max_length=100)
    limit: int = Field(default=20, ge=1, le=50)


@router.post("/search", response_model=SearchResponse)
async def hybrid_search(
    request: SearchRequest,
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Perform hybrid search across market signals."""
    import time
    
    start_time = time.time()
    
    # Initialize search service if needed
    await search_service.initialize()
    
    # Perform search
    results = await search_service.search(
        workspace_id=user_workspace.workspace_id,
        query=request.query,
        filters=request.filters,
        limit=request.limit,
        hybrid_weights=request.hybrid_weights
    )
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        results=results,
        total_results=len(results),
        query=request.query,
        search_time_ms=search_time
    )


@router.post("/search/trends", response_model=SearchResponse)
async def search_trends(
    request: TrendSearchRequest,
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Search for trending topics and patterns."""
    import time
    
    start_time = time.time()
    
    # Initialize search service if needed
    await search_service.initialize()
    
    # Perform trend search
    results = await search_service.search_trends(
        workspace_id=user_workspace.workspace_id,
        query=request.query,
        time_window_days=request.time_window_days,
        limit=request.limit
    )
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        results=results,
        total_results=len(results),
        query=request.query,
        search_time_ms=search_time,
        method="trend_analysis"
    )


@router.post("/search/whitespace", response_model=SearchResponse)
async def search_whitespace(
    request: WhitespaceSearchRequest,
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Search for whitespace opportunities in a specific industry."""
    import time
    
    start_time = time.time()
    
    # Initialize search service if needed
    await search_service.initialize()
    
    # Perform whitespace search
    results = await search_service.search_whitespace(
        workspace_id=user_workspace.workspace_id,
        industry=request.industry,
        limit=request.limit
    )
    
    search_time = (time.time() - start_time) * 1000
    
    return SearchResponse(
        results=results,
        total_results=len(results),
        query=f"whitespace in {request.industry}",
        search_time_ms=search_time,
        method="whitespace_analysis"
    )


@router.get("/search/suggestions")
async def get_search_suggestions(
    q: str = Query(..., min_length=1, max_length=100),
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Get search suggestions based on query prefix."""
    # This would typically use a suggestion service or autocomplete index
    # For now, return some basic suggestions
    
    suggestions = []
    
    # Industry-based suggestions
    industries = [
        "ai and machine learning", "fintech", "healthcare", "ecommerce",
        "gaming", "education", "productivity", "security", "iot"
    ]
    
    for industry in industries:
        if q.lower() in industry.lower():
            suggestions.append({
                "text": f"{industry} trends",
                "type": "trend",
                "category": "industry"
            })
            suggestions.append({
                "text": f"{industry} startups",
                "type": "search",
                "category": "industry"
            })
    
    # Technology-based suggestions
    technologies = [
        "artificial intelligence", "blockchain", "cloud computing",
        "mobile apps", "web development", "data analytics"
    ]
    
    for tech in technologies:
        if q.lower() in tech.lower():
            suggestions.append({
                "text": f"{tech} opportunities",
                "type": "whitespace",
                "category": "technology"
            })
    
    return {
        "suggestions": suggestions[:10],
        "query": q
    }


@router.get("/search/filters")
async def get_search_filters(
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Get available search filters for the workspace."""
    # This would typically query the database for available filter values
    # For now, return static filter options
    
    return {
        "sources": [
            {"value": "product_hunt", "label": "Product Hunt", "count": 150},
            {"value": "github", "label": "GitHub", "count": 200},
            {"value": "rss", "label": "RSS/News", "count": 300},
            {"value": "crunchbase", "label": "Crunchbase", "count": 50},
            {"value": "google_trends", "label": "Google Trends", "count": 100}
        ],
        "industries": [
            {"value": "software", "label": "Software", "count": 180},
            {"value": "ai_ml", "label": "AI/ML", "count": 120},
            {"value": "fintech", "label": "FinTech", "count": 90},
            {"value": "healthcare", "label": "Healthcare", "count": 70},
            {"value": "ecommerce", "label": "E-commerce", "count": 85},
            {"value": "gaming", "label": "Gaming", "count": 45},
            {"value": "education", "label": "Education", "count": 60},
            {"value": "productivity", "label": "Productivity", "count": 95},
            {"value": "security", "label": "Security", "count": 55},
            {"value": "iot", "label": "IoT", "count": 40}
        ],
        "technologies": [
            {"value": "python", "label": "Python", "count": 80},
            {"value": "javascript", "label": "JavaScript", "count": 90},
            {"value": "react", "label": "React", "count": 70},
            {"value": "nodejs", "label": "Node.js", "count": 60},
            {"value": "aws", "label": "AWS", "count": 50},
            {"value": "docker", "label": "Docker", "count": 45},
            {"value": "kubernetes", "label": "Kubernetes", "count": 30}
        ]
    }


@router.get("/search/analytics")
async def get_search_analytics(
    user_workspace: UserWorkspace = Depends(get_current_workspace),
    db: AsyncSession = Depends(get_db),
):
    """Get search analytics and insights."""
    # This would typically query analytics data
    # For now, return mock analytics
    
    return {
        "total_searches": 1250,
        "avg_results_per_search": 15.3,
        "avg_search_time_ms": 450,
        "top_queries": [
            {"query": "ai startups", "count": 45},
            {"query": "fintech trends", "count": 38},
            {"query": "saas opportunities", "count": 32},
            {"query": "mobile apps", "count": 28},
            {"query": "healthcare innovation", "count": 25}
        ],
        "top_sources": [
            {"source": "rss", "percentage": 35},
            {"source": "github", "percentage": 25},
            {"source": "product_hunt", "percentage": 20},
            {"source": "crunchbase", "percentage": 15},
            {"source": "google_trends", "percentage": 5}
        ],
        "search_performance": {
            "hybrid_score": 0.85,
            "bm25_contribution": 0.4,
            "vector_contribution": 0.4,
            "rerank_contribution": 0.2
        }
    }
