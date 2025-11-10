"""
WebNexus FastAPI Application

Main FastAPI application for WebNexus web crawler and RAG system.
Provides REST API endpoints for crawling and search operations.
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config.settings import settings
from ..config.database import db_config
from ..services import (
    embedding_service,
    vector_service, 
    search_service,
    crawling_service,
    storage_service,
    progress_tracker
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager for startup/shutdown operations.
    """
    # Startup
    logger.info("Starting WebNexus API server...")
    
    try:
        # Initialize database
        db_config.initialize()
        logger.info("Database initialized")
        
        # Initialize services
        embedding_service._load_model()
        vector_service._initialize_index()
        logger.info("Services initialized")
        
        # Yield control to the application
        yield
        
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown
        logger.info("Shutting down WebNexus API server...")
        
        try:
            # Cleanup services
            vector_service.save_index()
            logger.info("Services cleaned up successfully")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# Create FastAPI application
app = FastAPI(
    title="WebNexus",
    description="WebNexus Web Crawler & RAG System API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint with basic API information."""
    return {
        "name": "WebNexus API",
        "version": "1.0.0",
        "description": "Web Crawler & RAG System",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        db_config.get_session().close()
        
        # Check service status
        stats = await search_service.get_document_stats()
        
        return {
            "status": "healthy",
            "timestamp": progress_tracker.active_tasks.__len__(),
            "database": "connected",
            "services": "operational",
            "stats": stats
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")


@app.get("/api/stats")
async def get_system_stats() -> Dict[str, Any]:
    """Get comprehensive system statistics."""
    try:
        # Get search service stats
        search_stats = await search_service.get_document_stats()
        
        # Get storage stats
        storage_stats = storage_service.get_storage_stats()
        
        # Get active task count
        active_tasks = len(progress_tracker.get_active_tasks())
        
        return {
            "system": {
                "embedding_model": settings.embedding_model,
                "chunking_strategy": settings.chunking_strategy,
                "max_concurrent_crawls": settings.max_concurrent_crawls,
                "active_tasks": active_tasks
            },
            "search": search_stats,
            "storage": storage_stats,
            "database": {
                "engine": "SQLite",
                "vector_store": "FAISS"
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to get system stats")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)}
    )


# Import and include routers
from .crawl import router as crawl_router
from .search import router as search_router
from .indexes import router as indexes_router

app.include_router(crawl_router)
app.include_router(search_router)
app.include_router(indexes_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0", 
        port=8000,
        reload=True,
        log_level="info"
    )