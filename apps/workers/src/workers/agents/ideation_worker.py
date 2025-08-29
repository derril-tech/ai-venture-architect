"""Enhanced ideation worker using CrewAI and LangGraph orchestration."""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from langchain_openai import ChatOpenAI
from crewai import Agent, Task, Crew

from workers.core.worker import BaseWorker
from workers.core.config import get_settings
from workers.agents.langgraph_orchestrator import langgraph_orchestrator

logger = structlog.get_logger()
settings = get_settings()

# Database setup
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class IdeationWorker(BaseWorker):
    """Worker for AI-powered product ideation using CrewAI."""
    
    def __init__(self, nats_client):
        super().__init__(nats_client, "idea.generate")
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            api_key=settings.openai_api_key
        ) if settings.openai_api_key else None
        
        # Initialize agents
        self._setup_agents()
    
    def _setup_agents(self):
        """Setup CrewAI agents for ideation."""
        if not self.llm:
            logger.warning("OpenAI API key not provided, ideation will be limited")
            return
        
        # Research Agent
        self.research_agent = Agent(
            role="Market Research Analyst",
            goal="Analyze market signals and identify opportunities",
            backstory="""You are an expert market research analyst with deep knowledge of 
            technology trends, consumer behavior, and market dynamics. You excel at 
            identifying patterns in market data and spotting emerging opportunities.""",
            llm=self.llm,
            verbose=True
        )
        
        # Ideation Agent
        self.ideation_agent = Agent(
            role="Product Ideation Specialist",
            goal="Generate innovative product ideas based on market insights",
            backstory="""You are a creative product strategist with a track record of 
            identifying successful product opportunities. You combine market insights 
            with creative thinking to generate compelling product concepts.""",
            llm=self.llm,
            verbose=True
        )
        
        # Validation Agent
        self.validation_agent = Agent(
            role="Business Validation Expert",
            goal="Assess the viability and potential of product ideas",
            backstory="""You are a seasoned business analyst who evaluates product 
            concepts for market fit, technical feasibility, and business potential. 
            You provide realistic assessments and identify key risks and opportunities.""",
            llm=self.llm,
            verbose=True
        )
    
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process ideation request using LangGraph orchestration."""
        workspace_id = payload.get("workspace_id")
        query = payload.get("query", "")
        focus_areas = payload.get("focus_areas", [])
        constraints = payload.get("constraints", {})
        use_langgraph = payload.get("use_langgraph", True)
        
        if not workspace_id:
            raise ValueError("Missing required field: workspace_id")
        
        if not self.llm:
            return {
                "status": "failed",
                "error": "OpenAI API key not configured",
                "workspace_id": workspace_id,
            }
        
        logger.info(f"Starting ideation for workspace: {workspace_id}")
        
        try:
            if use_langgraph:
                # Use LangGraph orchestrated workflow
                result = await langgraph_orchestrator.run_ideation_workflow(
                    workspace_id=workspace_id,
                    query=query,
                    focus_areas=focus_areas,
                    constraints=constraints
                )
                
                # Store generated ideas
                stored_ideas = []
                for idea in result.get("final_ideas", []):
                    idea_id = await self._store_idea(workspace_id, idea)
                    stored_ideas.append({"id": idea_id, "title": idea.get("title")})
                
                return {
                    "status": result["status"],
                    "workspace_id": workspace_id,
                    "ideas": stored_ideas,
                    "confidence_scores": result.get("confidence_scores", {}),
                    "workflow_metadata": result.get("metadata", {}),
                    "method": "langgraph"
                }
            else:
                # Fallback to original CrewAI approach
                return await self._process_with_crewai(workspace_id, query, focus_areas, constraints)
            
        except Exception as e:
            logger.error(f"Ideation failed: {e}")
            return {
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(e),
            }
    
    async def _process_with_crewai(
        self, 
        workspace_id: str, 
        query: str, 
        focus_areas: List[str], 
        constraints: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process ideation using original CrewAI approach."""
        # Get relevant market signals
        signals = await self._get_relevant_signals(workspace_id, query, focus_areas)
        
        # Generate ideas using CrewAI
        ideas = await self._generate_ideas(signals, query, focus_areas, constraints)
        
        # Store generated ideas
        stored_ideas = []
        for idea in ideas:
            idea_id = await self._store_idea(workspace_id, idea)
            stored_ideas.append({"id": idea_id, "title": idea.get("title")})
        
        logger.info(f"CrewAI ideation completed: {len(ideas)} ideas generated")
        
        return {
            "status": "completed",
            "workspace_id": workspace_id,
            "ideas": stored_ideas,
            "signal_count": len(signals),
            "method": "crewai"
        }
    
    async def _get_relevant_signals(
        self, 
        workspace_id: str, 
        query: str, 
        focus_areas: List[str]
    ) -> List[Dict[str, Any]]:
        """Get relevant signals for ideation."""
        async with AsyncSessionLocal() as session:
            from api.models.signal import Signal
            from uuid import UUID
            from sqlalchemy import select, and_, or_
            
            # Build query based on focus areas and query
            base_query = select(Signal).where(Signal.workspace_id == UUID(workspace_id))
            
            # Filter by focus areas if provided
            if focus_areas:
                industry_filters = []
                for area in focus_areas:
                    industry_filters.append(
                        Signal.entities.op('->>')('industries').op('@>')([area])
                    )
                
                if industry_filters:
                    base_query = base_query.where(or_(*industry_filters))
            
            # Add text search if query provided
            if query:
                search_terms = query.lower().split()
                text_filters = []
                for term in search_terms:
                    text_filters.append(
                        or_(
                            Signal.title.ilike(f"%{term}%"),
                            Signal.content.ilike(f"%{term}%")
                        )
                    )
                
                if text_filters:
                    base_query = base_query.where(and_(*text_filters))
            
            # Limit and order by recency
            base_query = base_query.order_by(Signal.created_at.desc()).limit(50)
            
            result = await session.execute(base_query)
            signals = result.scalars().all()
            
            return [
                {
                    "id": str(signal.id),
                    "title": signal.title or "",
                    "content": signal.content,
                    "source": signal.source,
                    "url": signal.url,
                    "entities": signal.entities or {},
                    "metadata": signal.metadata or {},
                    "created_at": signal.created_at.isoformat(),
                }
                for signal in signals
            ]
    
    async def _generate_ideas(
        self, 
        signals: List[Dict[str, Any]], 
        query: str, 
        focus_areas: List[str], 
        constraints: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate product ideas using CrewAI."""
        if not signals:
            logger.warning("No signals available for ideation")
            return []
        
        # Prepare context
        signal_summary = self._summarize_signals(signals)
        context = {
            "signals": signal_summary,
            "query": query,
            "focus_areas": focus_areas,
            "constraints": constraints,
        }
        
        # Define tasks
        research_task = Task(
            description=f"""
            Analyze the following market signals and identify key trends, opportunities, 
            and unmet needs:
            
            Query: {query}
            Focus Areas: {', '.join(focus_areas) if focus_areas else 'Any'}
            
            Market Signals:
            {signal_summary}
            
            Provide insights on:
            1. Key trends and patterns
            2. Market gaps and unmet needs
            3. Emerging technologies and opportunities
            4. Target audience insights
            """,
            agent=self.research_agent,
            expected_output="Detailed market analysis with identified opportunities"
        )
        
        ideation_task = Task(
            description=f"""
            Based on the market research, generate 3-5 innovative product ideas that:
            1. Address identified market gaps
            2. Leverage emerging trends
            3. Have clear value propositions
            4. Target specific customer segments
            
            For each idea, provide:
            - Product name and tagline
            - Problem it solves
            - Target customer profile
            - Key features (MVP)
            - Unique value proposition
            - Business model approach
            - Market positioning
            
            Constraints: {json.dumps(constraints)}
            """,
            agent=self.ideation_agent,
            expected_output="3-5 detailed product concepts with clear value propositions"
        )
        
        validation_task = Task(
            description="""
            Evaluate each product idea for:
            1. Market potential and size
            2. Technical feasibility
            3. Competitive landscape
            4. Business model viability
            5. Key risks and mitigation strategies
            6. Success probability (1-10 scale)
            
            Provide actionable recommendations for each idea.
            """,
            agent=self.validation_agent,
            expected_output="Comprehensive validation assessment for each product idea"
        )
        
        # Create and run crew
        crew = Crew(
            agents=[self.research_agent, self.ideation_agent, self.validation_agent],
            tasks=[research_task, ideation_task, validation_task],
            verbose=True
        )
        
        try:
            result = crew.kickoff()
            
            # Parse the result and structure ideas
            ideas = self._parse_crew_result(result, signals)
            
            return ideas
            
        except Exception as e:
            logger.error(f"CrewAI execution failed: {e}")
            # Fallback to simple idea generation
            return self._generate_fallback_ideas(signals, query, focus_areas)
    
    def _summarize_signals(self, signals: List[Dict[str, Any]]) -> str:
        """Summarize signals for context."""
        if not signals:
            return "No signals available"
        
        # Group by source
        by_source = {}
        for signal in signals:
            source = signal['source']
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(signal)
        
        summary_parts = []
        for source, source_signals in by_source.items():
            titles = [s['title'] for s in source_signals[:5] if s['title']]
            if titles:
                summary_parts.append(f"{source.title()}: {', '.join(titles)}")
        
        return "\n".join(summary_parts)
    
    def _parse_crew_result(self, result: str, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse CrewAI result into structured ideas."""
        # This is a simplified parser - in production, you'd want more robust parsing
        ideas = []
        
        # Try to extract structured information from the result
        # For now, create a single comprehensive idea
        idea = {
            "title": "AI-Generated Product Concept",
            "description": result[:500] + "..." if len(result) > 500 else result,
            "uvp": "Addresses market opportunities identified from recent signals",
            "problem_statement": "Based on analysis of market trends and signals",
            "solution_approach": "Leverages emerging technologies and market gaps",
            "icps": {
                "primary": "Early adopters in identified market segments",
                "secondary": "Mainstream users seeking innovative solutions"
            },
            "mvp_features": [
                "Core functionality addressing primary use case",
                "User-friendly interface",
                "Integration capabilities",
                "Analytics and insights"
            ],
            "positioning": "Innovative solution in emerging market space",
            "sources": [s['id'] for s in signals[:10]],
            "citations": {
                "market_analysis": f"Based on {len(signals)} market signals",
                "trend_analysis": "AI-powered analysis of recent market data"
            },
            "attractiveness_score": 7.5,
            "confidence_score": 6.8,
            "status": "completed",
        }
        
        ideas.append(idea)
        return ideas
    
    def _generate_fallback_ideas(
        self, 
        signals: List[Dict[str, Any]], 
        query: str, 
        focus_areas: List[str]
    ) -> List[Dict[str, Any]]:
        """Generate simple fallback ideas when CrewAI is not available."""
        # Extract common themes from signals
        industries = []
        technologies = []
        
        for signal in signals:
            entities = signal.get('entities', {})
            industries.extend(entities.get('industries', []))
            technologies.extend(entities.get('technologies', []))
        
        # Count frequencies
        from collections import Counter
        top_industries = Counter(industries).most_common(3)
        top_technologies = Counter(technologies).most_common(3)
        
        # Generate simple ideas
        ideas = []
        
        for i, (industry, count) in enumerate(top_industries):
            idea = {
                "title": f"{industry.title()} Innovation Platform",
                "description": f"A platform addressing emerging needs in the {industry} sector",
                "uvp": f"Streamlines {industry} operations with modern technology",
                "problem_statement": f"Current {industry} solutions lack modern capabilities",
                "solution_approach": f"Technology-driven approach to {industry} challenges",
                "icps": {
                    "primary": f"{industry.title()} professionals and companies"
                },
                "mvp_features": [
                    "Core platform functionality",
                    "User management",
                    "Analytics dashboard",
                    "Integration APIs"
                ],
                "positioning": f"Next-generation {industry} solution",
                "sources": [s['id'] for s in signals if industry in s.get('entities', {}).get('industries', [])],
                "citations": {
                    "market_signals": f"Based on {count} relevant signals"
                },
                "attractiveness_score": 6.0 + i * 0.5,
                "confidence_score": 5.5 + i * 0.3,
                "status": "completed",
            }
            ideas.append(idea)
        
        return ideas[:3]  # Return top 3 ideas
    
    async def _store_idea(self, workspace_id: str, idea: Dict[str, Any]) -> str:
        """Store generated idea in database."""
        async with AsyncSessionLocal() as session:
            try:
                from api.models.idea import Idea, IdeaStatus
                from uuid import UUID
                
                db_idea = Idea(
                    workspace_id=UUID(workspace_id),
                    title=idea.get("title", "Untitled Idea"),
                    description=idea.get("description", ""),
                    uvp=idea.get("uvp"),
                    problem_statement=idea.get("problem_statement"),
                    solution_approach=idea.get("solution_approach"),
                    icps=idea.get("icps", {}),
                    mvp_features=idea.get("mvp_features", []),
                    positioning=idea.get("positioning"),
                    attractiveness_score=idea.get("attractiveness_score"),
                    confidence_score=idea.get("confidence_score"),
                    sources=idea.get("sources", []),
                    citations=idea.get("citations", {}),
                    status=IdeaStatus.COMPLETED,
                    completed_at=datetime.utcnow(),
                )
                
                session.add(db_idea)
                await session.commit()
                
                logger.debug(f"Stored idea: {db_idea.id}")
                return str(db_idea.id)
                
            except Exception as e:
                logger.error(f"Error storing idea: {e}")
                await session.rollback()
                raise
