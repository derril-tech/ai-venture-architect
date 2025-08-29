"""Tests for business modeling service."""

import pytest
import pytest_asyncio
from unittest.mock import Mock, patch

from api.services.business_modeling import BusinessModelingService, MarketSizeResult, UnitEconomicsResult


class TestBusinessModelingService:
    """Test cases for BusinessModelingService."""
    
    @pytest.fixture
    def service(self):
        """Create business modeling service instance."""
        return BusinessModelingService()
    
    @pytest.mark.asyncio
    async def test_calculate_market_size_top_down(self, service):
        """Test top-down market size calculation."""
        result = await service._calculate_top_down_market_size(
            industry="software",
            target_segments=["enterprise", "smb"],
            geographic_scope="global"
        )
        
        assert isinstance(result, MarketSizeResult)
        assert result.tam > 0
        assert result.sam > 0
        assert result.som > 0
        assert result.sam <= result.tam
        assert result.som <= result.sam
        assert result.methodology == "top_down"
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    async def test_calculate_market_size_bottom_up(self, service):
        """Test bottom-up market size calculation."""
        result = await service._calculate_bottom_up_market_size(
            industry="ai_ml",
            target_segments=["startups", "enterprise"],
            geographic_scope="north_america"
        )
        
        assert isinstance(result, MarketSizeResult)
        assert result.tam > 0
        assert result.sam > 0
        assert result.som > 0
        assert result.methodology == "bottom_up"
        assert "customer_segments" in result.assumptions
        assert "total_target_customers" in result.assumptions
    
    @pytest.mark.asyncio
    async def test_calculate_market_size_hybrid(self, service):
        """Test hybrid market size calculation."""
        result = await service.calculate_market_size(
            industry="fintech",
            target_segments=["smb", "consumers"],
            geographic_scope="global",
            methodology="hybrid"
        )
        
        assert isinstance(result, MarketSizeResult)
        assert result.methodology == "hybrid"
        assert "top_down" in result.assumptions
        assert "bottom_up" in result.assumptions
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    async def test_calculate_unit_economics(self, service):
        """Test unit economics calculation."""
        assumptions = {
            "monthly_revenue_per_customer": 100,
            "churn_rate_monthly": 0.05,
            "gross_margin": 0.8,
            "cac_multiplier": 1.2
        }
        
        result = await service.calculate_unit_economics(
            industry="software",
            pricing_model="subscription",
            customer_segments=["smb"],
            assumptions=assumptions
        )
        
        assert isinstance(result, UnitEconomicsResult)
        assert result.cac > 0
        assert result.ltv > 0
        assert result.ltv_cac_ratio > 0
        assert result.payback_period_months > 0
        assert result.gross_margin == 0.8
        assert len(result.sensitivity_analysis) > 0
    
    @pytest.mark.asyncio
    async def test_recommend_pricing_strategy(self, service):
        """Test pricing strategy recommendation."""
        competitor_pricing = {
            "competitor_a": {"starter": 29, "pro": 99},
            "competitor_b": {"basic": 19, "premium": 79}
        }
        
        result = await service.recommend_pricing_strategy(
            industry="software",
            target_segments=["smb", "enterprise"],
            competitor_pricing=competitor_pricing,
            value_proposition="10x faster analysis"
        )
        
        assert result.model in ["subscription", "freemium", "usage_based", "enterprise"]
        assert len(result.tiers) > 0
        assert result.rationale is not None
        assert result.competitive_positioning is not None
        assert isinstance(result.revenue_projections, dict)
        
        # Check tier structure
        for tier in result.tiers:
            assert "name" in tier
            assert "price" in tier
            assert "features" in tier
            assert "target" in tier
    
    def test_get_geographic_multiplier(self, service):
        """Test geographic multiplier calculation."""
        global_mult = service._get_geographic_multiplier("global")
        us_mult = service._get_geographic_multiplier("us_only")
        emerging_mult = service._get_geographic_multiplier("emerging_markets")
        
        assert global_mult == 1.0
        assert us_mult < global_mult
        assert emerging_mult < us_mult
    
    def test_estimate_sam_percentage(self, service):
        """Test SAM percentage estimation."""
        software_sam = service._estimate_sam_percentage("software", ["enterprise", "smb"])
        ai_sam = service._estimate_sam_percentage("ai_ml", ["startups"])
        
        assert 0 < software_sam < 1
        assert 0 < ai_sam < 1
        assert software_sam != ai_sam  # Different industries should have different SAM %
    
    def test_estimate_target_customers(self, service):
        """Test target customer estimation."""
        estimates = service._estimate_target_customers(
            industry="software",
            segments=["enterprise", "smb"],
            geographic_scope="global"
        )
        
        assert isinstance(estimates, dict)
        assert "enterprise" in estimates
        assert "smb" in estimates
        assert estimates["enterprise"] > 0
        assert estimates["smb"] > 0
        assert estimates["smb"] > estimates["enterprise"]  # More SMBs than enterprises
    
    def test_estimate_arpu(self, service):
        """Test ARPU estimation."""
        enterprise_arpu = service._estimate_arpu("software", ["enterprise"])
        consumer_arpu = service._estimate_arpu("software", ["consumers"])
        
        assert enterprise_arpu > 0
        assert consumer_arpu > 0
        assert enterprise_arpu > consumer_arpu  # Enterprise should have higher ARPU
    
    def test_calculate_cac(self, service):
        """Test CAC calculation."""
        freemium_cac = service._calculate_cac("software", "freemium", {})
        enterprise_cac = service._calculate_cac("software", "enterprise", {})
        
        assert freemium_cac > 0
        assert enterprise_cac > 0
        assert enterprise_cac > freemium_cac  # Enterprise CAC should be higher
    
    def test_calculate_ltv(self, service):
        """Test LTV calculation."""
        assumptions = {
            "monthly_revenue_per_customer": 100,
            "churn_rate_monthly": 0.05,
            "gross_margin": 0.8
        }
        
        benchmarks = {
            "churn_rate_monthly": 0.05,
            "gross_margin": 0.8
        }
        
        ltv = service._calculate_ltv("software", "subscription", assumptions, benchmarks)
        
        assert ltv > 0
        # LTV should be monthly revenue * gross margin * lifetime (1/churn)
        expected_ltv = 100 * 0.8 * (1/0.05)
        assert abs(ltv - expected_ltv) < 1  # Allow small floating point differences
    
    def test_perform_sensitivity_analysis(self, service):
        """Test sensitivity analysis."""
        sensitivity = service._perform_sensitivity_analysis(
            cac=1000,
            ltv=3000,
            monthly_revenue=200,
            gross_margin=0.8
        )
        
        assert isinstance(sensitivity, dict)
        assert len(sensitivity) > 0
        
        # Check that scenarios have required fields
        for scenario_name, scenario_data in sensitivity.items():
            assert "ltv_cac_ratio" in scenario_data
            assert scenario_data["ltv_cac_ratio"] > 0
    
    def test_determine_optimal_pricing_model(self, service):
        """Test pricing model determination."""
        enterprise_model = service._determine_optimal_pricing_model(
            "software", ["enterprise"], None
        )
        consumer_model = service._determine_optimal_pricing_model(
            "software", ["consumers"], None
        )
        developer_model = service._determine_optimal_pricing_model(
            "software", ["developers"], None
        )
        
        assert enterprise_model == "enterprise"
        assert consumer_model == "freemium"
        assert developer_model == "usage_based"
    
    def test_generate_pricing_tiers(self, service):
        """Test pricing tier generation."""
        tiers = service._generate_pricing_tiers("software", "subscription", None)
        
        assert len(tiers) >= 3  # At least starter, pro, enterprise
        
        # Check tier structure
        for tier in tiers:
            assert "name" in tier
            assert "price" in tier
            assert "billing" in tier
            assert "features" in tier
            assert "target" in tier
        
        # Prices should generally increase
        prices = [tier["price"] for tier in tiers if tier["price"] > 0]
        assert prices == sorted(prices)
    
    def test_project_revenue(self, service):
        """Test revenue projection."""
        tiers = [
            {"name": "Starter", "price": 29},
            {"name": "Professional", "price": 99},
            {"name": "Enterprise", "price": 299}
        ]
        
        projections = service._project_revenue(tiers, ["smb", "enterprise"])
        
        assert "total_monthly" in projections
        assert "total_annual" in projections
        assert projections["total_annual"] == projections["total_monthly"] * 12
        
        # Check individual tier projections
        for tier in tiers:
            tier_name = tier["name"].lower()
            assert f"{tier_name}_monthly" in projections
            assert f"{tier_name}_annual" in projections
    
    def test_calculate_market_size_confidence(self, service):
        """Test market size confidence calculation."""
        high_confidence = service._calculate_market_size_confidence(
            industry="software",  # Well-known industry
            num_segments=3,       # Good segment specificity
            geographic_scope="us_only"  # Well-defined geography
        )
        
        low_confidence = service._calculate_market_size_confidence(
            industry="unknown_industry",
            num_segments=1,
            geographic_scope="emerging_markets"
        )
        
        assert 0 <= high_confidence <= 1
        assert 0 <= low_confidence <= 1
        assert high_confidence > low_confidence
    
    def test_categorize_prices(self, service):
        """Test price categorization."""
        prices = [5, 25, 75, 150, 750]
        categories = service._categorize_prices(prices)
        
        expected_keys = ["under_10", "10_to_50", "50_to_100", "100_to_500", "over_500"]
        assert all(key in categories for key in expected_keys)
        
        assert categories["under_10"] == 1  # $5
        assert categories["10_to_50"] == 1  # $25
        assert categories["50_to_100"] == 1  # $75
        assert categories["100_to_500"] == 1  # $150
        assert categories["over_500"] == 1  # $750
