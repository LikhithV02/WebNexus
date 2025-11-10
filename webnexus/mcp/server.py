"""
WebNexus MCP Server

Model Context Protocol server providing web crawling and RAG tools for AI agents.
Implements crawl_website, search_documents, and get_sources tools.
"""

import asyncio
import logging
import os
import sys
from contextlib import contextmanager
from datetime import datetime
from typing import Dict, List, Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
from mcp import types

# Handle both relative and absolute imports for flexibility
try:
    # Try relative imports first (when run as module)
    from ..services import (
        crawling_service,
        search_service,
        storage_service,
        progress_tracker
    )
    from ..config.database import db_config
    from ..config.settings import settings
except ImportError:
    # Fallback to absolute imports (when run as script)
    import sys
    from pathlib import Path
    
    # Add project root to Python path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    from webnexus.services import (
        crawling_service,
        search_service,
        storage_service,
        progress_tracker
    )
    from webnexus.config.database import db_config
    from webnexus.config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create MCP server
mcp = FastMCP("WebNexus")


@contextmanager
def suppress_stdout():
    """
    Context manager to suppress all stdout output.
    Critical for MCP protocol which requires clean JSON-RPC on stdout.
    """
    with open(os.devnull, 'w') as devnull:
        old_stdout = sys.stdout
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


