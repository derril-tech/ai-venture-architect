"""Trend analysis worker for detecting patterns and kinetics."""

import numpy as np
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select, func, and_
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import HDBSCAN
from sklearn.decomposition import PCA

from workers.core.worker import BaseWorker
from workers.core.config import get_settings

logger = structlog.get_logger()
settings = get_settings()

# Database setup
engine = create_async_engine(settings.database_url)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class TrendWorker(BaseWorker):
    """Worker for trend analysis and topic modeling."""
    
    def __init__(self, nats_client):
        super().__init__(nats_client, "trends.detect")
        self.min_cluster_size = 5
        self.min_samples = 3
    
    async def process_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process trend detection request."""
        workspace_id = payload.get("workspace_id")
        time_window = payload.get("time_window", 7)  # days
        min_signals = payload.get("min_signals", 10)
        
        if not workspace_id:
            raise ValueError("Missing required field: workspace_id")
        
        logger.info(f"Starting trend analysis for workspace: {workspace_id}")
        
        try:
            # Get recent signals
            signals = await self._get_recent_signals(workspace_id, time_window)
            
            if len(signals) < min_signals:
                logger.warning(f"Insufficient signals for trend analysis: {len(signals)}")
                return {
                    "status": "insufficient_data",
                    "workspace_id": workspace_id,
                    "signal_count": len(signals),
                }
            
            # Perform topic clustering
            topics = await self._cluster_topics(signals)
            
            # Analyze trend kinetics
            trend_analysis = await self._analyze_trends(signals, topics, time_window)
            
            # Store results
            await self._store_trend_results(workspace_id, topics, trend_analysis)
            
            logger.info(f"Trend analysis completed: {len(topics)} topics identified")
            
            return {
                "status": "completed",
                "workspace_id": workspace_id,
                "signal_count": len(signals),
                "topic_count": len(topics),
                "trends": trend_analysis,
            }
            
        except Exception as e:
            logger.error(f"Trend analysis failed: {e}")
            return {
                "status": "failed",
                "workspace_id": workspace_id,
                "error": str(e),
            }
    
    async def _get_recent_signals(self, workspace_id: str, days: int) -> List[Dict[str, Any]]:
        """Get recent signals from database."""
        async with AsyncSessionLocal() as session:
            from api.models.signal import Signal
            from uuid import UUID
            
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            query = select(Signal).where(
                and_(
                    Signal.workspace_id == UUID(workspace_id),
                    Signal.created_at >= cutoff_date,
                    Signal.content.isnot(None),
                    func.length(Signal.content) > 50  # Filter out very short content
                )
            ).order_by(Signal.created_at.desc())
            
            result = await session.execute(query)
            signals = result.scalars().all()
            
            return [
                {
                    "id": str(signal.id),
                    "title": signal.title or "",
                    "content": signal.content,
                    "source": signal.source,
                    "url": signal.url,
                    "created_at": signal.created_at,
                    "published_at": signal.published_at,
                    "entities": signal.entities or {},
                    "metadata": signal.metadata or {},
                }
                for signal in signals
            ]
    
    async def _cluster_topics(self, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Cluster signals into topics using HDBSCAN."""
        if len(signals) < self.min_cluster_size:
            return []
        
        # Prepare text data
        texts = []
        for signal in signals:
            text = f"{signal['title']} {signal['content']}"
            texts.append(text)
        
        # Vectorize text
        vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=2,
            max_df=0.8
        )
        
        try:
            X = vectorizer.fit_transform(texts)
            
            # Reduce dimensionality for clustering
            if X.shape[1] > 50:
                pca = PCA(n_components=50, random_state=42)
                X_reduced = pca.fit_transform(X.toarray())
            else:
                X_reduced = X.toarray()
            
            # Cluster using HDBSCAN
            clusterer = HDBSCAN(
                min_cluster_size=self.min_cluster_size,
                min_samples=self.min_samples,
                metric='euclidean'
            )
            
            cluster_labels = clusterer.fit_predict(X_reduced)
            
            # Process clusters
            topics = []
            feature_names = vectorizer.get_feature_names_out()
            
            for cluster_id in set(cluster_labels):
                if cluster_id == -1:  # Noise cluster
                    continue
                
                # Get signals in this cluster
                cluster_signals = [
                    signals[i] for i, label in enumerate(cluster_labels) 
                    if label == cluster_id
                ]
                
                if len(cluster_signals) < self.min_cluster_size:
                    continue
                
                # Extract top terms for this cluster
                cluster_indices = [i for i, label in enumerate(cluster_labels) if label == cluster_id]
                cluster_vectors = X[cluster_indices]
                
                # Calculate mean TF-IDF for cluster
                mean_vector = np.mean(cluster_vectors.toarray(), axis=0)
                top_indices = np.argsort(mean_vector)[-10:][::-1]
                top_terms = [feature_names[i] for i in top_indices]
                
                # Generate topic summary
                topic_title = self._generate_topic_title(top_terms, cluster_signals)
                
                # Calculate topic metrics
                sources = [s['source'] for s in cluster_signals]
                source_distribution = {src: sources.count(src) for src in set(sources)}
                
                # Extract industries from entities
                industries = []
                for signal in cluster_signals:
                    industries.extend(signal.get('entities', {}).get('industries', []))
                industry_distribution = {ind: industries.count(ind) for ind in set(industries)}
                
                topics.append({
                    "id": f"topic_{cluster_id}",
                    "title": topic_title,
                    "terms": top_terms,
                    "signal_count": len(cluster_signals),
                    "signals": [s['id'] for s in cluster_signals],
                    "source_distribution": source_distribution,
                    "industry_distribution": industry_distribution,
                    "created_at": datetime.utcnow().isoformat(),
                })
            
            return topics
            
        except Exception as e:
            logger.error(f"Error in topic clustering: {e}")
            return []
    
    def _generate_topic_title(self, top_terms: List[str], signals: List[Dict[str, Any]]) -> str:
        """Generate a descriptive title for a topic."""
        # Use the most frequent terms
        if len(top_terms) >= 2:
            return f"{top_terms[0].title()} & {top_terms[1].title()}"
        elif len(top_terms) == 1:
            return top_terms[0].title()
        else:
            return "Emerging Topic"
    
    async def _analyze_trends(
        self, 
        signals: List[Dict[str, Any]], 
        topics: List[Dict[str, Any]], 
        time_window: int
    ) -> Dict[str, Any]:
        """Analyze trend kinetics and patterns."""
        trend_analysis = {
            "overall_volume": self._calculate_volume_trend(signals, time_window),
            "source_trends": self._analyze_source_trends(signals, time_window),
            "topic_trends": self._analyze_topic_trends(topics, signals, time_window),
            "emerging_patterns": self._detect_emerging_patterns(signals, time_window),
        }
        
        return trend_analysis
    
    def _calculate_volume_trend(self, signals: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
        """Calculate overall signal volume trend."""
        # Group signals by day
        daily_counts = defaultdict(int)
        
        for signal in signals:
            date = signal['created_at'].date()
            daily_counts[date] += 1
        
        # Calculate trend metrics
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[date] for date in dates]
        
        if len(counts) < 2:
            return {"trend": "insufficient_data", "slope": 0, "acceleration": 0}
        
        # Simple linear trend
        x = np.arange(len(counts))
        slope = np.polyfit(x, counts, 1)[0]
        
        # Acceleration (second derivative approximation)
        if len(counts) >= 3:
            acceleration = np.mean(np.diff(counts, n=2))
        else:
            acceleration = 0
        
        trend_direction = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
        
        return {
            "trend": trend_direction,
            "slope": float(slope),
            "acceleration": float(acceleration),
            "daily_average": np.mean(counts),
            "peak_day": str(dates[np.argmax(counts)]) if counts else None,
        }
    
    def _analyze_source_trends(self, signals: List[Dict[str, Any]], days: int) -> Dict[str, Any]:
        """Analyze trends by source."""
        source_trends = {}
        
        # Group by source
        by_source = defaultdict(list)
        for signal in signals:
            by_source[signal['source']].append(signal)
        
        for source, source_signals in by_source.items():
            if len(source_signals) < 3:
                continue
            
            # Calculate daily counts for this source
            daily_counts = defaultdict(int)
            for signal in source_signals:
                date = signal['created_at'].date()
                daily_counts[date] += 1
            
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[date] for date in dates]
            
            if len(counts) >= 2:
                x = np.arange(len(counts))
                slope = np.polyfit(x, counts, 1)[0]
                trend = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
            else:
                slope = 0
                trend = "stable"
            
            source_trends[source] = {
                "signal_count": len(source_signals),
                "trend": trend,
                "slope": float(slope),
                "daily_average": np.mean(counts),
            }
        
        return source_trends
    
    def _analyze_topic_trends(
        self, 
        topics: List[Dict[str, Any]], 
        signals: List[Dict[str, Any]], 
        days: int
    ) -> Dict[str, Any]:
        """Analyze trends for each topic."""
        topic_trends = {}
        
        # Create signal lookup
        signal_lookup = {s['id']: s for s in signals}
        
        for topic in topics:
            topic_signals = [
                signal_lookup[sid] for sid in topic['signals'] 
                if sid in signal_lookup
            ]
            
            if len(topic_signals) < 3:
                continue
            
            # Calculate daily counts for this topic
            daily_counts = defaultdict(int)
            for signal in topic_signals:
                date = signal['created_at'].date()
                daily_counts[date] += 1
            
            dates = sorted(daily_counts.keys())
            counts = [daily_counts[date] for date in dates]
            
            if len(counts) >= 2:
                x = np.arange(len(counts))
                slope = np.polyfit(x, counts, 1)[0]
                trend = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
            else:
                slope = 0
                trend = "stable"
            
            topic_trends[topic['id']] = {
                "title": topic['title'],
                "signal_count": len(topic_signals),
                "trend": trend,
                "slope": float(slope),
                "momentum": "high" if abs(slope) > 1 else "medium" if abs(slope) > 0.5 else "low",
            }
        
        return topic_trends
    
    def _detect_emerging_patterns(self, signals: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
        """Detect emerging patterns and anomalies."""
        patterns = []
        
        # Look for sudden spikes in activity
        daily_counts = defaultdict(int)
        for signal in signals:
            date = signal['created_at'].date()
            daily_counts[date] += 1
        
        if len(daily_counts) < 3:
            return patterns
        
        dates = sorted(daily_counts.keys())
        counts = [daily_counts[date] for date in dates]
        
        # Detect spikes (values > 2 standard deviations above mean)
        mean_count = np.mean(counts)
        std_count = np.std(counts)
        threshold = mean_count + 2 * std_count
        
        for i, (date, count) in enumerate(zip(dates, counts)):
            if count > threshold and count > mean_count * 1.5:
                patterns.append({
                    "type": "spike",
                    "date": str(date),
                    "value": count,
                    "baseline": mean_count,
                    "significance": (count - mean_count) / std_count if std_count > 0 else 0,
                })
        
        return patterns
    
    async def _store_trend_results(
        self, 
        workspace_id: str, 
        topics: List[Dict[str, Any]], 
        trend_analysis: Dict[str, Any]
    ):
        """Store trend analysis results."""
        # In a full implementation, you would store these in dedicated tables
        # For now, we'll log the results
        logger.info(
            "Trend analysis results",
            workspace_id=workspace_id,
            topic_count=len(topics),
            overall_trend=trend_analysis.get("overall_volume", {}).get("trend"),
            emerging_patterns=len(trend_analysis.get("emerging_patterns", [])),
        )
