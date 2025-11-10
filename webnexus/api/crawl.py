"""
Crawling API Endpoints

FastAPI router for web crawling operations.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl, validator

from ..services import (
    crawling_service,
    progress_tracker,
    url_handler
)

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response models
class CrawlRequest(BaseModel):
    """Request model for single page crawling."""
    url: HttpUrl
    index_name: str = "default"
    store_documents: bool = True
    
    @validator('url')
    def validate_url(cls, v):
        url_str = str(v)
        if not url_handler.is_valid_url(url_str):
            raise ValueError(f"Invalid or unsupported URL: {url_str}")
        return v
    
    @validator('index_name')
    def validate_index_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Index name cannot be empty")
        return v.strip()


class BatchCrawlRequest(BaseModel):
    """Request model for batch crawling."""
    urls: List[HttpUrl]
    index_name: str = "default"
    max_concurrent: int = 5
    store_documents: bool = True
    
    @validator('urls')
    def validate_urls(cls, v):
        if len(v) == 0:
            raise ValueError("At least one URL is required")
        if len(v) > 100:
            raise ValueError("Maximum 100 URLs allowed per batch")
        
        for url in v:
            url_str = str(url)
            if not url_handler.is_valid_url(url_str):
                raise ValueError(f"Invalid or unsupported URL: {url_str}")
        return v
    
    @validator('index_name')
    def validate_index_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Index name cannot be empty")
        return v.strip()
    
    @validator('max_concurrent')
    def validate_concurrent(cls, v):
        if v < 1 or v > 20:
            raise ValueError("max_concurrent must be between 1 and 20")
        return v


class CrawlResponse(BaseModel):
    """Response model for crawling operations."""
    success: bool
    session_id: Optional[str] = None
    message: str
    documents_stored: int = 0
    errors: List[str] = []
    metadata: Dict[str, Any] = {}


class CrawlStatus(BaseModel):
    """Model for crawl session status."""
    session_id: str
    status: str
    start_url: str
    crawl_type: str
    documents_stored: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


@router.post("/single", response_model=CrawlResponse)
async def crawl_single_page(
    request: CrawlRequest,
    background_tasks: BackgroundTasks
) -> CrawlResponse:
    """
    Crawl a single web page.
    
    This endpoint crawls a single URL and optionally stores the document
    in the vector database for later search and retrieval.
    """
    try:
        url = str(request.url)
        index_name = request.index_name
        logger.info(f"Starting single page crawl: {url} -> index '{index_name}'")
        
        # Validate index exists
        from ..services.index_manager import index_manager
        if not index_manager.get_index(index_name):
            raise HTTPException(
                status_code=404,
                detail=f"Index '{index_name}' not found. Create it first using /api/indexes/"
            )
        
        # Create progress callback
        async def progress_callback(message: str, percent: int):
            logger.info(f"Crawl progress {percent}%: {message}")
        
        # Perform crawl with index specification
        result = await crawling_service.crawl_single_page(
            url=url,
            index_name=index_name,
            progress_callback=progress_callback
        )
        
        if result["success"]:
            return CrawlResponse(
                success=True,
                session_id=result.get("session_id"),
                message=f"Successfully crawled {url}",
                documents_stored=result.get("documents_stored", 0),
                metadata={
                    "document_id": result.get("document_id"),
                    "title": result.get("title", ""),
                    "url": url
                }
            )
        else:
            return CrawlResponse(
                success=False,
                session_id=result.get("session_id"),
                message=f"Failed to crawl {url}",
                errors=[result.get("error", "Unknown error")]
            )
            
    except Exception as e:
        logger.error(f"Error in single page crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/batch", response_model=CrawlResponse)
async def crawl_batch_urls(
    request: BatchCrawlRequest,
    background_tasks: BackgroundTasks
) -> CrawlResponse:
    """
    Crawl multiple URLs in parallel.
    
    This endpoint crawls multiple URLs concurrently and stores
    all successful results in the vector database.
    """
    try:
        urls = [str(url) for url in request.urls]
        index_name = request.index_name
        logger.info(f"Starting batch crawl of {len(urls)} URLs -> index '{index_name}'")
        
        # Validate index exists
        from ..services.index_manager import index_manager
        if not index_manager.get_index(index_name):
            raise HTTPException(
                status_code=404,
                detail=f"Index '{index_name}' not found. Create it first using /api/indexes/"
            )
        
        # Create task ID for progress tracking
        task_id = f"batch_crawl_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        progress_tracker.start_task(
            task_id=task_id,
            task_type="batch_crawl",
            description=f"Crawling {len(urls)} URLs",
            total_items=len(urls)
        )
        
        # Crawl URLs with semaphore for concurrency control
        semaphore = asyncio.Semaphore(request.max_concurrent)
        results = []
        errors = []
        documents_stored = 0
        
        async def crawl_single_with_progress(url: str, index: int):
            async with semaphore:
                try:
                    result = await crawling_service.crawl_single_page(
                        url=url,
                        index_name=index_name
                    )
                    
                    # Update progress
                    progress_tracker.update_progress(
                        task_id=task_id,
                        current_item=index + 1,
                        message=f"Crawled {url}"
                    )
                    
                    return result
                except Exception as e:
                    logger.error(f"Error crawling {url}: {e}")
                    return {"success": False, "url": url, "error": str(e)}
        
        # Execute all crawls concurrently
        tasks = [crawl_single_with_progress(url, i) for i, url in enumerate(urls)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append(f"URL {urls[i]}: {str(result)}")
            elif result.get("success"):
                documents_stored += result.get("documents_stored", 0)
            else:
                errors.append(f"URL {urls[i]}: {result.get('error', 'Unknown error')}")
        
        # Complete progress tracking
        if errors:
            progress_tracker.fail_task(
                task_id=task_id,
                error_message=f"Completed with {len(errors)} errors",
                metadata={"total_errors": len(errors)}
            )
        else:
            progress_tracker.complete_task(
                task_id=task_id,
                message=f"Successfully crawled all {len(urls)} URLs",
                metadata={"documents_stored": documents_stored}
            )
        
        success = len(errors) == 0
        message = f"Crawled {len(urls)} URLs"
        if not success:
            message += f" with {len(errors)} errors"
        
        return CrawlResponse(
            success=success,
            session_id=task_id,
            message=message,
            documents_stored=documents_stored,
            errors=errors,
            metadata={
                "urls_processed": len(urls),
                "successful_crawls": documents_stored,
                "failed_crawls": len(errors)
            }
        )
        
    except Exception as e:
        logger.error(f"Error in batch crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{session_id}")
async def get_crawl_status(session_id: str) -> Dict[str, Any]:
    """
    Get the status of a crawling session.
    
    Returns the current status, progress, and metadata for a crawling session.
    """
    try:
        # Try to get from progress tracker first
        task_status = progress_tracker.get_task_status(session_id)
        if task_status:
            return {
                "session_id": session_id,
                "status": task_status["status"],
                "task_type": task_status["task_type"],
                "description": task_status["description"],
                "progress_percent": task_status["progress_percent"],
                "current_item": task_status["current_item"],
                "total_items": task_status["total_items"],
                "started_at": task_status["started_at"],
                "updated_at": task_status["updated_at"],
                "error_message": task_status.get("error_message"),
                "metadata": task_status.get("metadata", {})
            }
        
        # Try to get from crawling service
        session_status = crawling_service.get_session_status(session_id)
        if session_status:
            return session_status
        
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crawl status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/active")
async def get_active_crawls() -> Dict[str, Any]:
    """
    Get all currently active crawling sessions.
    
    Returns a list of active crawling tasks with their current progress.
    """
    try:
        active_tasks = progress_tracker.get_active_tasks()
        return {
            "active_crawls": len(active_tasks),
            "tasks": active_tasks
        }
        
    except Exception as e:
        logger.error(f"Error getting active crawls: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup")
async def cleanup_completed_tasks(
    max_age_hours: int = Query(24, ge=1, le=168, description="Maximum age in hours for completed tasks")
) -> Dict[str, Any]:
    """
    Clean up old completed/failed crawling tasks.
    
    Removes completed, failed, or cancelled tasks older than the specified age.
    """
    try:
        progress_tracker.cleanup_completed_tasks(max_age_hours)
        return {
            "success": True,
            "message": f"Cleaned up tasks older than {max_age_hours} hours"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel/{session_id}")
async def cancel_crawl(session_id: str) -> Dict[str, Any]:
    """
    Cancel an active crawling session.
    
    Attempts to cancel a running crawling task.
    """
    try:
        task_status = progress_tracker.get_task_status(session_id)
        if not task_status:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        if task_status["status"] != "running":
            return {
                "success": False,
                "message": f"Task {session_id} is not running (status: {task_status['status']})"
            }
        
        progress_tracker.cancel_task(session_id, "Cancelled by user request")
        
        return {
            "success": True,
            "message": f"Cancelled crawling session {session_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling crawl: {e}")
        raise HTTPException(status_code=500, detail=str(e))