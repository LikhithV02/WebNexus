"""Index management service for multi-index vector storage"""

import logging
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session
from sqlalchemy import func

from ..config.database import db_config
from ..models.database import VectorIndex, Document, DocumentChunk, Embedding
from ..services.vector_service import VectorService

logger = logging.getLogger(__name__)


class IndexManager:
    """Manages multiple vector indexes for different topics/projects"""

    def __init__(self):
        """Initialize index manager"""
        self.db_config = db_config
        self.active_indexes: Dict[str, VectorService] = {}  # name -> VectorService
        # Use absolute path from project root
        self.project_root = Path(__file__).parent.parent.parent
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.db_config.get_session()
    
    def _get_index_paths(self, index_name: str) -> tuple[str, str]:
        """Get file paths for an index"""
        base_path = f"vectors/{index_name}"
        index_path = f"{base_path}/faiss_index"
        metadata_path = f"{base_path}/faiss_metadata.pkl"
        return index_path, metadata_path
    
    def create_index(
        self,
        name: str,
        display_name: str,
        description: str = None,
        embedding_model: str = "dunzhang/stella_en_400M_v5",
        embedding_dimension: int = 1024,
        index_type: str = "IndexFlatIP"
    ) -> VectorIndex:
        """
        Create a new vector index
        
        Args:
            name: Unique index identifier (e.g., "python_docs", "ml_papers")
            display_name: Human-readable name
            description: Optional description
            embedding_model: Model to use for embeddings
            embedding_dimension: Dimension of embeddings
            index_type: FAISS index type
        
        Returns:
            Created VectorIndex instance
        """
        db_session = self.get_session()
        try:
            # Validate name (alphanumeric, underscore, hyphen only)
            if not name.replace("_", "").replace("-", "").isalnum():
                raise ValueError("Index name must contain only alphanumeric characters, underscores, and hyphens")
            
            # Check if index already exists
            existing = db_session.query(VectorIndex).filter_by(name=name).first()
            if existing:
                raise ValueError(f"Index '{name}' already exists")
            
            # Get file paths
            index_path, metadata_path = self._get_index_paths(name)

            # Create index directory
            full_index_dir = self.project_root / "data" / "vectors" / name
            full_index_dir.mkdir(parents=True, exist_ok=True)
            
            # Create database entry
            vector_index = VectorIndex(
                name=name,
                display_name=display_name,
                description=description,
                index_type=index_type,
                embedding_dimension=embedding_dimension,
                embedding_model=embedding_model,
                index_path=index_path,
                metadata_path=metadata_path,
                total_documents=0,
                total_chunks=0,
                total_vectors=0,
                index_size_mb=0.0,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                config={}
            )
            
            db_session.add(vector_index)
            db_session.commit()
            db_session.refresh(vector_index)
            
            logger.info(f"Created vector index: {name} (ID: {vector_index.id})")
            return vector_index
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error creating index '{name}': {e}")
            raise
        finally:
            db_session.close()
    
    def get_index(self, name: str) -> Optional[VectorIndex]:
        """Get index by name"""
        db_session = self.get_session()
        try:
            return db_session.query(VectorIndex).filter_by(name=name).first()
        finally:
            db_session.close()
    
    def get_index_by_id(self, index_id: int) -> Optional[VectorIndex]:
        """Get index by ID"""
        db_session = self.get_session()
        try:
            return db_session.query(VectorIndex).filter_by(id=index_id).first()
        finally:
            db_session.close()
    
    def list_indexes(
        self,
        active_only: bool = True,
        limit: int = 100,
        offset: int = 0
    ) -> List[VectorIndex]:
        """
        List all vector indexes
        
        Args:
            active_only: Only return active indexes
            limit: Maximum number of results
            offset: Number of results to skip
        
        Returns:
            List of VectorIndex instances
        """
        db_session = self.get_session()
        try:
            query = db_session.query(VectorIndex)
            
            if active_only:
                query = query.filter_by(is_active=True)
            
            return query.order_by(VectorIndex.created_at.desc()).offset(offset).limit(limit).all()
            
        finally:
            db_session.close()
    
    def update_index_stats(self, index_id: int) -> VectorIndex:
        """
        Update statistics for an index
        
        Args:
            index_id: Index ID to update
        
        Returns:
            Updated VectorIndex instance
        """
        db_session = self.get_session()
        try:
            vector_index = db_session.query(VectorIndex).filter_by(id=index_id).first()
            if not vector_index:
                raise ValueError(f"Index not found: {index_id}")
            
            # Count documents in this index
            doc_count = db_session.query(func.count(Document.id)).filter(
                Document.vector_index_id == index_id
            ).scalar()
            
            # Count chunks in documents from this index
            chunk_count = db_session.query(func.count(DocumentChunk.id)).join(
                Document
            ).filter(Document.vector_index_id == index_id).scalar()
            
            # Get index file size
            full_index_path = self.project_root / "data" / vector_index.index_path
            index_size_mb = 0.0
            if full_index_path.exists():
                index_dir = full_index_path.parent
                index_size_mb = sum(f.stat().st_size for f in index_dir.glob("*")) / (1024 * 1024)
            
            # Update statistics
            vector_index.total_documents = doc_count
            vector_index.total_chunks = chunk_count
            vector_index.total_vectors = chunk_count  # Assuming one vector per chunk
            vector_index.index_size_mb = round(index_size_mb, 2)
            vector_index.updated_at = datetime.utcnow()
            vector_index.last_indexed_at = datetime.utcnow()
            
            db_session.commit()
            db_session.refresh(vector_index)
            
            logger.info(f"Updated stats for index '{vector_index.name}': {doc_count} docs, {chunk_count} chunks")
            return vector_index
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error updating index stats: {e}")
            raise
        finally:
            db_session.close()
    
    def delete_index(self, name: str, delete_documents: bool = False) -> Dict[str, Any]:
        """
        Delete a vector index
        
        Args:
            name: Index name to delete
            delete_documents: If True, also delete all documents in this index
        
        Returns:
            Deletion results
        """
        db_session = self.get_session()
        try:
            vector_index = db_session.query(VectorIndex).filter_by(name=name).first()
            if not vector_index:
                raise ValueError(f"Index not found: {name}")
            
            index_id = vector_index.id
            
            # Count documents that will be affected
            doc_count = db_session.query(func.count(Document.id)).filter(
                Document.vector_index_id == index_id
            ).scalar()
            
            if delete_documents:
                # Delete all documents in this index (cascades to chunks and embeddings)
                db_session.query(Document).filter(
                    Document.vector_index_id == index_id
                ).delete()
                logger.info(f"Deleted {doc_count} documents from index '{name}'")
            else:
                # Set documents' vector_index_id to NULL
                db_session.query(Document).filter(
                    Document.vector_index_id == index_id
                ).update({"vector_index_id": None})
                logger.info(f"Unlinked {doc_count} documents from index '{name}'")
            
            # Delete index entry from database
            db_session.delete(vector_index)
            db_session.commit()
            
            # Delete index files
            full_index_dir = self.project_root / "data" / "vectors" / name
            if full_index_dir.exists():
                shutil.rmtree(full_index_dir)
                logger.info(f"Deleted index files: {full_index_dir}")
            
            # Remove from active indexes cache
            if name in self.active_indexes:
                del self.active_indexes[name]
            
            return {
                "success": True,
                "index_name": name,
                "documents_deleted" if delete_documents else "documents_unlinked": doc_count,
                "files_deleted": full_index_dir.exists()
            }
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error deleting index '{name}': {e}")
            raise
        finally:
            db_session.close()
    
    def get_vector_service(self, index_name: str) -> VectorService:
        """
        Get or create VectorService for a specific index
        
        Args:
            index_name: Index name
        
        Returns:
            VectorService instance for this index
        """
        # Check cache first
        if index_name in self.active_indexes:
            return self.active_indexes[index_name]
        
        # Get index from database
        vector_index = self.get_index(index_name)
        if not vector_index:
            raise ValueError(f"Index not found: {index_name}")
        
        # Create VectorService with custom paths
        full_index_path = self.project_root / "data" / vector_index.index_path
        full_metadata_path = self.project_root / "data" / vector_index.metadata_path
        
        # Create VectorService with custom parameters and paths
        vector_service = VectorService(
            dimension=vector_index.embedding_dimension,
            index_type=vector_index.index_type,
            custom_index_path=full_index_path,
            custom_metadata_path=full_metadata_path
        )
        
        # Cache for future use
        self.active_indexes[index_name] = vector_service
        
        logger.info(f"Loaded VectorService for index '{index_name}'")
        return vector_service
    
    def get_index_statistics(self, index_name: str) -> Dict[str, Any]:
        """
        Get detailed statistics for an index
        
        Args:
            index_name: Index name
        
        Returns:
            Statistics dictionary
        """
        db_session = self.get_session()
        try:
            vector_index = db_session.query(VectorIndex).filter_by(name=index_name).first()
            if not vector_index:
                raise ValueError(f"Index not found: {index_name}")
            
            # Get document statistics
            doc_count = db_session.query(func.count(Document.id)).filter(
                Document.vector_index_id == vector_index.id
            ).scalar()
            
            # Get crawl type distribution
            crawl_types = db_session.query(
                Document.crawl_type,
                func.count(Document.id).label('count')
            ).filter(
                Document.vector_index_id == vector_index.id
            ).group_by(Document.crawl_type).all()
            
            # Get domain distribution (top 10)
            domains = db_session.query(
                Document.domain,
                func.count(Document.id).label('count')
            ).filter(
                Document.vector_index_id == vector_index.id
            ).group_by(Document.domain).order_by(
                func.count(Document.id).desc()
            ).limit(10).all()
            
            return {
                "index_info": vector_index.to_dict(),
                "total_documents": doc_count,
                "total_chunks": vector_index.total_chunks,
                "total_vectors": vector_index.total_vectors,
                "index_size_mb": vector_index.index_size_mb,
                "crawl_types": {ctype: count for ctype, count in crawl_types if ctype},
                "top_domains": {domain: count for domain, count in domains if domain}
            }
            
        finally:
            db_session.close()


# Global index manager instance
index_manager = IndexManager()