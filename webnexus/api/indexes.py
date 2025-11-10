"""
Index Management API Router

FastAPI router for managing multiple vector indexes.
Provides CRUD operations for creating, listing, updating, and deleting vector indexes.
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.index_manager import index_manager
from ..config.database import db_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/indexes", tags=["indexes"])


# Request/Response Models
class CreateIndexRequest(BaseModel):
    """Request model for creating a new index"""
    name: str = Field(..., description="Unique index identifier (alphanumeric, underscore, hyphen)")
    display_name: str = Field(..., description="Human-readable name")
    description: Optional[str] = Field(None, description="Optional description")
    embedding_model: str = Field("dunzhang/stella_en_400M_v5", description="Embedding model to use")
    embedding_dimension: int = Field(1024, description="Dimension of embeddings")
    index_type: str = Field("IndexFlatIP", description="FAISS index type")


class IndexResponse(BaseModel):
    """Response model for index information"""
    id: int
    name: str
    display_name: str
    description: Optional[str]
    index_type: str
    embedding_dimension: int
    embedding_model: str
    total_documents: int
    total_chunks: int
    total_vectors: int
    index_size_mb: float
    is_active: bool
    created_at: str
    updated_at: str


class IndexListResponse(BaseModel):
    """Response model for listing indexes"""
    indexes: List[IndexResponse]
    total: int


class IndexStatsResponse(BaseModel):
    """Response model for index statistics"""
    index_info: IndexResponse
    total_documents: int
    total_chunks: int
    total_vectors: int
    index_size_mb: float
    crawl_types: Dict[str, int]
    top_domains: Dict[str, int]


class DeleteIndexRequest(BaseModel):
    """Request model for deleting an index"""
    delete_documents: bool = Field(False, description="Whether to also delete documents in this index")


class MessageResponse(BaseModel):
    """Generic message response"""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# API Endpoints

@router.post("/", response_model=IndexResponse, status_code=status.HTTP_201_CREATED)
async def create_index(request: CreateIndexRequest):
    """
    Create a new vector index.
    
    Creates a new vector index with the specified configuration.
    The index will be stored in `data/vectors/{name}/`.
    """
    try:
        vector_index = index_manager.create_index(
            name=request.name,
            display_name=request.display_name,
            description=request.description,
            embedding_model=request.embedding_model,
            embedding_dimension=request.embedding_dimension,
            index_type=request.index_type
        )
        
        return IndexResponse(
            id=vector_index.id,
            name=vector_index.name,
            display_name=vector_index.display_name,
            description=vector_index.description,
            index_type=vector_index.index_type,
            embedding_dimension=vector_index.embedding_dimension,
            embedding_model=vector_index.embedding_model,
            total_documents=vector_index.total_documents,
            total_chunks=vector_index.total_chunks,
            total_vectors=vector_index.total_vectors,
            index_size_mb=vector_index.index_size_mb,
            is_active=vector_index.is_active,
            created_at=vector_index.created_at.isoformat() if vector_index.created_at else "",
            updated_at=vector_index.updated_at.isoformat() if vector_index.updated_at else ""
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating index: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/", response_model=IndexListResponse)
async def list_indexes(
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0
):
    """
    List all vector indexes.
    
    Returns a list of all available vector indexes with their metadata and statistics.
    """
    try:
        indexes = index_manager.list_indexes(active_only=active_only, limit=limit, offset=offset)
        
        index_responses = []
        for idx in indexes:
            index_responses.append(IndexResponse(
                id=idx.id,
                name=idx.name,
                display_name=idx.display_name,
                description=idx.description,
                index_type=idx.index_type,
                embedding_dimension=idx.embedding_dimension,
                embedding_model=idx.embedding_model,
                total_documents=idx.total_documents,
                total_chunks=idx.total_chunks,
                total_vectors=idx.total_vectors,
                index_size_mb=idx.index_size_mb,
                is_active=idx.is_active,
                created_at=idx.created_at.isoformat() if idx.created_at else "",
                updated_at=idx.updated_at.isoformat() if idx.updated_at else ""
            ))
        
        return IndexListResponse(
            indexes=index_responses,
            total=len(index_responses)
        )
    except Exception as e:
        logger.error(f"Error listing indexes: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{index_name}", response_model=IndexResponse)
async def get_index(index_name: str):
    """
    Get details of a specific index.
    
    Returns detailed information about a single vector index.
    """
    try:
        vector_index = index_manager.get_index(index_name)
        if not vector_index:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index '{index_name}' not found"
            )
        
        return IndexResponse(
            id=vector_index.id,
            name=vector_index.name,
            display_name=vector_index.display_name,
            description=vector_index.description,
            index_type=vector_index.index_type,
            embedding_dimension=vector_index.embedding_dimension,
            embedding_model=vector_index.embedding_model,
            total_documents=vector_index.total_documents,
            total_chunks=vector_index.total_chunks,
            total_vectors=vector_index.total_vectors,
            index_size_mb=vector_index.index_size_mb,
            is_active=vector_index.is_active,
            created_at=vector_index.created_at.isoformat() if vector_index.created_at else "",
            updated_at=vector_index.updated_at.isoformat() if vector_index.updated_at else ""
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting index: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{index_name}/stats", response_model=IndexStatsResponse)
async def get_index_statistics(index_name: str):
    """
    Get detailed statistics for an index.
    
    Returns comprehensive statistics including document counts, crawl types, and top domains.
    """
    try:
        vector_index = index_manager.get_index(index_name)
        if not vector_index:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index '{index_name}' not found"
            )
        
        # Get detailed statistics from database
        session = db_config.get_session()
        try:
            from ..models.database import Document
            from sqlalchemy import func
            
            # Get crawl type distribution
            crawl_types = dict(
                session.query(Document.crawl_type, func.count(Document.id))
                .filter(Document.vector_index_id == vector_index.id)
                .group_by(Document.crawl_type)
                .all()
            )
            
            # Get top domains
            top_domains_query = (
                session.query(
                    func.substr(Document.url, func.instr(Document.url, '://') + 3),
                    func.count(Document.id)
                )
                .filter(Document.vector_index_id == vector_index.id)
                .group_by(func.substr(Document.url, func.instr(Document.url, '://') + 3))
                .order_by(func.count(Document.id).desc())
                .limit(10)
                .all()
            )
            top_domains = {domain: count for domain, count in top_domains_query}
            
        finally:
            session.close()
        
        index_info = IndexResponse(
            id=vector_index.id,
            name=vector_index.name,
            display_name=vector_index.display_name,
            description=vector_index.description,
            index_type=vector_index.index_type,
            embedding_dimension=vector_index.embedding_dimension,
            embedding_model=vector_index.embedding_model,
            total_documents=vector_index.total_documents,
            total_chunks=vector_index.total_chunks,
            total_vectors=vector_index.total_vectors,
            index_size_mb=vector_index.index_size_mb,
            is_active=vector_index.is_active,
            created_at=vector_index.created_at.isoformat() if vector_index.created_at else "",
            updated_at=vector_index.updated_at.isoformat() if vector_index.updated_at else ""
        )
        
        return IndexStatsResponse(
            index_info=index_info,
            total_documents=vector_index.total_documents,
            total_chunks=vector_index.total_chunks,
            total_vectors=vector_index.total_vectors,
            index_size_mb=vector_index.index_size_mb,
            crawl_types=crawl_types,
            top_domains=top_domains
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting index statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{index_name}/update-stats", response_model=MessageResponse)
async def update_index_stats(index_name: str):
    """
    Update index statistics.
    
    Recalculates and updates statistics for the specified index.
    """
    try:
        vector_index = index_manager.get_index(index_name)
        if not vector_index:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index '{index_name}' not found"
            )
        
        index_manager.update_index_stats(index_name)
        
        return MessageResponse(
            success=True,
            message=f"Successfully updated statistics for index '{index_name}'",
            details={
                "index_name": index_name,
                "total_documents": vector_index.total_documents,
                "total_chunks": vector_index.total_chunks,
                "total_vectors": vector_index.total_vectors
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating index statistics: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{index_name}", response_model=MessageResponse)
async def delete_index(index_name: str, request: DeleteIndexRequest = DeleteIndexRequest()):
    """
    Delete a vector index.
    
    Deletes the specified index and optionally its associated documents.
    """
    try:
        if index_name == "default":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete the default index"
            )
        
        vector_index = index_manager.get_index(index_name)
        if not vector_index:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Index '{index_name}' not found"
            )
        
        index_manager.delete_index(index_name, delete_documents=request.delete_documents)
        
        return MessageResponse(
            success=True,
            message=f"Successfully deleted index '{index_name}'",
            details={
                "index_name": index_name,
                "documents_deleted": request.delete_documents
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting index: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))