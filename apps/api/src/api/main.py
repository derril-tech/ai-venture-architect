"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

from api.core.config import get_settings
from api.core.database import init_db
from api.core.exceptions import APIException
from api.routes import health, auth, signals, ideas, exports, search

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    logger.info("Starting AI Venture Architect API")
    
    # Initialize database
    await init_db()
    
    yield
    
    logger.info("Shutting down AI Venture Architect API")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title="AI Venture Architect API",
        description="Multi-agent market research & AI product ideation platform",
        version="0.1.0",
        openapi_url="/v1/openapi.json" if settings.environment != "production" else None,
        docs_url="/v1/docs" if settings.environment != "production" else None,
        redoc_url="/v1/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Exception handler
    @app.exception_handler(APIException)
    async def api_exception_handler(request: Request, exc: APIException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": exc.error_type,
                "title": exc.title,
                "detail": exc.detail,
                "instance": str(request.url),
            },
        )
    
    # Request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        logger.info(
            "Request processed",
            method=request.method,
            url=str(request.url),
            status_code=response.status_code,
            process_time=process_time,
        )
        return response
    
    # Metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
    
    # Include routers
    app.include_router(health.router, prefix="/v1")
    app.include_router(auth.router, prefix="/v1/auth", tags=["auth"])
    app.include_router(signals.router, prefix="/v1/signals", tags=["signals"])
    app.include_router(ideas.router, prefix="/v1/ideas", tags=["ideas"])
    app.include_router(exports.router, prefix="/v1/exports", tags=["exports"])
    app.include_router(search.router, prefix="/v1", tags=["search"])
    
    # OpenTelemetry instrumentation
    FastAPIInstrumentor.instrument_app(app)
    
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    import time
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_config=None,  # Use structlog instead
    )
