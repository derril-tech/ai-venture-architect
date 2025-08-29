"""Business modeling service for TAM/SAM/SOM, unit economics, and pricing analysis."""

import math
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

import structlog
import numpy as np

logger = structlog.get_logger()


@dataclass
class MarketSizeResult:
    """Market size calculation result."""
    tam: float  # Total Addressable Market
    sam: float  # Serviceable Addressable Market
    som: float  # Serviceable Obtainable Market
    methodology: str
    assumptions: Dict[str, Any]
    confidence: float
    sources: List[str]


@dataclass
class UnitEconomicsResult:
    """Unit economics calculation result."""
    cac: float  # Customer Acquisition Cost
    ltv: float  # Lifetime Value
    ltv_cac_ratio: float
    payback_period_months: float
    gross_margin: float
    contribution_margin: float
    assumptions: Dict[str, Any]
    sensitivity_analysis: Dict[str, Any]


@dataclass
class PricingRecommendation:
    """Pricing strategy recommendation."""
    model: str  # subscription, one_time, usage_based, freemium
    tiers: List[Dict[str, Any]]
    rationale: str
    competitive_positioning: str
    price_elasticity: Optional[float]
    revenue_projections: Dict[str, float]


class BusinessModelingService:
    """Service for business model analysis and validation."""
    
    def __init__(self):
        # Industry benchmarks (simplified - in production, use real data)
        self.industry_benchmarks = {
            "software": {
                "gross_margin": 0.80,
                "cac_ltv_ratio": 3.0,
                "payback_months": 12,
                "churn_rate_monthly": 0.05,
                "pricing_multiple": 10  # Annual revenue multiple for valuation
            },
            "ai_ml": {
                "gross_margin": 0.75,
                "cac_ltv_ratio": 4.0,
                "payback_months": 18,
                "churn_rate_monthly": 0.03,
                "pricing_multiple": 15
            },
            "fintech": {
                "gross_margin": 0.70,
                "cac_ltv_ratio": 3.5,
                "payback_months": 15,
                "churn_rate_monthly": 0.04,
                "pricing_multiple": 12
            },
            "healthcare": {
                "gross_margin": 0.65,
                "cac_ltv_ratio": 5.0,
                "payback_months": 24,
                "churn_rate_monthly": 0.02,
                "pricing_multiple": 8
            },
            "ecommerce": {
                "gross_margin": 0.40,
                "cac_ltv_ratio": 2.5,
                "payback_months": 8,
                "churn_rate_monthly": 0.08,
                "pricing_multiple": 6
            }
        }
        
        # Market size data sources
        self.market_data_sources = {
            "software": {"global_market_2024": 650000, "growth_rate": 0.11},
            "ai_ml": {"global_market_2024": 150000, "growth_rate": 0.35},
            "fintech": {"global_market_2024": 310000, "growth_rate": 0.25},
            "healthcare": {"global_market_2024": 350000, "growth_rate": 0.15},
            "ecommerce": {"global_market_2024": 5800000, "growth_rate": 0.14}
        }
    
    async def calculate_market_size(
        self,
        industry: str,
        target_segments: List[str],
        geographic_scope: str = "global",
        methodology: str = "top_down"
    ) -> MarketSizeResult:
        """Calculate TAM/SAM/SOM using specified methodology."""
        
        if methodology == "top_down":
            return await self._calculate_top_down_market_size(
                industry, target_segments, geographic_scope
            )
        elif methodology == "bottom_up":
            return await self._calculate_bottom_up_market_size(
                industry, target_segments, geographic_scope
            )
        else:
            # Hybrid approach - average of both methods
            top_down = await self._calculate_top_down_market_size(
                industry, target_segments, geographic_scope
            )
            bottom_up = await self._calculate_bottom_up_market_size(
                industry, target_segments, geographic_scope
            )
            
            return MarketSizeResult(
                tam=(top_down.tam + bottom_up.tam) / 2,
                sam=(top_down.sam + bottom_up.sam) / 2,
                som=(top_down.som + bottom_up.som) / 2,
                methodology="hybrid",
                assumptions={
                    "top_down": top_down.assumptions,
                    "bottom_up": bottom_up.assumptions
                },
                confidence=(top_down.confidence + bottom_up.confidence) / 2,
                sources=list(set(top_down.sources + bottom_up.sources))
            )
    
    async def _calculate_top_down_market_size(
        self,
        industry: str,
        target_segments: List[str],
        geographic_scope: str
    ) -> MarketSizeResult:
        """Calculate market size using top-down approach."""
        
        # Get industry market data
        market_data = self.market_data_sources.get(industry, {})
        global_market = market_data.get("global_market_2024", 100000)  # Default $100B
        growth_rate = market_data.get("growth_rate", 0.10)
        
        # Geographic adjustment
        geo_multiplier = self._get_geographic_multiplier(geographic_scope)
        
        # TAM calculation
        tam = global_market * geo_multiplier
        
        # SAM calculation (addressable with our solution)
        sam_percentage = self._estimate_sam_percentage(industry, target_segments)
        sam = tam * sam_percentage
        
        # SOM calculation (realistically obtainable)
        som_percentage = self._estimate_som_percentage(industry)
        som = sam * som_percentage
        
        assumptions = {
            "global_market_size_millions": global_market,
            "growth_rate": growth_rate,
            "geographic_multiplier": geo_multiplier,
            "sam_percentage": sam_percentage,
            "som_percentage": som_percentage,
            "target_segments": target_segments
        }
        
        confidence = self._calculate_market_size_confidence(
            industry, len(target_segments), geographic_scope
        )
        
        return MarketSizeResult(
            tam=tam,
            sam=sam,
            som=som,
            methodology="top_down",
            assumptions=assumptions,
            confidence=confidence,
            sources=[f"{industry}_market_research", "industry_reports"]
        )
    
    async def _calculate_bottom_up_market_size(
        self,
        industry: str,
        target_segments: List[str],
        geographic_scope: str
    ) -> MarketSizeResult:
        """Calculate market size using bottom-up approach."""
        
        # Estimate target customer counts
        customer_estimates = self._estimate_target_customers(
            industry, target_segments, geographic_scope
        )
        
        # Estimate average revenue per customer
        arpu = self._estimate_arpu(industry, target_segments)
        
        # Calculate market sizes
        total_customers = sum(customer_estimates.values())
        
        # TAM: All potential customers × ARPU
        tam = total_customers * arpu
        
        # SAM: Customers we can realistically reach
        sam_reach_rate = 0.3  # Assume we can reach 30% of total market
        sam = tam * sam_reach_rate
        
        # SOM: Market share we can capture
        market_share = 0.05  # Assume 5% market share is achievable
        som = sam * market_share
        
        assumptions = {
            "customer_segments": customer_estimates,
            "total_target_customers": total_customers,
            "average_revenue_per_user": arpu,
            "sam_reach_rate": sam_reach_rate,
            "achievable_market_share": market_share
        }
        
        confidence = self._calculate_market_size_confidence(
            industry, len(target_segments), geographic_scope
        )
        
        return MarketSizeResult(
            tam=tam,
            sam=sam,
            som=som,
            methodology="bottom_up",
            assumptions=assumptions,
            confidence=confidence,
            sources=["customer_research", "pricing_analysis"]
        )
    
    async def calculate_unit_economics(
        self,
        industry: str,
        pricing_model: str,
        customer_segments: List[str],
        assumptions: Optional[Dict[str, Any]] = None
    ) -> UnitEconomicsResult:
        """Calculate unit economics including CAC, LTV, and key ratios."""
        
        # Get industry benchmarks
        benchmarks = self.industry_benchmarks.get(industry, self.industry_benchmarks["software"])
        
        # Use provided assumptions or defaults
        model_assumptions = assumptions or {}
        
        # Calculate Customer Acquisition Cost (CAC)
        cac = self._calculate_cac(industry, pricing_model, model_assumptions)
        
        # Calculate Lifetime Value (LTV)
        ltv = self._calculate_ltv(industry, pricing_model, model_assumptions, benchmarks)
        
        # Calculate key ratios
        ltv_cac_ratio = ltv / cac if cac > 0 else 0
        
        # Calculate payback period
        monthly_revenue = model_assumptions.get("monthly_revenue_per_customer", ltv / 24)
        gross_margin = model_assumptions.get("gross_margin", benchmarks["gross_margin"])
        monthly_contribution = monthly_revenue * gross_margin
        payback_period_months = cac / monthly_contribution if monthly_contribution > 0 else float('inf')
        
        # Calculate margins
        contribution_margin = gross_margin  # Simplified
        
        # Sensitivity analysis
        sensitivity = self._perform_sensitivity_analysis(
            cac, ltv, monthly_revenue, gross_margin
        )
        
        final_assumptions = {
            "industry": industry,
            "pricing_model": pricing_model,
            "customer_segments": customer_segments,
            "monthly_revenue_per_customer": monthly_revenue,
            "gross_margin": gross_margin,
            "churn_rate_monthly": model_assumptions.get("churn_rate_monthly", benchmarks["churn_rate_monthly"]),
            **model_assumptions
        }
        
        return UnitEconomicsResult(
            cac=cac,
            ltv=ltv,
            ltv_cac_ratio=ltv_cac_ratio,
            payback_period_months=payback_period_months,
            gross_margin=gross_margin,
            contribution_margin=contribution_margin,
            assumptions=final_assumptions,
            sensitivity_analysis=sensitivity
        )
    
    async def recommend_pricing_strategy(
        self,
        industry: str,
        target_segments: List[str],
        competitor_pricing: Optional[Dict[str, Any]] = None,
        value_proposition: Optional[str] = None
    ) -> PricingRecommendation:
        """Recommend pricing strategy based on market analysis."""
        
        # Analyze optimal pricing model
        pricing_model = self._determine_optimal_pricing_model(
            industry, target_segments, competitor_pricing
        )
        
        # Generate pricing tiers
        tiers = self._generate_pricing_tiers(
            industry, pricing_model, competitor_pricing
        )
        
        # Calculate revenue projections
        revenue_projections = self._project_revenue(tiers, target_segments)
        
        # Generate rationale
        rationale = self._generate_pricing_rationale(
            pricing_model, industry, competitor_pricing
        )
        
        # Competitive positioning
        positioning = self._analyze_competitive_positioning(
            tiers, competitor_pricing
        )
        
        return PricingRecommendation(
            model=pricing_model,
            tiers=tiers,
            rationale=rationale,
            competitive_positioning=positioning,
            price_elasticity=self._estimate_price_elasticity(industry),
            revenue_projections=revenue_projections
        )
    
    def _get_geographic_multiplier(self, scope: str) -> float:
        """Get geographic market multiplier."""
        multipliers = {
            "global": 1.0,
            "north_america": 0.35,
            "europe": 0.25,
            "asia_pacific": 0.30,
            "us_only": 0.25,
            "emerging_markets": 0.15
        }
        return multipliers.get(scope, 1.0)
    
    def _estimate_sam_percentage(self, industry: str, segments: List[str]) -> float:
        """Estimate what percentage of TAM is serviceable."""
        base_percentage = {
            "software": 0.15,
            "ai_ml": 0.08,
            "fintech": 0.12,
            "healthcare": 0.06,
            "ecommerce": 0.20
        }.get(industry, 0.10)
        
        # Adjust based on number of target segments
        segment_multiplier = min(1.0, len(segments) * 0.3)
        return base_percentage * (1 + segment_multiplier)
    
    def _estimate_som_percentage(self, industry: str) -> float:
        """Estimate what percentage of SAM is obtainable."""
        return {
            "software": 0.05,
            "ai_ml": 0.03,
            "fintech": 0.04,
            "healthcare": 0.02,
            "ecommerce": 0.08
        }.get(industry, 0.05)
    
    def _estimate_target_customers(
        self, 
        industry: str, 
        segments: List[str], 
        geographic_scope: str
    ) -> Dict[str, int]:
        """Estimate number of target customers by segment."""
        
        # Base customer counts (simplified estimates)
        base_counts = {
            "enterprise": 50000,
            "smb": 500000,
            "startups": 100000,
            "consumers": 10000000,
            "developers": 25000000,
            "agencies": 75000
        }
        
        geo_multiplier = self._get_geographic_multiplier(geographic_scope)
        
        estimates = {}
        for segment in segments:
            base_count = base_counts.get(segment, 100000)
            estimates[segment] = int(base_count * geo_multiplier)
        
        return estimates
    
    def _estimate_arpu(self, industry: str, segments: List[str]) -> float:
        """Estimate average revenue per user."""
        
        # Base ARPU by industry (annual)
        base_arpu = {
            "software": 2400,
            "ai_ml": 12000,
            "fintech": 1800,
            "healthcare": 8000,
            "ecommerce": 600
        }.get(industry, 2400)
        
        # Adjust based on target segments
        segment_multipliers = {
            "enterprise": 3.0,
            "smb": 1.0,
            "startups": 0.3,
            "consumers": 0.1,
            "developers": 0.5,
            "agencies": 1.5
        }
        
        if segments:
            avg_multiplier = sum(segment_multipliers.get(s, 1.0) for s in segments) / len(segments)
            return base_arpu * avg_multiplier
        
        return base_arpu
    
    def _calculate_cac(
        self, 
        industry: str, 
        pricing_model: str, 
        assumptions: Dict[str, Any]
    ) -> float:
        """Calculate Customer Acquisition Cost."""
        
        # Base CAC by industry
        base_cac = {
            "software": 1200,
            "ai_ml": 3000,
            "fintech": 2000,
            "healthcare": 4000,
            "ecommerce": 300
        }.get(industry, 1200)
        
        # Adjust based on pricing model
        pricing_multipliers = {
            "freemium": 0.5,
            "subscription": 1.0,
            "one_time": 1.5,
            "usage_based": 0.8,
            "enterprise": 2.0
        }
        
        multiplier = pricing_multipliers.get(pricing_model, 1.0)
        
        # Apply custom assumptions
        if "cac_multiplier" in assumptions:
            multiplier *= assumptions["cac_multiplier"]
        
        return base_cac * multiplier
    
    def _calculate_ltv(
        self, 
        industry: str, 
        pricing_model: str, 
        assumptions: Dict[str, Any],
        benchmarks: Dict[str, Any]
    ) -> float:
        """Calculate Lifetime Value."""
        
        # Get monthly revenue
        monthly_revenue = assumptions.get("monthly_revenue_per_customer", 200)
        
        # Get churn rate
        churn_rate = assumptions.get("churn_rate_monthly", benchmarks["churn_rate_monthly"])
        
        # Get gross margin
        gross_margin = assumptions.get("gross_margin", benchmarks["gross_margin"])
        
        # Calculate average customer lifetime (months)
        if churn_rate > 0:
            lifetime_months = 1 / churn_rate
        else:
            lifetime_months = 24  # Default 2 years
        
        # LTV = Monthly Revenue × Gross Margin × Lifetime
        ltv = monthly_revenue * gross_margin * lifetime_months
        
        return ltv
    
    def _perform_sensitivity_analysis(
        self, 
        cac: float, 
        ltv: float, 
        monthly_revenue: float, 
        gross_margin: float
    ) -> Dict[str, Any]:
        """Perform sensitivity analysis on key metrics."""
        
        scenarios = {}
        
        # Revenue sensitivity
        for change in [-0.2, -0.1, 0.1, 0.2]:
            scenario_name = f"revenue_{'+' if change > 0 else ''}{int(change*100)}%"
            new_revenue = monthly_revenue * (1 + change)
            new_ltv = ltv * (1 + change)
            scenarios[scenario_name] = {
                "ltv_cac_ratio": new_ltv / cac,
                "ltv": new_ltv,
                "monthly_revenue": new_revenue
            }
        
        # Churn sensitivity
        base_churn = 0.05  # 5% monthly
        for churn_change in [-0.02, -0.01, 0.01, 0.02]:
            new_churn = base_churn + churn_change
            if new_churn > 0:
                scenario_name = f"churn_{'+' if churn_change > 0 else ''}{int(churn_change*100)}%"
                new_lifetime = 1 / new_churn
                new_ltv = monthly_revenue * gross_margin * new_lifetime
                scenarios[scenario_name] = {
                    "ltv_cac_ratio": new_ltv / cac,
                    "ltv": new_ltv,
                    "churn_rate": new_churn
                }
        
        return scenarios
    
    def _determine_optimal_pricing_model(
        self, 
        industry: str, 
        segments: List[str], 
        competitor_pricing: Optional[Dict[str, Any]]
    ) -> str:
        """Determine optimal pricing model."""
        
        # Industry preferences
        industry_models = {
            "software": "subscription",
            "ai_ml": "usage_based",
            "fintech": "subscription",
            "healthcare": "subscription",
            "ecommerce": "freemium"
        }
        
        base_model = industry_models.get(industry, "subscription")
        
        # Adjust based on target segments
        if "enterprise" in segments:
            return "enterprise"
        elif "consumers" in segments:
            return "freemium"
        elif "developers" in segments:
            return "usage_based"
        
        return base_model
    
    def _generate_pricing_tiers(
        self, 
        industry: str, 
        pricing_model: str, 
        competitor_pricing: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate pricing tier recommendations."""
        
        # Base pricing by industry
        base_prices = {
            "software": {"starter": 29, "pro": 99, "enterprise": 299},
            "ai_ml": {"starter": 99, "pro": 299, "enterprise": 999},
            "fintech": {"starter": 49, "pro": 149, "enterprise": 499},
            "healthcare": {"starter": 199, "pro": 499, "enterprise": 1499},
            "ecommerce": {"starter": 19, "pro": 79, "enterprise": 199}
        }
        
        prices = base_prices.get(industry, base_prices["software"])
        
        tiers = []
        
        if pricing_model == "freemium":
            tiers.append({
                "name": "Free",
                "price": 0,
                "billing": "monthly",
                "features": ["Basic features", "Limited usage", "Community support"],
                "target": "Individual users, trial"
            })
        
        tiers.extend([
            {
                "name": "Starter",
                "price": prices["starter"],
                "billing": "monthly",
                "features": ["Core features", "Standard support", "Basic integrations"],
                "target": "Small teams, startups"
            },
            {
                "name": "Professional",
                "price": prices["pro"],
                "billing": "monthly",
                "features": ["Advanced features", "Priority support", "Full integrations", "Analytics"],
                "target": "Growing businesses"
            },
            {
                "name": "Enterprise",
                "price": prices["enterprise"],
                "billing": "monthly",
                "features": ["All features", "24/7 support", "Custom integrations", "SLA", "SSO"],
                "target": "Large organizations"
            }
        ])
        
        return tiers
    
    def _project_revenue(
        self, 
        tiers: List[Dict[str, Any]], 
        segments: List[str]
    ) -> Dict[str, float]:
        """Project revenue based on pricing tiers."""
        
        # Simple revenue projection
        projections = {}
        
        # Estimate customer distribution across tiers
        tier_distribution = {
            "Free": 0.6,
            "Starter": 0.25,
            "Professional": 0.12,
            "Enterprise": 0.03
        }
        
        total_customers = 1000  # Assume 1000 customers in first year
        
        for tier in tiers:
            tier_name = tier["name"]
            customers = total_customers * tier_distribution.get(tier_name, 0.1)
            monthly_revenue = customers * tier["price"]
            annual_revenue = monthly_revenue * 12
            
            projections[f"{tier_name.lower()}_monthly"] = monthly_revenue
            projections[f"{tier_name.lower()}_annual"] = annual_revenue
        
        projections["total_monthly"] = sum(
            v for k, v in projections.items() if k.endswith("_monthly")
        )
        projections["total_annual"] = projections["total_monthly"] * 12
        
        return projections
    
    def _generate_pricing_rationale(
        self, 
        pricing_model: str, 
        industry: str, 
        competitor_pricing: Optional[Dict[str, Any]]
    ) -> str:
        """Generate rationale for pricing strategy."""
        
        rationales = {
            "subscription": f"Subscription model aligns with {industry} industry standards and provides predictable recurring revenue.",
            "freemium": f"Freemium model reduces barriers to adoption and allows for viral growth in {industry}.",
            "usage_based": f"Usage-based pricing scales with customer value and is well-suited for {industry} solutions.",
            "enterprise": f"Enterprise pricing reflects the high value and customization required for {industry} solutions."
        }
        
        base_rationale = rationales.get(pricing_model, "Pricing model optimized for target market.")
        
        if competitor_pricing:
            base_rationale += " Pricing positioned competitively against market alternatives."
        
        return base_rationale
    
    def _analyze_competitive_positioning(
        self, 
        tiers: List[Dict[str, Any]], 
        competitor_pricing: Optional[Dict[str, Any]]
    ) -> str:
        """Analyze competitive positioning."""
        
        if not competitor_pricing:
            return "Pricing positioned based on value delivery and market standards."
        
        # Simple competitive analysis
        our_mid_tier = next((t for t in tiers if t["name"] == "Professional"), tiers[1])
        our_price = our_mid_tier["price"]
        
        # Compare with competitor average (simplified)
        competitor_prices = [p for p in competitor_pricing.values() if isinstance(p, (int, float))]
        if competitor_prices:
            avg_competitor_price = sum(competitor_prices) / len(competitor_prices)
            
            if our_price < avg_competitor_price * 0.8:
                return "Positioned as cost-effective alternative to competitors."
            elif our_price > avg_competitor_price * 1.2:
                return "Premium positioning with superior value proposition."
            else:
                return "Competitively positioned within market range."
        
        return "Pricing aligned with competitive landscape."
    
    def _estimate_price_elasticity(self, industry: str) -> float:
        """Estimate price elasticity for the industry."""
        
        elasticities = {
            "software": -1.2,
            "ai_ml": -0.8,
            "fintech": -1.5,
            "healthcare": -0.6,
            "ecommerce": -2.0
        }
        
        return elasticities.get(industry, -1.0)
    
    def _calculate_market_size_confidence(
        self, 
        industry: str, 
        num_segments: int, 
        geographic_scope: str
    ) -> float:
        """Calculate confidence score for market size estimates."""
        
        base_confidence = 0.7
        
        # Industry data availability
        industry_confidence = {
            "software": 0.9,
            "ai_ml": 0.7,
            "fintech": 0.8,
            "healthcare": 0.8,
            "ecommerce": 0.9
        }.get(industry, 0.7)
        
        # Segment specificity
        segment_confidence = min(0.9, 0.5 + (num_segments * 0.1))
        
        # Geographic scope
        geo_confidence = {
            "global": 0.6,
            "north_america": 0.8,
            "us_only": 0.9,
            "europe": 0.7,
            "asia_pacific": 0.6,
            "emerging_markets": 0.5
        }.get(geographic_scope, 0.7)
        
        # Weighted average
        confidence = (
            industry_confidence * 0.4 +
            segment_confidence * 0.3 +
            geo_confidence * 0.3
        )
        
        return min(0.95, confidence)


# Global service instance
business_modeling_service = BusinessModelingService()
