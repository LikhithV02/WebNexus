"""
RAG Query Endpoints

FastAPI endpoints for document search and retrieval in WebNexus.
Provides vector search, keyword search, and hybrid RAG functionality.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field, validator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from ..services.search_service import search_service, SearchResponse, SearchResult
from ..services.storage_service import storage_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


# Request Models
class SearchRequest(BaseModel):
    """Request model for document search."""
    query: str = Field(..., min_length=1, max_length=1000, description="Search query")
    index_name: Optional[str] = Field(None, description="Specific index to search (searches all if not specified)")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")
    search_type: str = Field(default="hybrid", description="Search type: vector, keyword, or hybrid")
    vector_weight: float = Field(default=0.7, ge=0.0, le=1.0, description="Weight for vector similarity (0.0-1.0)")
    keyword_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Weight for keyword scores (0.0-1.0)")
    similarity_threshold: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")
    use_reranking: bool = Field(default=False, description="Whether to apply reranking")
    rerank_strategy: str = Field(default="hybrid", description="Reranking strategy: bm25, hybrid, or quality")

    @validator('vector_weight', 'keyword_weight', always=True)
    def validate_weights(cls, v, values):
        """Ensure vector and keyword weights sum to 1.0."""
        if 'vector_weight' in values and 'keyword_weight' in values:
            if abs(values['vector_weight'] + values['keyword_weight'] - 1.0) > 0.01:
                raise ValueError("vector_weight and keyword_weight must sum to 1.0")
        return v


class DocumentQuery(BaseModel):
    """Request model for document queries."""
    document_id: str = Field(..., description="Document ID to query")
    query: str = Field(..., min_length=1, max_length=1000, description="Query within document")
    max_chunks: int = Field(default=5, ge=1, le=20, description="Maximum chunks to return")


# Response Models
class SearchResultResponse(BaseModel):
    """Response model for search results."""
    document_id: str
    chunk_id: Optional[str]
    title: str
    content: str
    url: str
    similarity_score: float
    keyword_score: float
    combined_score: float
    metadata: Dict[str, Any]
    source_type: str


class SearchApiResponse(BaseModel):
    """API response model for search."""
    success: bool
    results: List[SearchResultResponse]
    total_results: int
    query: str
    search_time_ms: float
    search_strategy: str
    message: Optional[str] = None


class DocumentInfo(BaseModel):
    """Document information model."""
    document_id: str
    title: str
    url: str
    source_type: str
    created_at: Optional[str]
    chunk_count: int
    metadata: Dict[str, Any]


class DocumentListResponse(BaseModel):
    """Response model for document listing."""
    success: bool
    documents: List[DocumentInfo]
    total_count: int
    message: Optional[str] = None


# Search Endpoints
@router.post("/query", response_model=SearchApiResponse)
async def search_documents(request: SearchRequest):
    """
    Search documents using vector, keyword, or hybrid search.
    
    Supports multiple search strategies:
    - vector: Pure vector similarity search
    - keyword: BM25 keyword search  
    - hybrid: Combined vector + keyword search with configurable weights
    
    Optional reranking can be applied to improve result relevance.
    """
    try:
        logger.info(f"Search request: query='{request.query}', type={request.search_type}, top_k={request.top_k}")
        
        if request.search_type == "vector":
            # Pure vector search
            vector_results = await search_service.vector_search(
                request.query,
                top_k=request.top_k,
                similarity_threshold=request.similarity_threshold,
                index_name=request.index_name
            )
            
            # Convert to SearchResult format
            results = []
            for result in vector_results:
                results.append(SearchResultResponse(
                    document_id=str(result['document_id']),
                    chunk_id=str(result.get('chunk_id')) if result.get('chunk_id') is not None else None,
                    title=result['title'],
                    content=result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                    url=result['url'],
                    similarity_score=result.get('similarity_score', 0.0),
                    keyword_score=0.0,
                    combined_score=result.get('similarity_score', 0.0),
                    metadata=result.get('metadata', {}),
                    source_type=result.get('source_type', 'unknown')
                ))
            
            return SearchApiResponse(
                success=True,
                results=results,
                total_results=len(results),
                query=request.query,
                search_time_ms=0.0,  # Vector search doesn't track time separately
                search_strategy="vector"
            )
            
        elif request.search_type == "keyword":
            # Pure keyword search
            # Note: keyword_search searches across all documents regardless of index
            keyword_results = await search_service.keyword_search(
                request.query,
                top_k=request.top_k
            )
            
            # Convert to SearchResult format
            results = []
            for result in keyword_results:
                results.append(SearchResultResponse(
                    document_id=str(result['document_id']),
                    chunk_id=str(result.get('chunk_id')) if result.get('chunk_id') is not None else None,
                    title=result['title'],
                    content=result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                    url=result['url'],
                    similarity_score=0.0,
                    keyword_score=result.get('keyword_score', 0.0),
                    combined_score=result.get('keyword_score', 0.0),
                    metadata=result.get('metadata', {}),
                    source_type=result.get('source_type', 'unknown')
                ))
            
            return SearchApiResponse(
                success=True,
                results=results,
                total_results=len(results),
                query=request.query,
                search_time_ms=0.0,  # Keyword search doesn't track time separately
                search_strategy="keyword"
            )
            
        else:
            # Hybrid search (default)
            if request.use_reranking:
                search_response = await search_service.hybrid_search_with_reranking(
                    query=request.query,
                    top_k=request.top_k,
                    vector_weight=request.vector_weight,
                    keyword_weight=request.keyword_weight,
                    similarity_threshold=request.similarity_threshold,
                    rerank_strategy=request.rerank_strategy,
                    use_reranking=True,
                    index_name=request.index_name
                )
            else:
                search_response = await search_service.hybrid_search(
                    query=request.query,
                    top_k=request.top_k,
                    vector_weight=request.vector_weight,
                    keyword_weight=request.keyword_weight,
                    similarity_threshold=request.similarity_threshold,
                    index_name=request.index_name
                )
            
            # Convert SearchResult objects to response model
            results = []
            for result in search_response.results:
                results.append(SearchResultResponse(
                    document_id=result.document_id,
                    chunk_id=result.chunk_id,
                    title=result.title,
                    content=result.content,
                    url=result.url,
                    similarity_score=result.similarity_score,
                    keyword_score=result.keyword_score,
                    combined_score=result.combined_score,
                    metadata=result.metadata,
                    source_type=result.source_type
                ))
            
            return SearchApiResponse(
                success=True,
                results=results,
                total_results=search_response.total_results,
                query=search_response.query,
                search_time_ms=search_response.search_time_ms,
                search_strategy=search_response.search_strategy
            )
    
    except Exception as e:
        logger.error(f"Error in search endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/simple", response_model=SearchApiResponse)
async def simple_search(
    q: str = Query(..., min_length=1, max_length=1000, description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    type: str = Query("hybrid", description="Search type: vector, keyword, or hybrid"),
    index: Optional[str] = Query(None, description="Specific index to search (searches all if not specified)")
):
    """
    Simple search endpoint with query parameters.
    
    Convenient GET endpoint for basic search functionality.
    """
    try:
        # Create search request from query parameters
        search_request = SearchRequest(
            query=q,
            top_k=limit,
            search_type=type,
            index_name=index
        )
        
        # Use the main search endpoint
        return await search_documents(search_request)
        
    except Exception as e:
        logger.error(f"Error in simple search endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Simple search failed: {str(e)}")


@router.post("/document", response_model=SearchApiResponse)
async def search_within_document(request: DocumentQuery):
    """
    Search within a specific document.
    
    Performs search limited to chunks from a single document.
    """
    try:
        logger.info(f"Document search: doc_id={request.document_id}, query='{request.query}'")
        
        # Get document chunks first
        db_session = storage_service.db_config.get_session()
        try:
            from ..models.database import Document, DocumentChunk
            
            # Verify document exists
            document = db_session.query(Document).filter(
                Document.id == request.document_id
            ).first()
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Get chunks for this document
            chunks = db_session.query(DocumentChunk).filter(
                DocumentChunk.document_id == request.document_id
            ).limit(request.max_chunks).all()
            
            if not chunks:
                return SearchApiResponse(
                    success=True,
                    results=[],
                    total_results=0,
                    query=request.query,
                    search_time_ms=0.0,
                    search_strategy="document_search",
                    message=f"No chunks found in document {request.document_id}"
                )
            
            # Perform vector search on document chunks
            # This would need to be implemented to filter by document_id
            vector_results = await search_service.vector_search(
                request.query,
                top_k=request.max_chunks * 2,  # Get more for filtering
                similarity_threshold=0.0
            )
            
            # Filter results to only include chunks from the target document
            filtered_results = [
                r for r in vector_results 
                if r['document_id'] == request.document_id
            ][:request.max_chunks]
            
            # Convert to response format
            results = []
            for result in filtered_results:
                results.append(SearchResultResponse(
                    document_id=str(result['document_id']),
                    chunk_id=str(result.get('chunk_id')) if result.get('chunk_id') is not None else None,
                    title=result['title'],
                    content=result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                    url=result['url'],
                    similarity_score=result.get('similarity_score', 0.0),
                    keyword_score=0.0,
                    combined_score=result.get('similarity_score', 0.0),
                    metadata=result.get('metadata', {}),
                    source_type=result.get('source_type', 'unknown')
                ))
            
            return SearchApiResponse(
                success=True,
                results=results,
                total_results=len(results),
                query=request.query,
                search_time_ms=0.0,
                search_strategy="document_search"
            )
            
        finally:
            db_session.close()
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in document search endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Document search failed: {str(e)}")


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    limit: int = Query(50, ge=1, le=200, description="Number of documents to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    url_pattern: str = Query(None, description="URL pattern to filter by")
):
    """
    List available documents with optional URL filtering.
    
    Useful for discovering what content is available for search.
    """
    try:
        logger.info(f"List documents: limit={limit}, offset={offset}, url_pattern={url_pattern}")
        
        if url_pattern:
            # Search by URL pattern
            url_results = await search_service.search_documents_by_url(
                url_pattern=url_pattern,
                limit=limit
            )
            
            documents = []
            for doc in url_results:
                documents.append(DocumentInfo(
                    document_id=str(doc['document_id']),
                    title=doc['title'],
                    url=doc['url'],
                    source_type=doc['source_type'],
                    created_at=doc.get('created_at'),
                    chunk_count=0,  # Would need separate query
                    metadata=doc.get('metadata', {})
                ))
            
            return DocumentListResponse(
                success=True,
                documents=documents,
                total_count=len(documents)
            )
        
        else:
            # Get all documents with pagination
            db_session = storage_service.db_config.get_session()
            try:
                from ..models.database import Document, DocumentChunk
                from sqlalchemy import func
                
                # Get documents with chunk counts
                query = db_session.query(
                    Document,
                    func.count(DocumentChunk.id).label('chunk_count')
                ).outerjoin(DocumentChunk).group_by(Document.id)
                
                total_count = query.count()
                docs_with_counts = query.offset(offset).limit(limit).all()
                
                documents = []
                for doc, chunk_count in docs_with_counts:
                    documents.append(DocumentInfo(
                        document_id=str(doc.id),
                        title=doc.title or "Untitled",
                        url=doc.url,
                        source_type=doc.source_type or "unknown",
                        created_at=doc.created_at.isoformat() if doc.created_at else None,
                        chunk_count=chunk_count or 0,
                        metadata=doc.doc_metadata or {}
                    ))
                
                return DocumentListResponse(
                    success=True,
                    documents=documents,
                    total_count=total_count
                )
                
            finally:
                db_session.close()
    
    except Exception as e:
        logger.error(f"Error in list documents endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@router.get("/stats")
async def get_search_stats():
    """
    Get search service statistics.
    
    Returns information about indexed documents, search capabilities, and performance.
    """
    try:
        stats = await search_service.get_document_stats()
        
        return JSONResponse({
            "success": True,
            "statistics": {
                "search_service": stats,
                "capabilities": {
                    "vector_search": True,
                    "keyword_search": True,
                    "hybrid_search": True,
                    "reranking": True,
                    "document_filtering": True
                },
                "search_strategies": [
                    "vector",
                    "keyword", 
                    "hybrid",
                    "hybrid+bm25_rerank",
                    "hybrid+hybrid_rerank",
                    "hybrid+quality_rerank"
                ]
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting search stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get search statistics: {str(e)}")