def serialize_value(value: Any) -> Any:
    """
    Convert complex types to JSON-serializable values.
    Handles datetime, SQLAlchemy models, and other non-serializable types.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    if hasattr(value, '__dict__'):
        # Handle SQLAlchemy models and other objects
        return {k: serialize_value(v) for k, v in value.__dict__.items()
                if not k.startswith('_')}
    # Fallback to string representation
    return str(value)


@mcp.tool()
async def crawl_website(
    url: str,
    index_name: str = "default",
    max_depth: int = 2,
    max_pages: int = 50,
    strategy: str = "recursive",
    store_documents: bool = True
) -> Dict[str, Any]:
    """
    Crawl a website and optionally store documents for later search.

    Args:
        url: The URL to crawl (required)
        index_name: Vector index to store documents in (default: "default")
        max_depth: Maximum crawl depth for recursive strategy (default: 2)
        max_pages: Maximum number of pages to crawl (default: 50)
        strategy: Crawling strategy - "single_page", "batch", "recursive", or "sitemap" (default: "recursive")
        store_documents: Whether to store crawled documents for search (default: True)

    Returns:
        Dictionary with crawl results and statistics
    """
    try:
        logger.info(f"MCP crawl_website: url={url}, index={index_name}, strategy={strategy}, max_depth={max_depth}")
        
        # Validate index exists
        try:
            from ..services.index_manager import index_manager
        except ImportError:
            from webnexus.services.index_manager import index_manager
        
        if not index_manager.get_index(index_name):
            return {
                "success": False,
                "error": f"Index '{index_name}' not found. Use list_indexes or create_index first."
            }
        
        # Validate strategy
        valid_strategies = ["single_page", "batch", "recursive", "sitemap"]
        if strategy not in valid_strategies:
            return {
                "success": False,
                "error": f"Invalid strategy '{strategy}'. Must be one of: {', '.join(valid_strategies)}"
            }
        
        # Generate session ID for tracking
        session_id = f"mcp_crawl_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Wrap ALL crawling operations in suppress_stdout to prevent output pollution
        with suppress_stdout():
            if strategy == "single_page":
                # Single page crawl
                result = await crawling_service.crawl_single_page(url, index_name=index_name)
                crawl_result = {
                    "success": True,
                    "documents_stored": 1 if store_documents else 0,
                    "pages_crawled": 1,
                    "errors": []
                }

            elif strategy in ["batch", "recursive", "sitemap"]:
                # For now, all other strategies fall back to single page
                # This is a simplified implementation until full strategies are available
                result = await crawling_service.crawl_single_page(url, index_name=index_name)
                crawl_result = {
                    "success": True,
                    "documents_stored": 1 if store_documents else 0,
                    "pages_crawled": 1,
                    "errors": [f"Strategy '{strategy}' not fully implemented yet - falling back to single page crawl"],
                    "note": f"Used single page crawl instead of {strategy}"
                }
        
        # Prepare response
        response = {
            "success": crawl_result.get("success", True),
            "session_id": session_id,
            "strategy": strategy,
            "url": url,
            "index_name": index_name,
            "documents_stored": crawl_result.get("documents_stored", 0),
            "pages_crawled": crawl_result.get("pages_crawled", 0),
            "errors": crawl_result.get("errors", []),
            "progress": {
                "status": "completed",
                "progress_percent": 100.0,
                "current_item": 1,
                "total_items": 1
            }
        }
        
        # Add note if present
        if "note" in crawl_result:
            response["note"] = crawl_result["note"]
        
        if store_documents and crawl_result.get("documents_stored", 0) > 0:
            response["message"] = f"Successfully crawled and stored {crawl_result['documents_stored']} documents in index '{index_name}'. You can now search them using search_documents."
        else:
            response["message"] = f"Crawling completed. {crawl_result.get('pages_crawled', 0)} pages processed."

        return serialize_value(response)

    except Exception as e:
        logger.error(f"Error in crawl_website MCP tool: {e}")
        return {
            "success": False,
            "error": f"Crawling failed: {str(e)}",
            "url": url,
            "strategy": strategy
        }


@mcp.tool()
async def search_documents(
    query: str,
    index_name: Optional[str] = None,
    max_results: int = 10,
    search_type: str = "hybrid",
    use_reranking: bool = True,
    similarity_threshold: float = 0.1
) -> Dict[str, Any]:
    """
    Search crawled documents using vector similarity, keyword search, or hybrid RAG.

    Args:
        query: Search query (required)
        index_name: Specific index to search (searches all indexes if not specified)
        max_results: Maximum number of results to return (default: 10)
        search_type: Search strategy - "vector", "keyword", or "hybrid" (default: "hybrid")
        use_reranking: Whether to apply reranking for better results (default: True)
        similarity_threshold: Minimum similarity score for results (default: 0.1)

    Returns:
        Dictionary with search results and metadata
    """
    try:
        logger.info(f"MCP search_documents: query='{query}', index={index_name}, type={search_type}, max_results={max_results}")
        
        # Validate search type
        valid_types = ["vector", "keyword", "hybrid"]
        if search_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid search_type '{search_type}'. Must be one of: {', '.join(valid_types)}"
            }
        
        # Check if we have any documents to search
        stats = await search_service.get_document_stats()
        if stats["total_documents"] == 0:
            return {
                "success": True,
                "results": [],
                "total_results": 0,
                "query": query,
                "message": "No documents available for search. Use crawl_website first to crawl and store documents."
            }
        
        if search_type == "vector":
            # Vector similarity search
            results = await search_service.vector_search(
                query=query,
                top_k=max_results,
                similarity_threshold=similarity_threshold,
                index_name=index_name
            )
            
            search_results = []
            for result in results:
                search_results.append({
                    "title": result["title"],
                    "content": result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"],
                    "url": result["url"],
                    "similarity_score": result.get("similarity_score", 0.0),
                    "source_type": result.get("source_type", "unknown"),
                    "document_id": result["document_id"]
                })

            return serialize_value({
                "success": True,
                "results": search_results,
                "total_results": len(search_results),
                "query": query,
                "search_type": "vector",
                "statistics": stats
            })
            
        elif search_type == "keyword":
            # Keyword (BM25) search
            results = await search_service.keyword_search(
                query=query,
                top_k=max_results
            )
            
            search_results = []
            for result in results:
                search_results.append({
                    "title": result["title"],
                    "content": result["content"][:300] + "..." if len(result["content"]) > 300 else result["content"],
                    "url": result["url"],
                    "keyword_score": result.get("keyword_score", 0.0),
                    "source_type": result.get("source_type", "unknown"),
                    "document_id": result["document_id"]
                })

            return serialize_value({
                "success": True,
                "results": search_results,
                "total_results": len(search_results),
                "query": query,
                "search_type": "keyword",
                "statistics": stats
            })
            
        else:
            # Hybrid search (default)
            if use_reranking:
                search_response = await search_service.hybrid_search_with_reranking(
                    query=query,
                    top_k=max_results,
                    vector_weight=0.7,
                    keyword_weight=0.3,
                    similarity_threshold=similarity_threshold,
                    rerank_strategy="hybrid",
                    use_reranking=True,
                    index_name=index_name
                )
            else:
                search_response = await search_service.hybrid_search(
                    query=query,
                    top_k=max_results,
                    vector_weight=0.7,
                    keyword_weight=0.3,
                    similarity_threshold=similarity_threshold,
                    index_name=index_name
                )
            
            # Convert SearchResult objects to serializable format
            search_results = []
            for result in search_response.results:
                search_results.append({
                    "title": result.title,
                    "content": result.content,
                    "url": result.url,
                    "similarity_score": result.similarity_score,
                    "keyword_score": result.keyword_score,
                    "combined_score": result.combined_score,
                    "source_type": result.source_type,
                    "document_id": result.document_id
                })

            return serialize_value({
                "success": True,
                "results": search_results,
                "total_results": search_response.total_results,
                "query": search_response.query,
                "search_type": search_response.search_strategy,
                "search_time_ms": search_response.search_time_ms,
                "statistics": stats,
                "index_name": index_name,
                "message": f"Found {len(search_results)} relevant documents using {search_response.search_strategy} search{' in index ' + index_name if index_name else ' across all indexes'}."
            })

    except Exception as e:
        logger.error(f"Error in search_documents MCP tool: {e}")
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "query": query,
            "search_type": search_type
        }


@mcp.tool()
async def list_indexes() -> Dict[str, Any]:
    """
    List all available vector indexes.

    Returns:
        Dictionary with all available indexes and their metadata
    """
    try:
        logger.info("MCP list_indexes")
        
        # Import index_manager
        try:
            from ..services.index_manager import index_manager
        except ImportError:
            from webnexus.services.index_manager import index_manager
        
        # Get all indexes
        indexes = index_manager.list_indexes(active_only=True)
        
        # Format indexes
        index_list = []
        for idx in indexes:
            # Get created_at as string (safely handle SQLAlchemy columns)
            created_at_str = None
            try:
                created_at_val = getattr(idx, 'created_at', None)
                if created_at_val is not None:
                    created_at_str = created_at_val.isoformat() if hasattr(created_at_val, 'isoformat') else str(created_at_val)
            except:
                pass
            
            index_info = {
                "name": idx.name,
                "display_name": idx.display_name,
                "description": idx.description,
                "index_type": idx.index_type,
                "embedding_model": idx.embedding_model,
                "embedding_dimension": idx.embedding_dimension,
                "total_documents": idx.total_documents,
                "total_chunks": idx.total_chunks,
                "total_vectors": idx.total_vectors,
                "index_size_mb": idx.index_size_mb,
                "is_active": idx.is_active,
                "created_at": created_at_str
            }
            index_list.append(index_info)
        
        response = {
            "success": True,
            "indexes": index_list,
            "total_indexes": len(index_list),
            "message": f"Found {len(index_list)} active vector indexes."
        }

        return serialize_value(response)

    except Exception as e:
        logger.error(f"Error in list_indexes MCP tool: {e}")
        return {
            "success": False,
            "error": f"Failed to list indexes: {str(e)}"
        }


@mcp.tool()
async def create_index(
    name: str,
    display_name: str,
    description: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new vector index.

    Args:
        name: Unique index identifier (alphanumeric, underscore, hyphen)
        display_name: Human-readable name
        description: Optional description

    Returns:
        Dictionary with created index information
    """
    try:
        logger.info(f"MCP create_index: name={name}, display_name={display_name}")
        
        # Import index_manager
        try:
            from ..services.index_manager import index_manager
        except ImportError:
            from webnexus.services.index_manager import index_manager
        
        # Create index (handle optional description)
        vector_index = index_manager.create_index(
            name=name,
            display_name=display_name,
            description=description or "",
            embedding_model="dunzhang/stella_en_400M_v5",
            embedding_dimension=1024,
            index_type="IndexFlatIP"
        )
        
        # Get created_at as string (safely handle SQLAlchemy columns)
        created_at_str = None
        try:
            created_at_val = getattr(vector_index, 'created_at', None)
            if created_at_val is not None:
                created_at_str = created_at_val.isoformat() if hasattr(created_at_val, 'isoformat') else str(created_at_val)
        except:
            pass
        
        response = {
            "success": True,
            "index": {
                "name": vector_index.name,
                "display_name": vector_index.display_name,
                "description": vector_index.description,
                "index_type": vector_index.index_type,
                "embedding_model": vector_index.embedding_model,
                "embedding_dimension": vector_index.embedding_dimension,
                "created_at": created_at_str
            },
            "message": f"Successfully created index '{name}'. You can now crawl documents into this index."
        }

        return serialize_value(response)

    except ValueError as e:
        return {
            "success": False,
            "error": str(e)
        }
    except Exception as e:
        logger.error(f"Error in create_index MCP tool: {e}")
        return {
            "success": False,
            "error": f"Failed to create index: {str(e)}"
        }


