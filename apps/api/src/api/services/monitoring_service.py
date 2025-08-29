"""Monitoring and SLO tracking service."""

import time
import asyncio
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass, field
import statistics

import structlog
from prometheus_client import Counter, Histogram, Gauge, Summary
import psutil

logger = structlog.get_logger()


@dataclass
class SLOTarget:
    """SLO target definition."""
    name: str
    description: str
    target_value: float
    unit: str
    measurement_window_minutes: int = 60
    alert_threshold: float = 0.9  # Alert when SLO is at 90% of target


@dataclass
class PerformanceMetrics:
    """Performance metrics snapshot."""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    active_connections: int
    response_times: Dict[str, float]
    error_rates: Dict[str, float]
    throughput: Dict[str, float]


@dataclass
class SLOStatus:
    """SLO status and compliance."""
    name: str
    current_value: float
    target_value: float
    compliance_percentage: float
    status: str  # "healthy", "warning", "critical"
    last_updated: datetime
    trend: str  # "improving", "stable", "degrading"
    violations: List[Dict[str, Any]] = field(default_factory=list)


class MonitoringService:
    """Service for performance monitoring and SLO tracking."""
    
    def __init__(self):
        # Prometheus metrics
        self.request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint', 'status_code']
        )
        
        self.request_count = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status_code']
        )
        
        self.search_duration = Histogram(
            'search_duration_seconds',
            'Search request duration in seconds',
            ['search_type']
        )
        
        self.idea_generation_duration = Histogram(
            'idea_generation_duration_seconds',
            'Idea generation duration in seconds',
            ['method']
        )
        
        self.export_duration = Histogram(
            'export_duration_seconds',
            'Export generation duration in seconds',
            ['export_type']
        )
        
        self.active_users = Gauge(
            'active_users_total',
            'Number of active users'
        )
        
        self.data_freshness = Gauge(
            'data_freshness_hours',
            'Age of most recent data in hours',
            ['source']
        )
        
        self.error_rate = Gauge(
            'error_rate_percentage',
            'Error rate percentage',
            ['service']
        )
        
        # SLO definitions
        self.slo_targets = {
            "search_p95": SLOTarget(
                name="search_p95",
                description="Search API 95th percentile response time",
                target_value=1.2,  # seconds
                unit="seconds",
                measurement_window_minutes=60
            ),
            "idea_generation_p95": SLOTarget(
                name="idea_generation_p95", 
                description="Idea generation 95th percentile time",
                target_value=60.0,  # seconds
                unit="seconds",
                measurement_window_minutes=60
            ),
            "export_p95": SLOTarget(
                name="export_p95",
                description="Export generation 95th percentile time",
                target_value=10.0,  # seconds
                unit="seconds",
                measurement_window_minutes=60
            ),
            "data_freshness": SLOTarget(
                name="data_freshness",
                description="Maximum data age across all sources",
                target_value=24.0,  # hours
                unit="hours",
                measurement_window_minutes=1440  # 24 hours
            ),
            "api_availability": SLOTarget(
                name="api_availability",
                description="API availability percentage",
                target_value=99.9,  # percent
                unit="percent",
                measurement_window_minutes=60
            ),
            "error_rate": SLOTarget(
                name="error_rate",
                description="Overall error rate",
                target_value=1.0,  # percent
                unit="percent",
                measurement_window_minutes=60
            )
        }
        
        # Performance tracking
        self.performance_history = deque(maxlen=1440)  # 24 hours of minute-by-minute data
        self.response_times = defaultdict(lambda: deque(maxlen=1000))
        self.error_counts = defaultdict(int)
        self.request_counts = defaultdict(int)
        
        # SLO tracking
        self.slo_measurements = defaultdict(lambda: deque(maxlen=1440))
        self.slo_violations = defaultdict(list)
        
        # Background monitoring task
        self.monitoring_task = None
        self.is_monitoring = False
    
    async def start_monitoring(self):
        """Start background monitoring."""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Performance monitoring started")
    
    async def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Performance monitoring stopped")
    
    async def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.is_monitoring:
            try:
                # Collect performance metrics
                metrics = await self._collect_performance_metrics()
                self.performance_history.append(metrics)
                
                # Update SLO measurements
                await self._update_slo_measurements()
                
                # Check for SLO violations
                await self._check_slo_violations()
                
                # Sleep for 1 minute
                await asyncio.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _collect_performance_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics."""
        # System metrics
        cpu_usage = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        
        # Application metrics
        response_times = {}
        error_rates = {}
        throughput = {}
        
        # Calculate response time percentiles
        for endpoint, times in self.response_times.items():
            if times:
                response_times[f"{endpoint}_p50"] = statistics.median(times)
                response_times[f"{endpoint}_p95"] = statistics.quantiles(times, n=20)[18] if len(times) > 20 else max(times)
                response_times[f"{endpoint}_p99"] = statistics.quantiles(times, n=100)[98] if len(times) > 100 else max(times)
        
        # Calculate error rates
        for service in ["api", "search", "ideation", "export"]:
            total_requests = self.request_counts.get(service, 0)
            error_count = self.error_counts.get(service, 0)
            error_rates[service] = (error_count / max(1, total_requests)) * 100
        
        # Calculate throughput (requests per minute)
        for service, count in self.request_counts.items():
            throughput[service] = count  # This is already per-minute in our tracking
        
        return PerformanceMetrics(
            timestamp=datetime.utcnow(),
            cpu_usage=cpu_usage,
            memory_usage=memory.percent,
            disk_usage=disk.percent,
            network_io={
                "bytes_sent": network.bytes_sent,
                "bytes_recv": network.bytes_recv,
                "packets_sent": network.packets_sent,
                "packets_recv": network.packets_recv
            },
            active_connections=len(self.response_times),  # Approximation
            response_times=response_times,
            error_rates=error_rates,
            throughput=throughput
        )
    
    async def _update_slo_measurements(self):
        """Update SLO measurements."""
        current_time = datetime.utcnow()
        
        # Search P95
        search_times = list(self.response_times.get("search", []))
        if search_times:
            p95 = statistics.quantiles(search_times, n=20)[18] if len(search_times) > 20 else max(search_times)
            self.slo_measurements["search_p95"].append((current_time, p95))
        
        # Idea generation P95
        idea_times = list(self.response_times.get("idea_generation", []))
        if idea_times:
            p95 = statistics.quantiles(idea_times, n=20)[18] if len(idea_times) > 20 else max(idea_times)
            self.slo_measurements["idea_generation_p95"].append((current_time, p95))
        
        # Export P95
        export_times = list(self.response_times.get("export", []))
        if export_times:
            p95 = statistics.quantiles(export_times, n=20)[18] if len(export_times) > 20 else max(export_times)
            self.slo_measurements["export_p95"].append((current_time, p95))
        
        # API availability (based on error rate)
        total_requests = sum(self.request_counts.values())
        total_errors = sum(self.error_counts.values())
        if total_requests > 0:
            availability = ((total_requests - total_errors) / total_requests) * 100
            self.slo_measurements["api_availability"].append((current_time, availability))
        
        # Overall error rate
        if total_requests > 0:
            error_rate = (total_errors / total_requests) * 100
            self.slo_measurements["error_rate"].append((current_time, error_rate))
    
    async def _check_slo_violations(self):
        """Check for SLO violations and trigger alerts."""
        current_time = datetime.utcnow()
        
        for slo_name, target in self.slo_targets.items():
            measurements = self.slo_measurements[slo_name]
            if not measurements:
                continue
            
            # Get measurements within the window
            window_start = current_time - timedelta(minutes=target.measurement_window_minutes)
            recent_measurements = [
                (timestamp, value) for timestamp, value in measurements
                if timestamp >= window_start
            ]
            
            if not recent_measurements:
                continue
            
            # Calculate current value
            values = [value for _, value in recent_measurements]
            current_value = statistics.mean(values)
            
            # Check for violation
            is_violation = False
            if slo_name in ["search_p95", "idea_generation_p95", "export_p95", "data_freshness"]:
                # Lower is better
                is_violation = current_value > target.target_value
            elif slo_name in ["api_availability"]:
                # Higher is better
                is_violation = current_value < target.target_value
            elif slo_name in ["error_rate"]:
                # Lower is better
                is_violation = current_value > target.target_value
            
            if is_violation:
                violation = {
                    "timestamp": current_time.isoformat(),
                    "slo_name": slo_name,
                    "current_value": current_value,
                    "target_value": target.target_value,
                    "severity": "critical" if current_value > target.target_value * 1.5 else "warning"
                }
                
                self.slo_violations[slo_name].append(violation)
                
                # Trigger alert
                await self._trigger_slo_alert(violation)
    
    async def _trigger_slo_alert(self, violation: Dict[str, Any]):
        """Trigger SLO violation alert."""
        logger.warning(
            "SLO violation detected",
            slo_name=violation["slo_name"],
            current_value=violation["current_value"],
            target_value=violation["target_value"],
            severity=violation["severity"]
        )
        
        # In production, this would integrate with alerting systems
        # like PagerDuty, Slack, email, etc.
    
    def record_request(self, method: str, endpoint: str, duration: float, status_code: int):
        """Record HTTP request metrics."""
        # Update Prometheus metrics
        self.request_duration.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).observe(duration)
        
        self.request_count.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).inc()
        
        # Update internal tracking
        self.response_times[endpoint].append(duration)
        self.request_counts["api"] += 1
        
        if status_code >= 400:
            self.error_counts["api"] += 1
    
    def record_search_request(self, search_type: str, duration: float, success: bool):
        """Record search request metrics."""
        self.search_duration.labels(search_type=search_type).observe(duration)
        self.response_times["search"].append(duration)
        self.request_counts["search"] += 1
        
        if not success:
            self.error_counts["search"] += 1
    
    def record_idea_generation(self, method: str, duration: float, success: bool):
        """Record idea generation metrics."""
        self.idea_generation_duration.labels(method=method).observe(duration)
        self.response_times["idea_generation"].append(duration)
        self.request_counts["ideation"] += 1
        
        if not success:
            self.error_counts["ideation"] += 1
    
    def record_export_request(self, export_type: str, duration: float, success: bool):
        """Record export request metrics."""
        self.export_duration.labels(export_type=export_type).observe(duration)
        self.response_times["export"].append(duration)
        self.request_counts["export"] += 1
        
        if not success:
            self.error_counts["export"] += 1
    
    def update_data_freshness(self, source: str, hours_old: float):
        """Update data freshness metric."""
        self.data_freshness.labels(source=source).set(hours_old)
        self.slo_measurements["data_freshness"].append((datetime.utcnow(), hours_old))
    
    def update_active_users(self, count: int):
        """Update active users count."""
        self.active_users.set(count)
    
    async def get_slo_status(self) -> List[SLOStatus]:
        """Get current SLO status for all targets."""
        current_time = datetime.utcnow()
        statuses = []
        
        for slo_name, target in self.slo_targets.items():
            measurements = self.slo_measurements[slo_name]
            
            if not measurements:
                status = SLOStatus(
                    name=slo_name,
                    current_value=0.0,
                    target_value=target.target_value,
                    compliance_percentage=0.0,
                    status="unknown",
                    last_updated=current_time,
                    trend="stable",
                    violations=[]
                )
                statuses.append(status)
                continue
            
            # Get recent measurements
            window_start = current_time - timedelta(minutes=target.measurement_window_minutes)
            recent_measurements = [
                (timestamp, value) for timestamp, value in measurements
                if timestamp >= window_start
            ]
            
            if not recent_measurements:
                continue
            
            values = [value for _, value in recent_measurements]
            current_value = statistics.mean(values)
            
            # Calculate compliance
            if slo_name in ["search_p95", "idea_generation_p95", "export_p95", "data_freshness", "error_rate"]:
                # Lower is better
                compliance = min(100.0, (target.target_value / max(current_value, 0.001)) * 100)
            else:
                # Higher is better (availability)
                compliance = min(100.0, (current_value / target.target_value) * 100)
            
            # Determine status
            if compliance >= 95:
                status_level = "healthy"
            elif compliance >= 90:
                status_level = "warning"
            else:
                status_level = "critical"
            
            # Calculate trend
            if len(values) >= 10:
                recent_avg = statistics.mean(values[-5:])
                older_avg = statistics.mean(values[-10:-5])
                
                if recent_avg < older_avg * 0.95:
                    trend = "improving"
                elif recent_avg > older_avg * 1.05:
                    trend = "degrading"
                else:
                    trend = "stable"
            else:
                trend = "stable"
            
            # Get recent violations
            recent_violations = [
                v for v in self.slo_violations[slo_name]
                if datetime.fromisoformat(v["timestamp"]) >= window_start
            ]
            
            status = SLOStatus(
                name=slo_name,
                current_value=current_value,
                target_value=target.target_value,
                compliance_percentage=compliance,
                status=status_level,
                last_updated=current_time,
                trend=trend,
                violations=recent_violations
            )
            
            statuses.append(status)
        
        return statuses
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary."""
        if not self.performance_history:
            return {"status": "no_data"}
        
        latest = self.performance_history[-1]
        
        # Calculate averages over last hour
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        recent_metrics = [m for m in self.performance_history if m.timestamp >= hour_ago]
        
        if recent_metrics:
            avg_cpu = statistics.mean([m.cpu_usage for m in recent_metrics])
            avg_memory = statistics.mean([m.memory_usage for m in recent_metrics])
            avg_disk = statistics.mean([m.disk_usage for m in recent_metrics])
        else:
            avg_cpu = latest.cpu_usage
            avg_memory = latest.memory_usage
            avg_disk = latest.disk_usage
        
        return {
            "timestamp": latest.timestamp.isoformat(),
            "system": {
                "cpu_usage": latest.cpu_usage,
                "memory_usage": latest.memory_usage,
                "disk_usage": latest.disk_usage,
                "avg_cpu_1h": avg_cpu,
                "avg_memory_1h": avg_memory,
                "avg_disk_1h": avg_disk
            },
            "application": {
                "response_times": latest.response_times,
                "error_rates": latest.error_rates,
                "throughput": latest.throughput,
                "active_connections": latest.active_connections
            },
            "network": latest.network_io
        }
    
    async def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check."""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {}
        }
        
        # System health
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            health_status["checks"]["system"] = {
                "status": "healthy" if cpu_usage < 80 and memory.percent < 85 and disk.percent < 90 else "warning",
                "cpu_usage": cpu_usage,
                "memory_usage": memory.percent,
                "disk_usage": disk.percent
            }
            
            if health_status["checks"]["system"]["status"] == "warning":
                health_status["status"] = "warning"
                
        except Exception as e:
            health_status["checks"]["system"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        # SLO health
        try:
            slo_statuses = await self.get_slo_status()
            critical_slos = [s for s in slo_statuses if s.status == "critical"]
            warning_slos = [s for s in slo_statuses if s.status == "warning"]
            
            health_status["checks"]["slos"] = {
                "status": "critical" if critical_slos else "warning" if warning_slos else "healthy",
                "critical_count": len(critical_slos),
                "warning_count": len(warning_slos),
                "total_count": len(slo_statuses)
            }
            
            if critical_slos:
                health_status["status"] = "unhealthy"
            elif warning_slos and health_status["status"] == "healthy":
                health_status["status"] = "warning"
                
        except Exception as e:
            health_status["checks"]["slos"] = {
                "status": "error",
                "error": str(e)
            }
            health_status["status"] = "unhealthy"
        
        return health_status


# Global monitoring service instance
monitoring_service = MonitoringService()
