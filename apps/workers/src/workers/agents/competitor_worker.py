"""Competitor analysis worker for pricing, features, and traction analysis."""

import re
import json
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, and_, func
import httpx
from bs4 import BeautifulSoup

from workers.core.worker import BaseWorker
from workers.core.config import get_settings
from workers.connectors.base import BaseConnector

logger = structlog.get_logger()
settings = get_settings()

# Database setup
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class CompetitorWorker(BaseWorker):
    """Worker for competitor analysis and benchmarking."""
    
    def __init__(self, nats_client):
        super().__init__(nats_client, "competitor.analyze")
        
        # Pricing extraction patterns
        self.pricing_patterns = [
            r'\$(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:per|/)\s*(?:month|mo|user|seat)',
            r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:USD|dollars?)\s*(?:per|/)\s*(?:month|mo)',
            r'Starting\s+at\s+\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'From\s+\$(\d+(?:,\d{3})*(?:\.\d{2})?)',
            r'Free\s+(?:tier|plan)',
            r'Enterprise\s+pricing',
            r'Contact\s+(?:us|sales)\s+for\s+pricing'
        ]
        
        # Feature extraction keywords
        self.feature_categories = {
            "core_features": [
                "dashboard", "analytics", "reporting", "api", "integration",
                "automation", "workflow", "collaboration", "security", "backup"
            ],
            "advanced_features": [
                "ai", "machine learning", "ml", "artificial intelligence",
                "custom", "enterprise", "sso", "saml", "ldap", "audit"
            ],
            "platform_features": [
                "mobile app", "web app", "desktop", "cloud", "on-premise",
                "multi-tenant", "white-label", "marketplace", "plugins"
            ],
            "support_features": [
                "24/7 support", "phone support", "chat support", "email support",
                "documentation", "training", "onboarding", "community"
            ]
        }
    
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process competitor analysis request."""
        workspace_id = payload.get("workspace_id")
        competitors = payload.get("competitors", [])  # List of competitor URLs or names
        analysis_type = payload.get("analysis_type", "full")  # full, pricing, features, traction
        
        if not workspace_id:
            raise ValueError("Missing required field: workspace_id")
        
        logger.info(f"Starting competitor analysis for workspace: {workspace_id}")
        
        try:
            results = {}
            
            if analysis_type in ["full", "pricing"]:
                pricing_analysis = await self._analyze_pricing(competitors)
                results["pricing"] = pricing_analysis
            
            if analysis_type in ["full", "features"]:
                feature_analysis = await self._analyze_features(competitors)
                results["features"] = feature_analysis
            
            if analysis_type in ["full", "traction"]:
                traction_analysis = await self._analyze_traction(competitors)
                results["traction"] = traction_analysis
            
            # Store analysis results
            await self._store_analysis(workspace_id, results)
            
            logger.info(f"Competitor analysis completed for {len(competitors)} competitors")
            
            return {
                "status": "completed",
                "workspace_id": workspace_id,
                "competitor_count": len(competitors),
                "analysis_type": analysis_type,
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Competitor analysis failed: {e}")
            return {
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(e)
            }
    
    async def _analyze_pricing(self, competitors: List[str]) -> Dict[str, Any]:
        """Analyze competitor pricing strategies."""
        pricing_data = {}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for competitor in competitors:
                try:
                    pricing_info = await self._extract_pricing_info(client, competitor)
                    pricing_data[competitor] = pricing_info
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze pricing for {competitor}: {e}")
                    pricing_data[competitor] = {"error": str(e)}
        
        # Analyze pricing patterns
        analysis = self._analyze_pricing_patterns(pricing_data)
        
        return {
            "individual_pricing": pricing_data,
            "pricing_analysis": analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    async def _extract_pricing_info(self, client: httpx.AsyncClient, competitor: str) -> Dict[str, Any]:
        """Extract pricing information from competitor website."""
        # Try common pricing page URLs
        pricing_urls = [
            f"{competitor}/pricing",
            f"{competitor}/plans",
            f"{competitor}/pricing-plans",
            f"{competitor}/subscribe",
            f"{competitor}/buy"
        ]
        
        pricing_info = {
            "plans": [],
            "pricing_model": "unknown",
            "free_tier": False,
            "enterprise_pricing": False,
            "extracted_prices": []
        }
        
        for url in pricing_urls:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Extract pricing information
                    pricing_info.update(await self._parse_pricing_page(soup, url))
                    break
                    
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                continue
        
        return pricing_info
    
    async def _parse_pricing_page(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """Parse pricing information from HTML."""
        pricing_info = {
            "plans": [],
            "pricing_model": "unknown",
            "free_tier": False,
            "enterprise_pricing": False,
            "extracted_prices": [],
            "source_url": url
        }
        
        page_text = soup.get_text().lower()
        
        # Check for free tier
        if any(term in page_text for term in ["free", "free tier", "free plan", "$0"]):
            pricing_info["free_tier"] = True
        
        # Check for enterprise pricing
        if any(term in page_text for term in ["enterprise", "contact sales", "custom pricing"]):
            pricing_info["enterprise_pricing"] = True
        
        # Extract prices using regex patterns
        for pattern in self.pricing_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                try:
                    if isinstance(match, tuple):
                        price_str = match[0]
                    else:
                        price_str = match
                    
                    # Clean and convert price
                    price_clean = re.sub(r'[,$]', '', price_str)
                    if price_clean.replace('.', '').isdigit():
                        price = float(price_clean)
                        pricing_info["extracted_prices"].append(price)
                except ValueError:
                    continue
        
        # Try to identify pricing model
        if "per user" in page_text or "per seat" in page_text:
            pricing_info["pricing_model"] = "per_user"
        elif "per month" in page_text or "monthly" in page_text:
            pricing_info["pricing_model"] = "subscription"
        elif "one time" in page_text or "lifetime" in page_text:
            pricing_info["pricing_model"] = "one_time"
        elif "usage" in page_text or "pay as you go" in page_text:
            pricing_info["pricing_model"] = "usage_based"
        
        # Extract plan information from structured elements
        plan_elements = soup.find_all(['div', 'section'], class_=re.compile(r'plan|pricing|tier', re.I))
        
        for element in plan_elements[:5]:  # Limit to 5 plans
            plan_text = element.get_text()
            plan_info = {
                "name": self._extract_plan_name(plan_text),
                "price": self._extract_plan_price(plan_text),
                "features": self._extract_plan_features(plan_text)
            }
            
            if plan_info["name"] or plan_info["price"]:
                pricing_info["plans"].append(plan_info)
        
        return pricing_info
    
    def _extract_plan_name(self, text: str) -> Optional[str]:
        """Extract plan name from text."""
        # Look for common plan names
        plan_names = ["free", "basic", "pro", "premium", "enterprise", "starter", "business"]
        text_lower = text.lower()
        
        for name in plan_names:
            if name in text_lower:
                return name.title()
        
        return None
    
    def _extract_plan_price(self, text: str) -> Optional[float]:
        """Extract price from plan text."""
        for pattern in self.pricing_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    price_str = match.group(1) if match.groups() else match.group(0)
                    price_clean = re.sub(r'[,$]', '', price_str)
                    if price_clean.replace('.', '').isdigit():
                        return float(price_clean)
                except (ValueError, AttributeError):
                    continue
        
        return None
    
    def _extract_plan_features(self, text: str) -> List[str]:
        """Extract features from plan text."""
        features = []
        text_lower = text.lower()
        
        # Look for feature indicators
        feature_indicators = [
            "includes", "features", "✓", "✔", "•", "-", "unlimited", "up to"
        ]
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower().strip()
            if any(indicator in line_lower for indicator in feature_indicators):
                if len(line.strip()) > 3 and len(line.strip()) < 100:
                    features.append(line.strip())
        
        return features[:10]  # Limit to 10 features
    
    def _analyze_pricing_patterns(self, pricing_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze pricing patterns across competitors."""
        all_prices = []
        pricing_models = defaultdict(int)
        free_tier_count = 0
        enterprise_count = 0
        
        for competitor, data in pricing_data.items():
            if "error" in data:
                continue
            
            # Collect prices
            all_prices.extend(data.get("extracted_prices", []))
            
            # Count pricing models
            model = data.get("pricing_model", "unknown")
            pricing_models[model] += 1
            
            # Count free tiers and enterprise options
            if data.get("free_tier"):
                free_tier_count += 1
            if data.get("enterprise_pricing"):
                enterprise_count += 1
        
        analysis = {
            "total_competitors": len([d for d in pricing_data.values() if "error" not in d]),
            "price_statistics": {},
            "pricing_models": dict(pricing_models),
            "free_tier_percentage": free_tier_count / len(pricing_data) * 100 if pricing_data else 0,
            "enterprise_percentage": enterprise_count / len(pricing_data) * 100 if pricing_data else 0
        }
        
        if all_prices:
            import numpy as np
            analysis["price_statistics"] = {
                "min_price": min(all_prices),
                "max_price": max(all_prices),
                "median_price": np.median(all_prices),
                "mean_price": np.mean(all_prices),
                "price_ranges": self._categorize_prices(all_prices)
            }
        
        return analysis
    
    def _categorize_prices(self, prices: List[float]) -> Dict[str, int]:
        """Categorize prices into ranges."""
        ranges = {
            "under_10": 0,
            "10_to_50": 0,
            "50_to_100": 0,
            "100_to_500": 0,
            "over_500": 0
        }
        
        for price in prices:
            if price < 10:
                ranges["under_10"] += 1
            elif price < 50:
                ranges["10_to_50"] += 1
            elif price < 100:
                ranges["50_to_100"] += 1
            elif price < 500:
                ranges["100_to_500"] += 1
            else:
                ranges["over_500"] += 1
        
        return ranges
    
    async def _analyze_features(self, competitors: List[str]) -> Dict[str, Any]:
        """Analyze competitor features and capabilities."""
        feature_data = {}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for competitor in competitors:
                try:
                    features = await self._extract_features(client, competitor)
                    feature_data[competitor] = features
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze features for {competitor}: {e}")
                    feature_data[competitor] = {"error": str(e)}
        
        # Analyze feature patterns
        analysis = self._analyze_feature_patterns(feature_data)
        
        return {
            "individual_features": feature_data,
            "feature_analysis": analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    async def _extract_features(self, client: httpx.AsyncClient, competitor: str) -> Dict[str, Any]:
        """Extract features from competitor website."""
        feature_urls = [
            competitor,
            f"{competitor}/features",
            f"{competitor}/product",
            f"{competitor}/capabilities",
            f"{competitor}/solutions"
        ]
        
        all_features = {
            "core_features": [],
            "advanced_features": [],
            "platform_features": [],
            "support_features": [],
            "raw_features": []
        }
        
        for url in feature_urls:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    page_features = self._parse_features_page(soup)
                    
                    # Merge features
                    for category, features in page_features.items():
                        all_features[category].extend(features)
                    
            except Exception as e:
                logger.debug(f"Failed to fetch {url}: {e}")
                continue
        
        # Deduplicate features
        for category in all_features:
            all_features[category] = list(set(all_features[category]))
        
        return all_features
    
    def _parse_features_page(self, soup: BeautifulSoup) -> Dict[str, List[str]]:
        """Parse features from HTML page."""
        features = {
            "core_features": [],
            "advanced_features": [],
            "platform_features": [],
            "support_features": [],
            "raw_features": []
        }
        
        page_text = soup.get_text().lower()
        
        # Extract features by category
        for category, keywords in self.feature_categories.items():
            for keyword in keywords:
                if keyword in page_text:
                    features[category].append(keyword)
        
        # Extract structured feature lists
        feature_elements = soup.find_all(['ul', 'ol', 'div'], class_=re.compile(r'feature|benefit|capability', re.I))
        
        for element in feature_elements:
            items = element.find_all(['li', 'div', 'span'])
            for item in items:
                text = item.get_text().strip()
                if 10 < len(text) < 100:  # Reasonable feature length
                    features["raw_features"].append(text)
        
        return features
    
    def _analyze_feature_patterns(self, feature_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze feature patterns across competitors."""
        feature_counts = defaultdict(int)
        category_counts = defaultdict(int)
        
        for competitor, data in feature_data.items():
            if "error" in data:
                continue
            
            for category, features in data.items():
                if category != "raw_features":
                    category_counts[category] += len(features)
                    for feature in features:
                        feature_counts[feature] += 1
        
        # Find most common features
        common_features = sorted(feature_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        
        return {
            "total_competitors": len([d for d in feature_data.values() if "error" not in d]),
            "common_features": common_features,
            "category_distribution": dict(category_counts),
            "feature_gaps": self._identify_feature_gaps(feature_data),
            "unique_features": self._identify_unique_features(feature_data)
        }
    
    def _identify_feature_gaps(self, feature_data: Dict[str, Any]) -> List[str]:
        """Identify potential feature gaps in the market."""
        # This is a simplified implementation
        # In production, you'd use more sophisticated analysis
        
        expected_features = [
            "api", "mobile app", "analytics", "reporting", "integrations",
            "automation", "collaboration", "security", "backup", "sso"
        ]
        
        gaps = []
        for feature in expected_features:
            count = 0
            for competitor, data in feature_data.items():
                if "error" not in data:
                    all_features = []
                    for category_features in data.values():
                        if isinstance(category_features, list):
                            all_features.extend(category_features)
                    
                    if any(feature in f.lower() for f in all_features):
                        count += 1
            
            # If less than 50% of competitors have this feature, it's a potential gap
            if count < len(feature_data) * 0.5:
                gaps.append(feature)
        
        return gaps
    
    def _identify_unique_features(self, feature_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Identify unique features for each competitor."""
        unique_features = {}
        
        # Collect all features
        all_features = defaultdict(set)
        for competitor, data in feature_data.items():
            if "error" not in data:
                competitor_features = set()
                for category_features in data.values():
                    if isinstance(category_features, list):
                        competitor_features.update(f.lower() for f in category_features)
                all_features[competitor] = competitor_features
        
        # Find unique features
        for competitor, features in all_features.items():
            unique = []
            for feature in features:
                # Check if this feature appears in other competitors
                appears_elsewhere = any(
                    feature in other_features 
                    for other_comp, other_features in all_features.items() 
                    if other_comp != competitor
                )
                if not appears_elsewhere:
                    unique.append(feature)
            
            unique_features[competitor] = unique[:10]  # Limit to top 10
        
        return unique_features
    
    async def _analyze_traction(self, competitors: List[str]) -> Dict[str, Any]:
        """Analyze competitor traction metrics."""
        traction_data = {}
        
        for competitor in competitors:
            try:
                metrics = await self._extract_traction_metrics(competitor)
                traction_data[competitor] = metrics
                
            except Exception as e:
                logger.warning(f"Failed to analyze traction for {competitor}: {e}")
                traction_data[competitor] = {"error": str(e)}
        
        # Analyze traction patterns
        analysis = self._analyze_traction_patterns(traction_data)
        
        return {
            "individual_traction": traction_data,
            "traction_analysis": analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
    
    async def _extract_traction_metrics(self, competitor: str) -> Dict[str, Any]:
        """Extract traction metrics for a competitor."""
        metrics = {
            "web_metrics": {},
            "social_metrics": {},
            "product_metrics": {},
            "funding_metrics": {}
        }
        
        # This would integrate with various APIs and data sources
        # For now, we'll implement basic web scraping
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # Try to get basic web metrics
                response = await client.get(competitor)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    
                    # Look for traction indicators in the page
                    page_text = soup.get_text().lower()
                    
                    # Extract customer count indicators
                    customer_patterns = [
                        r'(\d+(?:,\d{3})*(?:\+)?)\s*(?:customers?|users?|companies?)',
                        r'trusted\s+by\s+(\d+(?:,\d{3})*(?:\+)?)',
                        r'over\s+(\d+(?:,\d{3})*(?:\+)?)\s+(?:customers?|users?)'
                    ]
                    
                    for pattern in customer_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            try:
                                count_str = match.group(1).replace(',', '').replace('+', '')
                                metrics["product_metrics"]["customer_count"] = int(count_str)
                                break
                            except ValueError:
                                continue
                    
                    # Look for funding information
                    funding_keywords = ["raised", "funding", "series", "investment", "million", "billion"]
                    if any(keyword in page_text for keyword in funding_keywords):
                        metrics["funding_metrics"]["has_funding_info"] = True
                    
                    # Look for team size indicators
                    team_patterns = [
                        r'(\d+)\s*(?:employees?|team\s+members?|people)',
                        r'team\s+of\s+(\d+)'
                    ]
                    
                    for pattern in team_patterns:
                        match = re.search(pattern, page_text)
                        if match:
                            try:
                                metrics["product_metrics"]["team_size"] = int(match.group(1))
                                break
                            except ValueError:
                                continue
                
            except Exception as e:
                logger.debug(f"Failed to extract traction metrics from {competitor}: {e}")
        
        return metrics
    
    def _analyze_traction_patterns(self, traction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze traction patterns across competitors."""
        customer_counts = []
        team_sizes = []
        funded_count = 0
        
        for competitor, data in traction_data.items():
            if "error" in data:
                continue
            
            # Collect customer counts
            if "customer_count" in data.get("product_metrics", {}):
                customer_counts.append(data["product_metrics"]["customer_count"])
            
            # Collect team sizes
            if "team_size" in data.get("product_metrics", {}):
                team_sizes.append(data["product_metrics"]["team_size"])
            
            # Count funded companies
            if data.get("funding_metrics", {}).get("has_funding_info"):
                funded_count += 1
        
        analysis = {
            "total_competitors": len([d for d in traction_data.values() if "error" not in d]),
            "funded_percentage": funded_count / len(traction_data) * 100 if traction_data else 0
        }
        
        if customer_counts:
            import numpy as np
            analysis["customer_statistics"] = {
                "min_customers": min(customer_counts),
                "max_customers": max(customer_counts),
                "median_customers": np.median(customer_counts),
                "mean_customers": np.mean(customer_counts)
            }
        
        if team_sizes:
            import numpy as np
            analysis["team_statistics"] = {
                "min_team_size": min(team_sizes),
                "max_team_size": max(team_sizes),
                "median_team_size": np.median(team_sizes),
                "mean_team_size": np.mean(team_sizes)
            }
        
        return analysis
    
    async def _store_analysis(self, workspace_id: str, results: Dict[str, Any]):
        """Store competitor analysis results."""
        # In a full implementation, you would store these in dedicated tables
        # For now, we'll log the results
        logger.info(
            "Competitor analysis results",
            workspace_id=workspace_id,
            analysis_types=list(results.keys()),
            competitor_count=len(results.get("pricing", {}).get("individual_pricing", {}))
        )
