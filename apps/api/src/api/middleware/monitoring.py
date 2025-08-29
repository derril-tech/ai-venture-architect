"""Monitoring middleware for request tracking and performance measurement."""

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from api.services.monitoring_service import monitoring_service


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware to track request metrics and performance."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and track metrics."""
        start_time = time.time()
        
        # Extract request info
        method = request.method
        path = request.url.path
        
        # Normalize endpoint for metrics (remove IDs, etc.)
        normalized_endpoint = self._normalize_endpoint(path)
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Record metrics
            monitoring_service.record_request(
                method=method,
                endpoint=normalized_endpoint,
                duration=duration,
                status_code=response.status_code
            )
            
            # Add performance headers
            response.headers["X-Response-Time"] = f"{duration:.3f}s"
            response.headers["X-Request-ID"] = request.headers.get("X-Request-ID", "unknown")
            
            return response
            
        except Exception as e:
            # Record error
            duration = time.time() - start_time
            monitoring_service.record_request(
                method=method,
                endpoint=normalized_endpoint,
                duration=duration,
                status_code=500
            )
            raise
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for metrics grouping."""
        # Remove UUIDs and numeric IDs
        import re
        
        # Replace UUIDs
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )
        
        # Replace numeric IDs
        path = re.sub(r'/\d+', '/{id}', path)
        
        # Group API versions
        path = re.sub(r'/v\d+/', '/v{version}/', path)
        
        return path


class SearchMonitoringMixin:
    """Mixin for search request monitoring."""
    
    async def monitor_search_request(self, search_type: str, func: Callable, *args, **kwargs):
        """Monitor search request performance."""
        start_time = time.time()
        success = False
        
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            raise
        finally:
            duration = time.time() - start_time
            monitoring_service.record_search_request(search_type, duration, success)


class IdeationMonitoringMixin:
    """Mixin for ideation request monitoring."""
    
    async def monitor_ideation_request(self, method: str, func: Callable, *args, **kwargs):
        """Monitor ideation request performance."""
        start_time = time.time()
        success = False
        
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            raise
        finally:
            duration = time.time() - start_time
            monitoring_service.record_idea_generation(method, duration, success)


class ExportMonitoringMixin:
    """Mixin for export request monitoring."""
    
    async def monitor_export_request(self, export_type: str, func: Callable, *args, **kwargs):
        """Monitor export request performance."""
        start_time = time.time()
        success = False
        
        try:
            result = await func(*args, **kwargs)
            success = True
            return result
        except Exception as e:
            raise
        finally:
            duration = time.time() - start_time
            monitoring_service.record_export_request(export_type, duration, success)
