"""Pytest configuration and fixtures for API tests."""

import asyncio
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from api.main import create_app
from api.core.database import Base, get_db
from api.core.config import get_settings
from api.models.workspace import Workspace
from api.models.user import User, UserWorkspace, UserRole
from api.models.signal import Signal
from api.models.idea import Idea, IdeaStatus

# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Create test engine
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    # Create tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async with TestSessionLocal() as session:
        yield session
    
    # Drop tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def app():
    """Create test FastAPI app."""
    app = create_app()
    
    # Override database dependency
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    return app


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_workspace(db_session: AsyncSession) -> Workspace:
    """Create test workspace."""
    workspace = Workspace(
        name="Test Workspace",
        slug="test-workspace",
        description="Test workspace for unit tests"
    )
    db_session.add(workspace)
    await db_session.commit()
    await db_session.refresh(workspace)
    return workspace


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create test user."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password="hashed_password_here",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_user_workspace(
    db_session: AsyncSession, 
    test_user: User, 
    test_workspace: Workspace
) -> UserWorkspace:
    """Create test user-workspace relationship."""
    user_workspace = UserWorkspace(
        user_id=test_user.id,
        workspace_id=test_workspace.id,
        role=UserRole.OWNER
    )
    db_session.add(user_workspace)
    await db_session.commit()
    await db_session.refresh(user_workspace)
    return user_workspace


@pytest_asyncio.fixture
async def test_signals(db_session: AsyncSession, test_workspace: Workspace) -> list[Signal]:
    """Create test signals."""
    signals = []
    
    signal_data = [
        {
            "source": "product_hunt",
            "title": "AI-Powered Analytics Tool",
            "content": "Revolutionary analytics platform using machine learning to provide insights.",
            "url": "https://example.com/product1",
            "entities": {"industries": ["software", "ai_ml"], "technologies": ["python", "tensorflow"]},
            "metadata": {"votes": 150, "comments": 25}
        },
        {
            "source": "github",
            "title": "Open Source ML Framework",
            "content": "New machine learning framework for rapid prototyping and deployment.",
            "url": "https://github.com/example/ml-framework",
            "entities": {"industries": ["ai_ml"], "technologies": ["python", "pytorch"]},
            "metadata": {"stars": 1200, "forks": 89}
        },
        {
            "source": "rss",
            "title": "Fintech Startup Raises $10M",
            "content": "Innovative fintech company secures Series A funding for expansion.",
            "url": "https://news.example.com/fintech-funding",
            "entities": {"industries": ["fintech"], "companies": ["FinTech Corp"]},
            "metadata": {"funding_amount": 10000000}
        }
    ]
    
    for data in signal_data:
        signal = Signal(
            workspace_id=test_workspace.id,
            source=data["source"],
            title=data["title"],
            content=data["content"],
            url=data["url"],
            entities=data["entities"],
            metadata=data["metadata"]
        )
        signals.append(signal)
        db_session.add(signal)
    
    await db_session.commit()
    
    for signal in signals:
        await db_session.refresh(signal)
    
    return signals


@pytest_asyncio.fixture
async def test_ideas(db_session: AsyncSession, test_workspace: Workspace) -> list[Idea]:
    """Create test ideas."""
    ideas = []
    
    idea_data = [
        {
            "title": "AI-Powered Market Research Platform",
            "description": "Automated market research using AI agents and real-time data analysis.",
            "uvp": "10x faster market research with AI-powered insights",
            "problem_statement": "Market research is slow, expensive, and often outdated",
            "solution_approach": "Use AI agents to continuously monitor and analyze market signals",
            "icps": {"primary": "Venture capital firms", "secondary": "Strategy consultants"},
            "target_segments": ["venture_capital", "consulting", "enterprise"],
            "mvp_features": ["Signal ingestion", "AI analysis", "Report generation"],
            "tam_sam_som": {"tam": 50000, "sam": 5000, "som": 500},
            "attractiveness_score": 8.5,
            "confidence_score": 7.8,
            "status": IdeaStatus.COMPLETED
        },
        {
            "title": "Automated Competitor Intelligence",
            "description": "Real-time competitor monitoring and analysis platform.",
            "uvp": "Never miss a competitor move with automated intelligence",
            "problem_statement": "Companies struggle to track competitor activities effectively",
            "solution_approach": "Automated web scraping and AI analysis of competitor data",
            "icps": {"primary": "Product managers", "secondary": "Marketing teams"},
            "target_segments": ["saas", "ecommerce", "startups"],
            "mvp_features": ["Competitor tracking", "Price monitoring", "Feature analysis"],
            "tam_sam_som": {"tam": 25000, "sam": 2500, "som": 250},
            "attractiveness_score": 7.2,
            "confidence_score": 8.1,
            "status": IdeaStatus.COMPLETED
        }
    ]
    
    for data in idea_data:
        idea = Idea(
            workspace_id=test_workspace.id,
            title=data["title"],
            description=data["description"],
            uvp=data["uvp"],
            problem_statement=data["problem_statement"],
            solution_approach=data["solution_approach"],
            icps=data["icps"],
            target_segments=data["target_segments"],
            mvp_features=data["mvp_features"],
            tam_sam_som=data["tam_sam_som"],
            attractiveness_score=data["attractiveness_score"],
            confidence_score=data["confidence_score"],
            status=data["status"]
        )
        ideas.append(idea)
        db_session.add(idea)
    
    await db_session.commit()
    
    for idea in ideas:
        await db_session.refresh(idea)
    
    return ideas


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "choices": [
            {
                "message": {
                    "content": "This is a mock AI response for testing purposes."
                }
            }
        ]
    }


@pytest.fixture
def mock_search_results():
    """Mock search results."""
    return [
        {
            "id": "signal-1",
            "title": "Test Signal 1",
            "content": "This is test content for signal 1",
            "source": "test_source",
            "search_score": 0.95,
            "search_method": "hybrid"
        },
        {
            "id": "signal-2", 
            "title": "Test Signal 2",
            "content": "This is test content for signal 2",
            "source": "test_source",
            "search_score": 0.87,
            "search_method": "vector"
        }
    ]


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        "industry": "software",
        "target_segments": ["enterprise", "smb"],
        "geographic_scope": "global",
        "tam": 100000,
        "sam": 10000,
        "som": 1000,
        "growth_rate": 0.15,
        "competitive_intensity": "medium"
    }


@pytest.fixture
def sample_competitor_data():
    """Sample competitor data for testing."""
    return {
        "competitors": [
            {
                "name": "Competitor A",
                "url": "https://competitora.com",
                "pricing": {"starter": 29, "pro": 99, "enterprise": 299},
                "features": ["feature1", "feature2", "feature3"],
                "traction": {"customers": 5000, "funding": 10000000}
            },
            {
                "name": "Competitor B", 
                "url": "https://competitorb.com",
                "pricing": {"basic": 19, "premium": 79, "enterprise": 199},
                "features": ["feature1", "feature4", "feature5"],
                "traction": {"customers": 2500, "funding": 5000000}
            }
        ]
    }


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
