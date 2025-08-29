"""Safety and bias control service for AI-generated content."""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from api.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class SafetyCheckResult:
    """Result of safety and bias checks."""
    passed: bool
    score: float  # 0-1, higher is safer
    violations: List[Dict[str, Any]]
    recommendations: List[str]
    metadata: Dict[str, Any]


@dataclass
class SourceDiversityResult:
    """Result of source diversity analysis."""
    diversity_score: float  # 0-1, higher is more diverse
    source_distribution: Dict[str, int]
    bias_indicators: List[str]
    recommendations: List[str]


@dataclass
class RecencyCheckResult:
    """Result of content recency analysis."""
    recency_score: float  # 0-1, higher is more recent
    avg_age_days: float
    stale_content_percentage: float
    recommendations: List[str]


class SafetyService:
    """Service for safety, bias, and quality control."""
    
    def __init__(self):
        # Bias detection patterns
        self.bias_patterns = {
            "gender_bias": [
                r"\b(he|his|him)\b.*\b(developer|engineer|CEO|founder)\b",
                r"\b(she|her)\b.*\b(assistant|secretary|nurse)\b",
                r"\bmale-dominated\b",
                r"\bboys club\b"
            ],
            "age_bias": [
                r"\byoung\s+(entrepreneur|founder|developer)\b",
                r"\bold\s+school\b",
                r"\bmillennial\s+mindset\b",
                r"\bboomer\s+mentality\b"
            ],
            "cultural_bias": [
                r"\bwestern\s+approach\b",
                r"\bamerican\s+way\b",
                r"\bfirst\s+world\s+problem\b",
                r"\bdeveloped\s+country\s+solution\b"
            ],
            "economic_bias": [
                r"\bpremium\s+customers?\b",
                r"\bhigh-end\s+market\b",
                r"\bluxury\s+segment\b",
                r"\baffordable\s+for\s+everyone\b"
            ]
        }
        
        # Harmful content patterns
        self.harmful_patterns = [
            r"\b(scam|fraud|ponzi|pyramid)\b",
            r"\b(illegal|unlawful|criminal)\b",
            r"\b(discriminat|racist|sexist)\b",
            r"\b(violence|violent|harm)\b",
            r"\b(hate|hatred|bigot)\b"
        ]
        
        # Quality indicators
        self.quality_indicators = {
            "positive": [
                "evidence", "research", "study", "analysis", "data",
                "validated", "tested", "proven", "verified", "confirmed"
            ],
            "negative": [
                "rumor", "speculation", "unconfirmed", "alleged", "supposedly",
                "might", "could be", "possibly", "maybe", "unclear"
            ]
        }
        
        # Source reliability tiers
        self.source_reliability = {
            "tier_1": ["arxiv", "pubmed", "ieee", "acm", "nature", "science"],
            "tier_2": ["techcrunch", "wired", "mit_tech_review", "harvard_business_review"],
            "tier_3": ["github", "product_hunt", "crunchbase", "bloomberg"],
            "tier_4": ["reddit", "twitter", "medium", "blog"],
            "tier_5": ["unknown", "social_media", "forum"]
        }
        
        # Recency thresholds (days)
        self.recency_thresholds = {
            "fresh": 7,
            "recent": 30,
            "current": 90,
            "outdated": 365,
            "stale": float('inf')
        }
    
    async def comprehensive_safety_check(
        self,
        content: str,
        sources: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> SafetyCheckResult:
        """Perform comprehensive safety and bias check."""
        
        violations = []
        recommendations = []
        scores = []
        
        # Bias detection
        bias_result = self._detect_bias(content)
        if bias_result["violations"]:
            violations.extend(bias_result["violations"])
            recommendations.extend(bias_result["recommendations"])
        scores.append(bias_result["score"])
        
        # Harmful content detection
        harmful_result = self._detect_harmful_content(content)
        if harmful_result["violations"]:
            violations.extend(harmful_result["violations"])
            recommendations.extend(harmful_result["recommendations"])
        scores.append(harmful_result["score"])
        
        # Source diversity check
        diversity_result = await self._check_source_diversity(sources)
        if diversity_result.diversity_score < 0.6:
            violations.append({
                "type": "source_diversity",
                "severity": "medium",
                "message": f"Low source diversity: {diversity_result.diversity_score:.2f}",
                "details": diversity_result.source_distribution
            })
            recommendations.extend(diversity_result.recommendations)
        scores.append(diversity_result.diversity_score)
        
        # Recency check
        recency_result = await self._check_content_recency(sources)
        if recency_result.recency_score < 0.5:
            violations.append({
                "type": "content_recency",
                "severity": "low",
                "message": f"Content may be outdated: avg age {recency_result.avg_age_days:.1f} days",
                "details": {"stale_percentage": recency_result.stale_content_percentage}
            })
            recommendations.extend(recency_result.recommendations)
        scores.append(recency_result.recency_score)
        
        # Quality assessment
        quality_result = self._assess_content_quality(content)
        scores.append(quality_result["score"])
        if quality_result["recommendations"]:
            recommendations.extend(quality_result["recommendations"])
        
        # Calculate overall safety score
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        # Determine if checks passed
        critical_violations = [v for v in violations if v.get("severity") == "critical"]
        passed = len(critical_violations) == 0 and overall_score >= 0.6
        
        return SafetyCheckResult(
            passed=passed,
            score=overall_score,
            violations=violations,
            recommendations=list(set(recommendations)),  # Remove duplicates
            metadata={
                "bias_score": bias_result["score"],
                "harmful_content_score": harmful_result["score"],
                "diversity_score": diversity_result.diversity_score,
                "recency_score": recency_result.recency_score,
                "quality_score": quality_result["score"],
                "total_sources": len(sources),
                "check_timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def _detect_bias(self, content: str) -> Dict[str, Any]:
        """Detect potential bias in content."""
        violations = []
        recommendations = []
        content_lower = content.lower()
        
        bias_scores = []
        
        for bias_type, patterns in self.bias_patterns.items():
            matches = []
            for pattern in patterns:
                found = re.findall(pattern, content_lower, re.IGNORECASE)
                matches.extend(found)
            
            if matches:
                violations.append({
                    "type": "bias_detection",
                    "subtype": bias_type,
                    "severity": "medium",
                    "message": f"Potential {bias_type.replace('_', ' ')} detected",
                    "matches": matches[:3],  # Limit to first 3 matches
                    "count": len(matches)
                })
                
                recommendations.append(f"Review content for {bias_type.replace('_', ' ')} and ensure inclusive language")
                bias_scores.append(0.3)  # Lower score for bias detection
            else:
                bias_scores.append(1.0)  # Perfect score for no bias
        
        # Calculate overall bias score
        bias_score = sum(bias_scores) / len(bias_scores) if bias_scores else 1.0
        
        return {
            "score": bias_score,
            "violations": violations,
            "recommendations": recommendations
        }
    
    def _detect_harmful_content(self, content: str) -> Dict[str, Any]:
        """Detect potentially harmful content."""
        violations = []
        recommendations = []
        content_lower = content.lower()
        
        harmful_matches = []
        for pattern in self.harmful_patterns:
            matches = re.findall(pattern, content_lower, re.IGNORECASE)
            harmful_matches.extend(matches)
        
        if harmful_matches:
            violations.append({
                "type": "harmful_content",
                "severity": "critical",
                "message": "Potentially harmful content detected",
                "matches": harmful_matches[:5],  # Limit to first 5 matches
                "count": len(harmful_matches)
            })
            
            recommendations.append("Remove or revise potentially harmful content")
            recommendations.append("Ensure content complies with platform guidelines")
            
            score = max(0.0, 1.0 - (len(harmful_matches) * 0.2))  # Penalize heavily
        else:
            score = 1.0
        
        return {
            "score": score,
            "violations": violations,
            "recommendations": recommendations
        }
    
    async def _check_source_diversity(self, sources: List[Dict[str, Any]]) -> SourceDiversityResult:
        """Check diversity of information sources."""
        if not sources:
            return SourceDiversityResult(
                diversity_score=0.0,
                source_distribution={},
                bias_indicators=["No sources provided"],
                recommendations=["Add diverse, credible sources"]
            )
        
        # Analyze source distribution
        source_types = defaultdict(int)
        source_reliability_scores = []
        
        for source in sources:
            source_name = source.get("source", "unknown").lower()
            source_types[source_name] += 1
            
            # Assign reliability score
            reliability_score = self._get_source_reliability_score(source_name)
            source_reliability_scores.append(reliability_score)
        
        # Calculate diversity metrics
        total_sources = len(sources)
        unique_sources = len(source_types)
        
        # Shannon diversity index
        diversity_score = 0.0
        for count in source_types.values():
            proportion = count / total_sources
            if proportion > 0:
                diversity_score -= proportion * (proportion ** 0.5)  # Modified Shannon
        
        # Normalize diversity score
        max_possible_diversity = 1.0
        diversity_score = min(1.0, diversity_score / max_possible_diversity)
        
        # Identify bias indicators
        bias_indicators = []
        recommendations = []
        
        # Check for over-reliance on single source
        max_source_percentage = max(source_types.values()) / total_sources
        if max_source_percentage > 0.5:
            bias_indicators.append(f"Over-reliance on single source type ({max_source_percentage:.1%})")
            recommendations.append("Diversify information sources")
        
        # Check source reliability
        avg_reliability = sum(source_reliability_scores) / len(source_reliability_scores)
        if avg_reliability < 0.6:
            bias_indicators.append("Low average source reliability")
            recommendations.append("Include more authoritative sources")
        
        # Check for missing source types
        if unique_sources < 3:
            bias_indicators.append("Limited source type diversity")
            recommendations.append("Include sources from different categories (academic, industry, news)")
        
        return SourceDiversityResult(
            diversity_score=diversity_score,
            source_distribution=dict(source_types),
            bias_indicators=bias_indicators,
            recommendations=recommendations
        )
    
    async def _check_content_recency(self, sources: List[Dict[str, Any]]) -> RecencyCheckResult:
        """Check recency of content sources."""
        if not sources:
            return RecencyCheckResult(
                recency_score=0.0,
                avg_age_days=float('inf'),
                stale_content_percentage=1.0,
                recommendations=["Add recent sources"]
            )
        
        current_time = datetime.utcnow()
        ages_days = []
        recency_categories = defaultdict(int)
        
        for source in sources:
            # Try to get timestamp from various fields
            timestamp_str = (
                source.get("published_at") or 
                source.get("created_at") or 
                source.get("updated_at")
            )
            
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, str):
                        # Handle ISO format
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    else:
                        timestamp = timestamp_str
                    
                    age_days = (current_time - timestamp).days
                    ages_days.append(age_days)
                    
                    # Categorize by recency
                    if age_days <= self.recency_thresholds["fresh"]:
                        recency_categories["fresh"] += 1
                    elif age_days <= self.recency_thresholds["recent"]:
                        recency_categories["recent"] += 1
                    elif age_days <= self.recency_thresholds["current"]:
                        recency_categories["current"] += 1
                    elif age_days <= self.recency_thresholds["outdated"]:
                        recency_categories["outdated"] += 1
                    else:
                        recency_categories["stale"] += 1
                        
                except (ValueError, TypeError):
                    # If timestamp parsing fails, assume old content
                    ages_days.append(365)  # Assume 1 year old
                    recency_categories["stale"] += 1
            else:
                # No timestamp available, assume old
                ages_days.append(365)
                recency_categories["stale"] += 1
        
        # Calculate metrics
        avg_age_days = sum(ages_days) / len(ages_days) if ages_days else 365
        stale_count = recency_categories["outdated"] + recency_categories["stale"]
        stale_percentage = stale_count / len(sources)
        
        # Calculate recency score (0-1, higher is better)
        if avg_age_days <= 7:
            recency_score = 1.0
        elif avg_age_days <= 30:
            recency_score = 0.8
        elif avg_age_days <= 90:
            recency_score = 0.6
        elif avg_age_days <= 365:
            recency_score = 0.4
        else:
            recency_score = 0.2
        
        # Adjust score based on stale content percentage
        recency_score *= (1.0 - stale_percentage * 0.5)
        
        # Generate recommendations
        recommendations = []
        if stale_percentage > 0.3:
            recommendations.append("Include more recent sources (within last 30 days)")
        if recency_categories["fresh"] == 0:
            recommendations.append("Add fresh sources from the last week")
        if avg_age_days > 180:
            recommendations.append("Content may be outdated - verify current relevance")
        
        return RecencyCheckResult(
            recency_score=recency_score,
            avg_age_days=avg_age_days,
            stale_content_percentage=stale_percentage,
            recommendations=recommendations
        )
    
    def _assess_content_quality(self, content: str) -> Dict[str, Any]:
        """Assess overall content quality."""
        content_lower = content.lower()
        recommendations = []
        
        # Count quality indicators
        positive_indicators = sum(1 for indicator in self.quality_indicators["positive"] 
                                if indicator in content_lower)
        negative_indicators = sum(1 for indicator in self.quality_indicators["negative"] 
                                if indicator in content_lower)
        
        # Calculate quality score
        total_indicators = positive_indicators + negative_indicators
        if total_indicators > 0:
            quality_score = positive_indicators / total_indicators
        else:
            quality_score = 0.5  # Neutral if no indicators
        
        # Content length assessment
        word_count = len(content.split())
        if word_count < 50:
            quality_score *= 0.8
            recommendations.append("Content may be too brief - consider adding more detail")
        elif word_count > 2000:
            quality_score *= 0.9
            recommendations.append("Content may be too lengthy - consider summarizing key points")
        
        # Check for citations/references
        citation_patterns = [r"\[.*\]", r"\(.*\)", r"source:", r"according to", r"study shows"]
        has_citations = any(re.search(pattern, content_lower) for pattern in citation_patterns)
        
        if not has_citations:
            quality_score *= 0.9
            recommendations.append("Consider adding citations or references to support claims")
        
        # Check for speculation vs facts
        speculation_ratio = negative_indicators / max(1, positive_indicators)
        if speculation_ratio > 0.5:
            quality_score *= 0.8
            recommendations.append("Content contains high speculation - add more factual evidence")
        
        return {
            "score": quality_score,
            "recommendations": recommendations,
            "metadata": {
                "word_count": word_count,
                "positive_indicators": positive_indicators,
                "negative_indicators": negative_indicators,
                "has_citations": has_citations,
                "speculation_ratio": speculation_ratio
            }
        }
    
    def _get_source_reliability_score(self, source_name: str) -> float:
        """Get reliability score for a source."""
        source_lower = source_name.lower()
        
        for tier, sources in self.source_reliability.items():
            if any(reliable_source in source_lower for reliable_source in sources):
                if tier == "tier_1":
                    return 1.0
                elif tier == "tier_2":
                    return 0.8
                elif tier == "tier_3":
                    return 0.6
                elif tier == "tier_4":
                    return 0.4
                else:  # tier_5
                    return 0.2
        
        return 0.3  # Default for unknown sources
    
    async def enforce_citation_requirements(
        self,
        content: str,
        claims: List[str],
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Enforce citation requirements for claims."""
        
        violations = []
        recommendations = []
        
        # Check if major claims have citations
        uncited_claims = []
        
        for claim in claims:
            # Simple heuristic: look for nearby citations
            claim_lower = claim.lower()
            
            # Look for citation patterns near the claim
            has_citation = any([
                "[" in claim and "]" in claim,
                "(" in claim and ")" in claim,
                "source:" in claim_lower,
                "according to" in claim_lower,
                "study" in claim_lower,
                "research" in claim_lower
            ])
            
            if not has_citation:
                uncited_claims.append(claim)
        
        if uncited_claims:
            violations.append({
                "type": "missing_citations",
                "severity": "medium",
                "message": f"{len(uncited_claims)} claims lack proper citations",
                "details": {"uncited_claims": uncited_claims[:3]}  # Show first 3
            })
            
            recommendations.append("Add citations for major claims and statistics")
            recommendations.append("Link claims to specific sources in the reference list")
        
        # Check source-to-content ratio
        source_count = len(sources)
        content_length = len(content.split())
        
        if source_count > 0:
            words_per_source = content_length / source_count
            if words_per_source > 200:  # More than 200 words per source
                recommendations.append("Consider adding more sources for comprehensive coverage")
        
        citation_score = 1.0 - (len(uncited_claims) / max(1, len(claims)))
        
        return {
            "citation_score": citation_score,
            "violations": violations,
            "recommendations": recommendations,
            "metadata": {
                "total_claims": len(claims),
                "uncited_claims": len(uncited_claims),
                "sources_count": source_count,
                "words_per_source": content_length / max(1, source_count)
            }
        }
    
    async def facts_first_validation(
        self,
        content: str,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Perform 'facts first' validation pass."""
        
        # Extract factual claims
        factual_patterns = [
            r"\d+%",  # Percentages
            r"\$\d+(?:,\d{3})*(?:\.\d{2})?",  # Money amounts
            r"\d+(?:,\d{3})*\s+(?:users|customers|companies)",  # User counts
            r"(?:increased|decreased|grew|fell)\s+by\s+\d+%",  # Growth metrics
            r"\d+\s+(?:million|billion|thousand)",  # Large numbers
        ]
        
        factual_claims = []
        for pattern in factual_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            factual_claims.extend(matches)
        
        # Validate against sources
        validated_claims = 0
        for claim in factual_claims:
            # Simple validation: check if claim appears in any source
            claim_validated = any(
                str(claim).lower() in str(source.get("content", "")).lower()
                for source in sources
            )
            if claim_validated:
                validated_claims += 1
        
        validation_score = validated_claims / max(1, len(factual_claims))
        
        recommendations = []
        if validation_score < 0.8:
            recommendations.append("Verify factual claims against provided sources")
            recommendations.append("Remove or qualify unsubstantiated claims")
        
        return {
            "validation_score": validation_score,
            "total_factual_claims": len(factual_claims),
            "validated_claims": validated_claims,
            "recommendations": recommendations,
            "factual_claims_sample": factual_claims[:5]  # Show first 5
        }


# Global safety service instance
safety_service = SafetyService()
