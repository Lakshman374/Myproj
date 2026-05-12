"""FastAPI application factory for HIPS."""

import os
from typing import Optional, Callable
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from hips_service.api.routes import (
    alerts,
    logs,
    rules,
    metrics,
    system,
    websocket,
    monitoring,
    settings,
    reports,
)

logger = logging.getLogger(__name__)


def create_app(lifespan: Optional[Callable] = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        lifespan: Optional async context manager for startup/shutdown logic.

    Returns:
        Configured FastAPI instance.
    """
    _app = FastAPI(
        title="CHIPS API",
        description="CHIPS - Intrusion Prevention System for FSKTM Data Centre",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Configure CORS — set HIPS_CORS_ORIGINS env var (comma-separated) for production
    _default_origins = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173"
    _cors_origins = [o.strip() for o in os.getenv('HIPS_CORS_ORIGINS', _default_origins).split(',') if o.strip()]
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    _app.include_router(alerts.router, prefix="/api/v1/alerts", tags=["alerts"])
    _app.include_router(logs.router, prefix="/api/v1/logs", tags=["logs"])
    _app.include_router(rules.router, prefix="/api/v1/rules", tags=["rules"])
    _app.include_router(metrics.router, prefix="/api/v1/metrics", tags=["metrics"])
    _app.include_router(reports.router, prefix="/api/v1/reports", tags=["reports"])
    _app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
    _app.include_router(monitoring.router, prefix="/api/v1/monitoring", tags=["monitoring"])
    _app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
    _app.include_router(websocket.router, prefix="/ws", tags=["websocket"])

    @_app.get("/")
    async def root():
        """Root endpoint."""
        return {"name": "CHIPS API", "version": "1.0.0", "status": "running"}

    @_app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return _app


# Default app instance — used when the module is imported without a lifespan
app = create_app()
