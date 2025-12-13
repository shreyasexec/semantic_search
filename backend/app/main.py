"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.websocket import websocket_router
from app.dependencies import init_services, cleanup_services
from app.ingestion.scheduler import get_scheduler
from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting Smart City Semantic Search API")

    # Initialize services
    await init_services()

    # Start ingestion scheduler
    scheduler = get_scheduler()
    await scheduler.start()

    yield

    # Shutdown
    logger.info("Shutting down Smart City Semantic Search API")

    # Stop scheduler
    scheduler.stop()

    # Cleanup services
    await cleanup_services()


# Create FastAPI application
app = FastAPI(
    title="Smart City Semantic Search API",
    description="Schema-agnostic semantic search for Smart City / Safe City platforms",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router)
app.include_router(websocket_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Smart City Semantic Search API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.app.debug,
        log_level=settings.app.log_level.lower(),
    )
