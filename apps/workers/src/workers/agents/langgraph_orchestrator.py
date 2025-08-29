"""LangGraph orchestrator for multi-agent ideation workflow."""

import json
from typing import Any, Dict, List, Optional, TypedDict, Annotated
from datetime import datetime
from uuid import uuid4

import structlog
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from crewai import Agent, Task, Crew

from workers.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class IdeationState(TypedDict):
    """State for the ideation workflow."""
    workspace_id: str
    query: str
    focus_areas: List[str]
    constraints: Dict[str, Any]
    
    # Data collected during workflow
    market_signals: List[Dict[str, Any]]
    competitor_analysis: Dict[str, Any]
    trend_analysis: Dict[str, Any]
    whitespace_analysis: Dict[str, Any]
    
    # Generated ideas and analysis
    raw_ideas: List[Dict[str, Any]]
    validated_ideas: List[Dict[str, Any]]
    business_models: List[Dict[str, Any]]
    tech_assessments: List[Dict[str, Any]]
    
    # Workflow control
    current_step: str
    confidence_scores: Dict[str, float]
    retry_count: int
    max_retries: int
    
    # Messages for agent communication
    messages: List[BaseMessage]
    
    # Final results
    final_ideas: List[Dict[str, Any]]
    export_ready: bool


class LangGraphOrchestrator:
    """LangGraph orchestrator for multi-agent ideation workflow."""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4-turbo-preview",
            temperature=0.7,
            api_key=settings.openai_api_key
        ) if settings.openai_api_key else None
        
        self.confidence_thresholds = {
            "market_research": 0.7,
            "competitor_analysis": 0.6,
            "idea_generation": 0.8,
            "business_validation": 0.7,
            "tech_feasibility": 0.6
        }
        
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow."""
        workflow = StateGraph(IdeationState)
        
        # Add nodes
        workflow.add_node("research_agent", self._research_node)
        workflow.add_node("competitor_agent", self._competitor_node)
        workflow.add_node("ideation_agent", self._ideation_node)
        workflow.add_node("business_agent", self._business_node)
        workflow.add_node("tech_agent", self._tech_node)
        workflow.add_node("validation_agent", self._validation_node)
        workflow.add_node("export_agent", self._export_node)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "research_agent",
            self._should_continue_research,
            {
                "continue": "competitor_agent",
                "retry": "research_agent",
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "competitor_agent",
            self._should_continue_competitor,
            {
                "continue": "ideation_agent",
                "retry": "competitor_agent",
                "skip": "ideation_agent"
            }
        )
        
        workflow.add_conditional_edges(
            "ideation_agent",
            self._should_continue_ideation,
            {
                "continue": "business_agent",
                "retry": "ideation_agent",
                "fail": END
            }
        )
        
        workflow.add_conditional_edges(
            "business_agent",
            self._should_continue_business,
            {
                "continue": "tech_agent",
                "retry": "business_agent",
                "skip": "tech_agent"
            }
        )
        
        workflow.add_conditional_edges(
            "tech_agent",
            self._should_continue_tech,
            {
                "continue": "validation_agent",
                "retry": "tech_agent",
                "skip": "validation_agent"
            }
        )
        
        workflow.add_conditional_edges(
            "validation_agent",
            self._should_continue_validation,
            {
                "continue": "export_agent",
                "retry": "validation_agent",
                "fail": END
            }
        )
        
        workflow.add_edge("export_agent", END)
        
        # Set entry point
        workflow.set_entry_point("research_agent")
        
        return workflow.compile()
    
    async def run_ideation_workflow(
        self,
        workspace_id: str,
        query: str,
        focus_areas: List[str] = None,
        constraints: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Run the complete ideation workflow."""
        if not self.llm:
            raise ValueError("OpenAI API key not configured")
        
        # Initialize state
        initial_state = IdeationState(
            workspace_id=workspace_id,
            query=query,
            focus_areas=focus_areas or [],
            constraints=constraints or {},
            market_signals=[],
            competitor_analysis={},
            trend_analysis={},
            whitespace_analysis={},
            raw_ideas=[],
            validated_ideas=[],
            business_models=[],
            tech_assessments=[],
            current_step="research_agent",
            confidence_scores={},
            retry_count=0,
            max_retries=3,
            messages=[HumanMessage(content=query)],
            final_ideas=[],
            export_ready=False
        )
        
        try:
            # Run the workflow
            final_state = await self.workflow.ainvoke(initial_state)
            
            return {
                "status": "completed" if final_state["export_ready"] else "failed",
                "workspace_id": workspace_id,
                "final_ideas": final_state["final_ideas"],
                "confidence_scores": final_state["confidence_scores"],
                "workflow_steps": self._extract_workflow_steps(final_state),
                "metadata": {
                    "total_signals": len(final_state["market_signals"]),
                    "ideas_generated": len(final_state["raw_ideas"]),
                    "ideas_validated": len(final_state["validated_ideas"]),
                    "completed_at": datetime.utcnow().isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            return {
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(e),
                "final_ideas": []
            }
    
    async def _research_node(self, state: IdeationState) -> IdeationState:
        """Research agent node - gather market signals and trends."""
        logger.info("Executing research agent")
        
        try:
            # Create research agent
            research_agent = Agent(
                role="Market Research Analyst",
                goal="Gather comprehensive market intelligence and identify trends",
                backstory="""You are an expert market research analyst with deep knowledge of 
                technology trends, consumer behavior, and market dynamics. You excel at 
                synthesizing data from multiple sources to identify emerging opportunities.""",
                llm=self.llm,
                verbose=True
            )
            
            # Define research task
            research_task = Task(
                description=f"""
                Analyze the market landscape for: {state['query']}
                Focus areas: {', '.join(state['focus_areas']) if state['focus_areas'] else 'General market'}
                
                Based on available market signals, provide:
                1. Key market trends and patterns
                2. Emerging opportunities and gaps
                3. Target audience insights
                4. Market size indicators
                5. Competitive landscape overview
                
                Constraints: {json.dumps(state['constraints'])}
                """,
                agent=research_agent,
                expected_output="Comprehensive market analysis with actionable insights"
            )
            
            # Execute research
            crew = Crew(agents=[research_agent], tasks=[research_task], verbose=True)
            result = crew.kickoff()
            
            # Parse and store results
            research_insights = self._parse_research_results(result)
            
            # Update state
            state["market_signals"] = research_insights.get("signals", [])
            state["trend_analysis"] = research_insights.get("trends", {})
            state["confidence_scores"]["market_research"] = research_insights.get("confidence", 0.8)
            state["current_step"] = "competitor_agent"
            state["messages"].append(AIMessage(content=f"Research completed: {result[:200]}..."))
            
            logger.info("Research agent completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Research agent failed: {e}")
            state["retry_count"] += 1
            state["confidence_scores"]["market_research"] = 0.0
            return state
    
    async def _competitor_node(self, state: IdeationState) -> IdeationState:
        """Competitor analysis agent node."""
        logger.info("Executing competitor agent")
        
        try:
            # Create competitor agent
            competitor_agent = Agent(
                role="Competitive Intelligence Analyst",
                goal="Analyze competitive landscape and identify differentiation opportunities",
                backstory="""You are a competitive intelligence expert who specializes in 
                analyzing market positioning, pricing strategies, and feature gaps. You 
                provide actionable insights for competitive differentiation.""",
                llm=self.llm,
                verbose=True
            )
            
            # Define competitor task
            competitor_task = Task(
                description=f"""
                Analyze the competitive landscape for: {state['query']}
                
                Based on market research findings, identify:
                1. Key competitors and their positioning
                2. Pricing strategies and models
                3. Feature gaps and opportunities
                4. Market positioning opportunities
                5. Differentiation strategies
                
                Market context: {json.dumps(state['trend_analysis'])}
                """,
                agent=competitor_agent,
                expected_output="Competitive analysis with differentiation opportunities"
            )
            
            # Execute analysis
            crew = Crew(agents=[competitor_agent], tasks=[competitor_task], verbose=True)
            result = crew.kickoff()
            
            # Parse and store results
            competitor_insights = self._parse_competitor_results(result)
            
            # Update state
            state["competitor_analysis"] = competitor_insights
            state["confidence_scores"]["competitor_analysis"] = competitor_insights.get("confidence", 0.7)
            state["current_step"] = "ideation_agent"
            state["messages"].append(AIMessage(content=f"Competitor analysis completed: {result[:200]}..."))
            
            logger.info("Competitor agent completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Competitor agent failed: {e}")
            state["retry_count"] += 1
            state["confidence_scores"]["competitor_analysis"] = 0.0
            return state
    
    async def _ideation_node(self, state: IdeationState) -> IdeationState:
        """Ideation agent node - generate product concepts."""
        logger.info("Executing ideation agent")
        
        try:
            # Create ideation agent
            ideation_agent = Agent(
                role="Product Ideation Specialist",
                goal="Generate innovative and viable product concepts",
                backstory="""You are a creative product strategist with a track record of 
                identifying successful product opportunities. You combine market insights 
                with creative thinking to generate compelling product concepts.""",
                llm=self.llm,
                verbose=True
            )
            
            # Define ideation task
            ideation_task = Task(
                description=f"""
                Generate 3-5 innovative product ideas based on:
                
                Query: {state['query']}
                Market insights: {json.dumps(state['trend_analysis'])}
                Competitive gaps: {json.dumps(state['competitor_analysis'])}
                
                For each idea, provide:
                1. Product name and tagline
                2. Problem it solves
                3. Target customer profile
                4. Unique value proposition
                5. Key features (MVP)
                6. Market positioning
                7. Competitive differentiation
                
                Constraints: {json.dumps(state['constraints'])}
                """,
                agent=ideation_agent,
                expected_output="3-5 detailed product concepts with clear value propositions"
            )
            
            # Execute ideation
            crew = Crew(agents=[ideation_agent], tasks=[ideation_task], verbose=True)
            result = crew.kickoff()
            
            # Parse and store results
            ideas = self._parse_ideation_results(result)
            
            # Update state
            state["raw_ideas"] = ideas
            state["confidence_scores"]["idea_generation"] = self._calculate_idea_confidence(ideas)
            state["current_step"] = "business_agent"
            state["messages"].append(AIMessage(content=f"Generated {len(ideas)} product ideas"))
            
            logger.info(f"Ideation agent completed: {len(ideas)} ideas generated")
            return state
            
        except Exception as e:
            logger.error(f"Ideation agent failed: {e}")
            state["retry_count"] += 1
            state["confidence_scores"]["idea_generation"] = 0.0
            return state
    
    async def _business_node(self, state: IdeationState) -> IdeationState:
        """Business validation agent node."""
        logger.info("Executing business agent")
        
        try:
            # Create business agent
            business_agent = Agent(
                role="Business Model Analyst",
                goal="Validate business viability and develop monetization strategies",
                backstory="""You are a business analyst who specializes in evaluating 
                product concepts for market fit, revenue potential, and business model 
                viability. You provide realistic assessments and actionable recommendations.""",
                llm=self.llm,
                verbose=True
            )
            
            # Define business task
            business_task = Task(
                description=f"""
                Analyze business viability for the generated product ideas:
                
                Ideas: {json.dumps(state['raw_ideas'])}
                Market context: {json.dumps(state['trend_analysis'])}
                
                For each idea, evaluate:
                1. Market size and opportunity (TAM/SAM/SOM)
                2. Revenue model and pricing strategy
                3. Unit economics and scalability
                4. Go-to-market strategy
                5. Key success metrics
                6. Business risks and mitigation
                7. Funding requirements
                """,
                agent=business_agent,
                expected_output="Business validation analysis for each product idea"
            )
            
            # Execute business analysis
            crew = Crew(agents=[business_agent], tasks=[business_task], verbose=True)
            result = crew.kickoff()
            
            # Parse and store results
            business_models = self._parse_business_results(result)
            
            # Update state
            state["business_models"] = business_models
            state["confidence_scores"]["business_validation"] = self._calculate_business_confidence(business_models)
            state["current_step"] = "tech_agent"
            state["messages"].append(AIMessage(content="Business validation completed"))
            
            logger.info("Business agent completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Business agent failed: {e}")
            state["retry_count"] += 1
            state["confidence_scores"]["business_validation"] = 0.0
            return state
    
    async def _tech_node(self, state: IdeationState) -> IdeationState:
        """Technical feasibility agent node."""
        logger.info("Executing tech agent")
        
        try:
            # Create tech agent
            tech_agent = Agent(
                role="Technical Feasibility Analyst",
                goal="Assess technical feasibility and recommend implementation approaches",
                backstory="""You are a technical architect with extensive experience in 
                evaluating technology solutions, assessing implementation complexity, and 
                recommending optimal technical approaches for product development.""",
                llm=self.llm,
                verbose=True
            )
            
            # Define tech task
            tech_task = Task(
                description=f"""
                Assess technical feasibility for the product ideas:
                
                Ideas: {json.dumps(state['raw_ideas'])}
                Business requirements: {json.dumps(state['business_models'])}
                
                For each idea, evaluate:
                1. Technical complexity and feasibility
                2. Recommended technology stack
                3. Architecture considerations
                4. Development timeline estimates
                5. Build vs buy recommendations
                6. Scalability considerations
                7. Security and compliance requirements
                8. Technical risks and mitigation
                """,
                agent=tech_agent,
                expected_output="Technical feasibility assessment for each product idea"
            )
            
            # Execute tech analysis
            crew = Crew(agents=[tech_agent], tasks=[tech_task], verbose=True)
            result = crew.kickoff()
            
            # Parse and store results
            tech_assessments = self._parse_tech_results(result)
            
            # Update state
            state["tech_assessments"] = tech_assessments
            state["confidence_scores"]["tech_feasibility"] = self._calculate_tech_confidence(tech_assessments)
            state["current_step"] = "validation_agent"
            state["messages"].append(AIMessage(content="Technical assessment completed"))
            
            logger.info("Tech agent completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Tech agent failed: {e}")
            state["retry_count"] += 1
            state["confidence_scores"]["tech_feasibility"] = 0.0
            return state
    
    async def _validation_node(self, state: IdeationState) -> IdeationState:
        """Final validation agent node."""
        logger.info("Executing validation agent")
        
        try:
            # Combine all analyses to create validated ideas
            validated_ideas = []
            
            for i, idea in enumerate(state["raw_ideas"]):
                business_model = state["business_models"][i] if i < len(state["business_models"]) else {}
                tech_assessment = state["tech_assessments"][i] if i < len(state["tech_assessments"]) else {}
                
                # Calculate overall attractiveness score
                attractiveness_score = self._calculate_attractiveness_score(
                    idea, business_model, tech_assessment, state["competitor_analysis"]
                )
                
                # Calculate confidence score
                confidence_score = self._calculate_overall_confidence(state["confidence_scores"])
                
                validated_idea = {
                    **idea,
                    "business_model": business_model,
                    "tech_assessment": tech_assessment,
                    "attractiveness_score": attractiveness_score,
                    "confidence_score": confidence_score,
                    "validation_status": "validated" if confidence_score > 0.7 else "needs_review",
                    "sources": [s.get("id") for s in state["market_signals"][:10]],
                    "citations": {
                        "market_research": f"Based on {len(state['market_signals'])} market signals",
                        "competitor_analysis": "AI-powered competitive intelligence",
                        "business_validation": "Multi-agent business model analysis",
                        "tech_feasibility": "Technical architecture assessment"
                    }
                }
                
                validated_ideas.append(validated_idea)
            
            # Update state
            state["validated_ideas"] = validated_ideas
            state["final_ideas"] = validated_ideas
            state["current_step"] = "export_agent"
            state["messages"].append(AIMessage(content=f"Validated {len(validated_ideas)} ideas"))
            
            logger.info(f"Validation agent completed: {len(validated_ideas)} ideas validated")
            return state
            
        except Exception as e:
            logger.error(f"Validation agent failed: {e}")
            state["retry_count"] += 1
            return state
    
    async def _export_node(self, state: IdeationState) -> IdeationState:
        """Export agent node - prepare final deliverables."""
        logger.info("Executing export agent")
        
        try:
            # Mark as export ready
            state["export_ready"] = True
            state["current_step"] = "completed"
            state["messages"].append(AIMessage(content="Export preparation completed"))
            
            logger.info("Export agent completed successfully")
            return state
            
        except Exception as e:
            logger.error(f"Export agent failed: {e}")
            state["export_ready"] = False
            return state
    
    # Conditional edge functions
    def _should_continue_research(self, state: IdeationState) -> str:
        """Determine if research should continue, retry, or fail."""
        confidence = state["confidence_scores"].get("market_research", 0.0)
        
        if confidence >= self.confidence_thresholds["market_research"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "fail"
    
    def _should_continue_competitor(self, state: IdeationState) -> str:
        """Determine if competitor analysis should continue, retry, or skip."""
        confidence = state["confidence_scores"].get("competitor_analysis", 0.0)
        
        if confidence >= self.confidence_thresholds["competitor_analysis"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "skip"  # Competitor analysis is optional
    
    def _should_continue_ideation(self, state: IdeationState) -> str:
        """Determine if ideation should continue, retry, or fail."""
        confidence = state["confidence_scores"].get("idea_generation", 0.0)
        
        if confidence >= self.confidence_thresholds["idea_generation"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "fail"
    
    def _should_continue_business(self, state: IdeationState) -> str:
        """Determine if business analysis should continue, retry, or skip."""
        confidence = state["confidence_scores"].get("business_validation", 0.0)
        
        if confidence >= self.confidence_thresholds["business_validation"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "skip"
    
    def _should_continue_tech(self, state: IdeationState) -> str:
        """Determine if tech analysis should continue, retry, or skip."""
        confidence = state["confidence_scores"].get("tech_feasibility", 0.0)
        
        if confidence >= self.confidence_thresholds["tech_feasibility"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "skip"
    
    def _should_continue_validation(self, state: IdeationState) -> str:
        """Determine if validation should continue, retry, or fail."""
        # Validation always continues if we have ideas
        if state["raw_ideas"]:
            return "continue"
        elif state["retry_count"] < state["max_retries"]:
            return "retry"
        else:
            return "fail"
    
    # Helper methods for parsing results
    def _parse_research_results(self, result: str) -> Dict[str, Any]:
        """Parse research agent results."""
        # Simplified parsing - in production, use more sophisticated NLP
        return {
            "signals": [{"content": result[:500], "confidence": 0.8}],
            "trends": {"summary": result[:200]},
            "confidence": 0.8
        }
    
    def _parse_competitor_results(self, result: str) -> Dict[str, Any]:
        """Parse competitor analysis results."""
        return {
            "summary": result[:300],
            "gaps": ["gap1", "gap2"],
            "confidence": 0.7
        }
    
    def _parse_ideation_results(self, result: str) -> List[Dict[str, Any]]:
        """Parse ideation results into structured ideas."""
        # Simplified parsing - create one comprehensive idea
        return [{
            "title": "AI-Generated Product Concept",
            "description": result[:500],
            "uvp": "Addresses identified market opportunities",
            "target_customers": "Early adopters and mainstream users",
            "key_features": ["Core functionality", "User interface", "Integrations"],
            "positioning": "Innovative solution in emerging market"
        }]
    
    def _parse_business_results(self, result: str) -> List[Dict[str, Any]]:
        """Parse business analysis results."""
        return [{
            "revenue_model": "subscription",
            "market_size": "large",
            "viability_score": 0.8,
            "summary": result[:300]
        }]
    
    def _parse_tech_results(self, result: str) -> List[Dict[str, Any]]:
        """Parse technical assessment results."""
        return [{
            "complexity": "medium",
            "tech_stack": ["Python", "React", "PostgreSQL"],
            "feasibility_score": 0.8,
            "summary": result[:300]
        }]
    
    # Helper methods for confidence calculation
    def _calculate_idea_confidence(self, ideas: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for generated ideas."""
        if not ideas:
            return 0.0
        
        # Simple heuristic based on idea completeness
        total_score = 0
        for idea in ideas:
            score = 0
            if idea.get("title"): score += 0.2
            if idea.get("description"): score += 0.2
            if idea.get("uvp"): score += 0.2
            if idea.get("target_customers"): score += 0.2
            if idea.get("key_features"): score += 0.2
            total_score += score
        
        return total_score / len(ideas)
    
    def _calculate_business_confidence(self, business_models: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for business models."""
        if not business_models:
            return 0.0
        
        return sum(bm.get("viability_score", 0.5) for bm in business_models) / len(business_models)
    
    def _calculate_tech_confidence(self, tech_assessments: List[Dict[str, Any]]) -> float:
        """Calculate confidence score for tech assessments."""
        if not tech_assessments:
            return 0.0
        
        return sum(ta.get("feasibility_score", 0.5) for ta in tech_assessments) / len(tech_assessments)
    
    def _calculate_attractiveness_score(
        self,
        idea: Dict[str, Any],
        business_model: Dict[str, Any],
        tech_assessment: Dict[str, Any],
        competitor_analysis: Dict[str, Any]
    ) -> float:
        """Calculate overall attractiveness score."""
        # Weighted combination of factors
        market_score = 0.8  # Based on market research
        business_score = business_model.get("viability_score", 0.5)
        tech_score = tech_assessment.get("feasibility_score", 0.5)
        competition_score = 0.7  # Based on competitive gaps
        
        return (
            market_score * 0.3 +
            business_score * 0.3 +
            tech_score * 0.2 +
            competition_score * 0.2
        )
    
    def _calculate_overall_confidence(self, confidence_scores: Dict[str, float]) -> float:
        """Calculate overall confidence score."""
        if not confidence_scores:
            return 0.0
        
        weights = {
            "market_research": 0.25,
            "competitor_analysis": 0.15,
            "idea_generation": 0.30,
            "business_validation": 0.20,
            "tech_feasibility": 0.10
        }
        
        total_score = 0
        total_weight = 0
        
        for key, weight in weights.items():
            if key in confidence_scores:
                total_score += confidence_scores[key] * weight
                total_weight += weight
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def _extract_workflow_steps(self, state: IdeationState) -> List[Dict[str, Any]]:
        """Extract workflow execution steps for debugging."""
        steps = []
        for message in state["messages"]:
            if isinstance(message, AIMessage):
                steps.append({
                    "type": "agent_response",
                    "content": message.content[:100],
                    "timestamp": datetime.utcnow().isoformat()
                })
        
        return steps


# Global orchestrator instance
langgraph_orchestrator = LangGraphOrchestrator()
