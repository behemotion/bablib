"""FastAPI application for Bablib unified project API."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .projects import router as projects_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Bablib API server")
    yield
    # Shutdown
    logger.info("Shutting down Bablib API server")


app = FastAPI(
    title="Bablib API",
    description="Unified API for Bablib project management with compatibility tracking",
    version="3.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(projects_router, prefix="/api", tags=["projects"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "3.0.0"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Bablib API v3.0.0",
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/health"
    }