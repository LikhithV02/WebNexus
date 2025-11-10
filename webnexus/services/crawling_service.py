"""
Crawling Service

Main orchestrator for web crawling operations in WebNexus.
Implements multi-strategy web crawling with SQLite + FAISS architecture.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from urllib.parse import urlparse

import httpx
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, CacheMode

from ..config.settings import settings
from ..config.database import db_config
from ..models.database import Document, CrawlSession
from ..services.storage_service import storage_service
from ..services.url_handler import url_handler

logger = logging.getLogger(__name__)


class CrawlingService:
    """
    Main crawling service that orchestrates web crawling operations.
    
    Supports multiple crawling strategies:
    - Single page crawling
    - Batch crawling
    - Recursive crawling  
    - Sitemap crawling
    """
    
    def __init__(self):
        """Initialize crawling service."""
        self.crawler = None
        self.active_sessions: Dict[str, CrawlSession] = {}
        
        # Crawling configuration
        self.max_concurrent = settings.max_concurrent_crawls
        self.default_timeout = settings.crawl_timeout
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
    
    async def _ensure_crawler(self):
        """Ensure crawler is initialized."""
        if self.crawler is None:
            try:
                self.crawler = AsyncWebCrawler(verbose=False)
                await self.crawler.start()
                logger.info("AsyncWebCrawler initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize crawler: {e}")
                raise
    
    async def _cleanup_crawler(self):
        """Clean up crawler resources."""
        if self.crawler:
            try:
                await self.crawler.aclose()
                self.crawler = None
                logger.info("AsyncWebCrawler closed successfully")
            except Exception as e:
                logger.warning(f"Error closing crawler: {e}")
    
    def _create_crawl_session(
        self, 
        start_url: str, 
        crawl_type: str,
        max_depth: int = 1,
        max_pages: Optional[int] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> CrawlSession:
        """
        Create a new crawl session.
        
        Args:
            start_url: Starting URL for crawl
            crawl_type: Type of crawl (single, batch, recursive, sitemap)
            max_depth: Maximum depth for recursive crawls
            max_pages: Maximum pages to crawl
            config: Additional configuration
            
        Returns:
            CrawlSession object
        """
        session_id = str(uuid.uuid4())
        
        db_session = db_config.get_session()
        try:
            crawl_session = CrawlSession(
                session_id=session_id,
                start_url=start_url,
                crawl_type=crawl_type,
                max_depth=max_depth,
                max_pages=max_pages,
                status="started",
                config=config or {},
                started_at=datetime.utcnow()
            )
            
            db_session.add(crawl_session)
            db_session.commit()
            db_session.refresh(crawl_session)
            
            self.active_sessions[session_id] = crawl_session
            logger.info(f"Created crawl session {session_id} for {start_url}")
            
            return crawl_session
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating crawl session: {e}")
            raise
        finally:
            db_session.close()
    
    async def crawl_single_page(
        self,
        url: str,
        index_name: str = "default",
        store_documents: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Crawl a single web page.
        
        Args:
            url: URL to crawl
            index_name: Vector index to store documents in (default: "default")
            store_documents: Whether to store crawled documents (default: True)
            progress_callback: Optional progress callback function
            
        Returns:
            Crawl results
        """
        logger.info(f"Starting single page crawl: {url}")
        
        # Create session
        session = self._create_crawl_session(url, "single_page")
        session_id = session.session_id
        
        try:
            if progress_callback:
                await progress_callback(f"Crawling {url}", 10)
            
            # Initialize crawler
            await self._ensure_crawler()
            
            if not url_handler.is_valid_url(url):
                raise ValueError(f"Invalid URL: {url}")
            
            # Crawl configuration - simplified for compatibility
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=10,
                exclude_external_links=True,
                verbose=False  # Suppress crawl4ai output
            )
            
            # Crawl the page
            result = await self.crawler.arun(url=url, config=config)
            
            if result.success and result.markdown:
                if progress_callback:
                    await progress_callback("Processing document", 50)
                
                # Store document in specified index
                document = await storage_service.store_document(
                    url=url,
                    content=result.markdown,
                    title=result.metadata.get("title", ""),
                    metadata={
                        "status_code": result.status_code,
                        "content_length": len(result.markdown),
                        "word_count": len(result.markdown.split()),
                        "crawl_timestamp": datetime.utcnow().isoformat(),
                        **result.metadata
                    },
                    crawl_type="single_page",
                    source_id=url_handler.get_domain(url),
                    index_name=index_name
                )
                
                if progress_callback:
                    await progress_callback("Crawl completed", 100)
                
                return {
                    "success": True,
                    "session_id": session_id,
                    "documents_stored": 1,
                    "document_id": document.id,
                    "url": url,
                    "title": result.metadata.get("title", "")
                }
            else:
                error_msg = result.error_message or "Failed to crawl page"
                logger.warning(f"Crawl unsuccessful for {url}: {error_msg}")
                
                return {
                    "success": False,
                    "session_id": session_id,
                    "error": error_msg,
                    "url": url
                }
                
        except Exception as e:
            logger.error(f"Error in single page crawl: {e}")
            
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "url": url
            }
        finally:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
    
    async def crawl_recursive(
        self,
        start_url: str,
        index_name: str = "default",
        max_depth: int = 2,
        max_pages: int = 50,
        store_documents: bool = True,
        progress_callback: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        Crawl website recursively starting from a URL.
        
        Args:
            start_url: Starting URL for recursive crawl
            index_name: Vector index to store documents in (default: "default")
            max_depth: Maximum depth to crawl (default: 2)
            max_pages: Maximum pages to crawl (default: 50)
            store_documents: Whether to store crawled documents (default: True)
            progress_callback: Optional progress callback function
            
        Returns:
            Crawl results with all discovered pages
        """
        logger.info(f"Starting recursive crawl: {start_url} (max_depth={max_depth}, max_pages={max_pages})")
        
        # Create session
        session = self._create_crawl_session(
            start_url,
            "recursive",
            max_depth=max_depth,
            max_pages=max_pages
        )
        session_id = session.session_id
        
        try:
            # Initialize crawler
            await self._ensure_crawler()
            
            if not url_handler.is_valid_url(start_url):
                raise ValueError(f"Invalid URL: {start_url}")
            
            # Track visited URLs and documents
            visited_urls: Set[str] = set()
            documents_stored = 0
            crawl_queue = [(start_url, 0)]  # (url, depth)
            domain = url_handler.get_domain(start_url)
            
            # Crawl configuration
            config = CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                word_count_threshold=10,
                exclude_external_links=True,
                verbose=False  # Suppress crawl4ai output
            )
            
            while crawl_queue and len(visited_urls) < max_pages:
                current_url, current_depth = crawl_queue.pop(0)
                
                # Skip if already visited or too deep
                if current_url in visited_urls or current_depth > max_depth:
                    continue
                
                visited_urls.add(current_url)
                
                if progress_callback:
                    await progress_callback(
                        f"Crawling {len(visited_urls)}/{max_pages}: {current_url}",
                        int((len(visited_urls) / max_pages) * 100)
                    )
                
                try:
                    # Crawl the page
                    result = await self.crawler.arun(url=current_url, config=config)
                    
                    if result.success and result.markdown and store_documents:
                        # Store document in specified index
                        await storage_service.store_document(
                            url=current_url,
                            content=result.markdown,
                            title=result.metadata.get("title", ""),
                            metadata={
                                "status_code": result.status_code,
                                "content_length": len(result.markdown),
                                "word_count": len(result.markdown.split()),
                                "crawl_depth": current_depth,
                                "crawl_timestamp": datetime.utcnow().isoformat(),
                                **result.metadata
                            },
                            crawl_type="recursive",
                            source_id=domain,
                            index_name=index_name
                        )
                        documents_stored += 1
                        
                        # Extract and queue internal links if not at max depth
                        if current_depth < max_depth and result.links:
                            internal_links = result.links.get("internal", [])
                            for link_data in internal_links[:10]:  # Limit links per page
                                link_url = link_data.get("href", "")
                                if link_url and url_handler.is_same_domain(link_url, start_url):
                                    normalized_url = url_handler.normalize_url(link_url)
                                    if normalized_url and normalized_url not in visited_urls:
                                        crawl_queue.append((normalized_url, current_depth + 1))
                    
                except Exception as e:
                    logger.warning(f"Error crawling {current_url}: {e}")
                    continue
            
            if progress_callback:
                await progress_callback("Recursive crawl completed", 100)
            
            return {
                "success": True,
                "session_id": session_id,
                "documents_stored": documents_stored,
                "pages_crawled": len(visited_urls),
                "start_url": start_url,
                "max_depth_reached": max_depth
            }
            
        except Exception as e:
            logger.error(f"Error in recursive crawl: {e}")
            
            return {
                "success": False,
                "session_id": session_id,
                "error": str(e),
                "start_url": start_url
            }
        finally:
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
    
    def get_session_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a crawl session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session status or None if not found
        """
        db_session = db_config.get_session()
        try:
            crawl_session = db_session.query(CrawlSession).filter(
                CrawlSession.session_id == session_id
            ).first()
            
            if crawl_session:
                return crawl_session.to_dict()
            
            return None
            
        finally:
            db_session.close()
    
    async def cleanup(self):
        """Clean up service resources."""
        await self._cleanup_crawler()
        self.active_sessions.clear()


# Global crawling service instance
crawling_service = CrawlingService()