@mcp.tool()
async def delete_index(
    name: str,
    delete_documents: bool = False
) -> Dict[str, Any]:
    """
    Delete a vector index.

    Args:
        name: Index name to delete
        delete_documents: Whether to also delete documents in this index (default: False)

    Returns:
        Dictionary with deletion result
    """
    try:
        logger.info(f"MCP delete_index: name={name}, delete_documents={delete_documents}")
        
        # Import index_manager
        try:
            from ..services.index_manager import index_manager
        except ImportError:
            from webnexus.services.index_manager import index_manager
        
        # Prevent deletion of default index
        if name == "default":
            return {
                "success": False,
                "error": "Cannot delete the default index."
            }

        # Check if index exists
        if not index_manager.get_index(name):
            return {
                "success": False,
                "error": f"Index '{name}' not found."
            }

        # Delete index
        index_manager.delete_index(name, delete_documents=delete_documents)

        response = {
            "success": True,
            "index_name": name,
            "documents_deleted": delete_documents,
            "message": f"Successfully deleted index '{name}'." + (" Documents also deleted." if delete_documents else "")
        }

        return serialize_value(response)

    except Exception as e:
        logger.error(f"Error in delete_index MCP tool: {e}")
        return {
            "success": False,
            "error": f"Failed to delete index: {str(e)}"
        }


@mcp.tool()
async def get_sources(
    limit: int = 50,
    url_pattern: Optional[str] = None,
    source_type: Optional[str] = None,
    index_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get information about available document sources and crawled content.

    Args:
        limit: Maximum number of sources to return (default: 50)
        url_pattern: Filter sources by URL pattern (optional)
        source_type: Filter by source type like "webpage", "pdf", etc. (optional)
        index_name: Filter by vector index name (optional)

    Returns:
        Dictionary with available sources and metadata
    """
    try:
        logger.info(f"MCP get_sources: limit={limit}, url_pattern={url_pattern}, source_type={source_type}, index_name={index_name}")
        
        db_session = db_config.get_session()
        try:
            from ..models.database import Document, DocumentChunk, VectorIndex
            from sqlalchemy import func, and_
            
            # Build query with filters
            query = db_session.query(
                Document.id,
                Document.title,
                Document.url,
                Document.crawl_type,
                Document.created_at,
                Document.doc_metadata,
                Document.vector_index_id,
                func.count(DocumentChunk.id).label('chunk_count'),
                func.sum(func.length(DocumentChunk.content)).label('total_content_length')
            ).outerjoin(DocumentChunk).group_by(Document.id)
            
            # Apply filters
            filters = []
            if url_pattern:
                filters.append(Document.url.like(f"%{url_pattern}%"))
            if source_type:
                filters.append(Document.crawl_type == source_type)
            if index_name:
                # Get index ID by name
                vector_index = db_session.query(VectorIndex).filter(VectorIndex.name == index_name).first()
                if vector_index:
                    filters.append(Document.vector_index_id == vector_index.id)
                else:
                    # Index not found - return empty results
                    db_session.close()
                    return {
                        "success": False,
                        "error": f"Index '{index_name}' not found."
                    }
            
            if filters:
                query = query.filter(and_(*filters))
            
            # Get total count and limited results
            total_count = query.count()
            sources = query.limit(limit).all()
            
            # Get overall statistics
            stats = await search_service.get_document_stats()
            
            # Format sources
            source_list = []
            for source in sources:
                source_info = {
                    "document_id": source.id,
                    "title": source.title or "Untitled",
                    "url": source.url,
                    "source_type": source.crawl_type or "unknown",
                    "created_at": source.created_at.isoformat() if source.created_at else None,
                    "chunk_count": source.chunk_count or 0,
                    "content_length": source.total_content_length or 0,
                    "metadata": source.doc_metadata or {}
                }
                source_list.append(source_info)
            
            # Get unique source types for reference
            source_types = db_session.query(Document.crawl_type).distinct().all()
            unique_types = [st[0] for st in source_types if st[0]]
            
            response = {
                "success": True,
                "sources": source_list,
                "total_sources": total_count,
                "returned_count": len(source_list),
                "filters": {
                    "url_pattern": url_pattern,
                    "source_type": source_type,
                    "limit": limit
                },
                "statistics": {
                    "total_documents": stats["total_documents"],
                    "total_chunks": stats["total_chunks"],
                    "total_embeddings": stats["total_embeddings"],
                    "available_source_types": unique_types
                },
                "message": f"Retrieved {len(source_list)} sources out of {total_count} total documents."
            }

            return serialize_value(response)

        finally:
            db_session.close()

    except Exception as e:
        logger.error(f"Error in get_sources MCP tool: {e}")
        return {
            "success": False,
            "error": f"Failed to get sources: {str(e)}",
            "filters": {
                "url_pattern": url_pattern,
                "source_type": source_type,
                "index_name": index_name,
                "limit": limit
            }
        }


def initialize_server() -> None:
    """Initialize the MCP server services."""
    logger.info("Initializing WebNexus MCP Server...")
    
    try:
        # Initialize database
        db_config.initialize()
        logger.info("Database initialized")
        
        # Initialize services
        try:
            from ..services.embedding_service import embedding_service
            from ..services.vector_service import vector_service
        except ImportError:
            from webnexus.services.embedding_service import embedding_service
            from webnexus.services.vector_service import vector_service
        
        embedding_service._load_model()
        vector_service._initialize_index()
        logger.info("Services initialized")
        
        logger.info("WebNexus MCP Server initialized successfully")
        
    except Exception as e:
        logger.error(f"Error initializing MCP server: {e}")
        raise


def main():
    """Run the MCP server."""
    # CRITICAL: Suppress ALL stdout except MCP protocol messages
    # Set environment variables to disable progress bars and verbose output
    os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
    os.environ['TRANSFORMERS_NO_ADVISORY_WARNINGS'] = '1'
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['CRAWL4AI_VERBOSE'] = '0'
    os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '0'

    # Configure logging to use stderr only (MCP uses stdout for protocol)
    logging.basicConfig(
        level=logging.CRITICAL,  # Only show critical errors
        format='%(levelname)s: %(message)s',
        stream=sys.stderr,
        force=True
    )

    # Suppress all third-party library logging including httpx/httpcore
    for logger_name in ['crawl4ai', 'transformers', 'sentence_transformers',
                        'torch', 'urllib3', 'httpx', 'httpcore']:
        lib_logger = logging.getLogger(logger_name)
        lib_logger.setLevel(logging.CRITICAL)
        lib_logger.propagate = False

    # Suppress warnings
    import warnings
    warnings.filterwarnings('ignore')

    # Initialize server services with COMPLETE stdout suppression
    # This prevents crawl4ai's [INIT], [FETCH], [COMPLETE] messages from polluting stdout
    try:
        with suppress_stdout():
            initialize_server()
    except Exception as e:
        sys.stderr.write(f"ERROR: Failed to initialize server: {e}\n")
        return 1

    # Determine transport method
    transport = "stdio" if "--stdio" in sys.argv else "stdio"  # Default to stdio

    # Run the FastMCP server (stdout is now clean for MCP JSON-RPC protocol)
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()