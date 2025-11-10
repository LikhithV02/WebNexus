"""Vector storage service using FAISS"""

import os
import pickle
import logging
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
import numpy as np

import faiss
from sqlalchemy.orm import Session

from ..config.settings import settings
from ..models.database import DocumentChunk, Embedding

logger = logging.getLogger(__name__)


class VectorService:
    """FAISS-based vector storage service"""

    def __init__(
        self,
        dimension: int = 1024,
        index_type: str = "IndexFlatIP",
        custom_index_path: Optional[Path] = None,
        custom_metadata_path: Optional[Path] = None
    ):
        """
        Initialize vector service
        
        Args:
            dimension: Embedding dimension (default: 1024 for Stella)
            index_type: FAISS index type (IndexFlatIP for cosine similarity)
            custom_index_path: Optional custom path for FAISS index file
            custom_metadata_path: Optional custom path for metadata file
        """
        self.dimension = dimension
        self.index_type = index_type
        self.index = None
        self.metadata = []  # Store chunk IDs and metadata

        # Use absolute paths from project root
        project_root = Path(__file__).parent.parent.parent

        # Set paths (custom or default)
        if custom_index_path:
            self.index_path = custom_index_path
        else:
            self.index_path = project_root / "data" / "faiss_index"

        if custom_metadata_path:
            self.metadata_path = custom_metadata_path
        else:
            self.metadata_path = project_root / "data" / "faiss_metadata.pkl"
        
        # Ensure parent directory exists
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize or load existing FAISS index"""
        try:
            if self.index_path.exists() and self.metadata_path.exists():
                # Load existing index
                self.index = faiss.read_index(str(self.index_path))
                with open(self.metadata_path, 'rb') as f:
                    self.metadata = pickle.load(f)
                logger.info(f"Loaded existing FAISS index with {self.index.ntotal} vectors")
            else:
                # Create new index
                if self.index_type == "IndexFlatIP":
                    # Inner product (cosine similarity with normalized vectors)
                    self.index = faiss.IndexFlatIP(self.dimension)
                elif self.index_type == "IndexFlatL2":
                    # L2 distance
                    self.index = faiss.IndexFlatL2(self.dimension)
                elif self.index_type == "IndexIVFFlat":
                    # IVF index for larger datasets
                    quantizer = faiss.IndexFlatL2(self.dimension)
                    self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)  # 100 centroids
                else:
                    raise ValueError(f"Unsupported index type: {self.index_type}")
                
                self.metadata = []
                logger.info(f"Created new FAISS index: {self.index_type}")
        except Exception as e:
            logger.error(f"Error initializing FAISS index: {e}")
            # Fallback to new index
            self.index = faiss.IndexFlatIP(self.dimension)
            self.metadata = []
    
    def add_vectors(self, vectors: np.ndarray, chunk_ids: List[int], metadata_list: List[Dict[str, Any]] = None) -> List[int]:
        """
        Add vectors to the index
        
        Args:
            vectors: Numpy array of shape (n_vectors, dimension)
            chunk_ids: List of chunk IDs corresponding to vectors
            metadata_list: Optional metadata for each vector
        
        Returns:
            List of FAISS indices where vectors were added
        """
        if vectors.shape[1] != self.dimension:
            raise ValueError(f"Vector dimension {vectors.shape[1]} doesn't match index dimension {self.dimension}")
        
        # Normalize vectors for cosine similarity (if using IndexFlatIP)
        if self.index_type == "IndexFlatIP":
            vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
        
        # Get starting index
        start_idx = self.index.ntotal
        
        # Add to FAISS
        self.index.add(vectors.astype(np.float32))
        
        # Add metadata
        if metadata_list is None:
            metadata_list = [{"chunk_id": chunk_id} for chunk_id in chunk_ids]
        else:
            # Ensure chunk_id is in metadata
            for i, meta in enumerate(metadata_list):
                meta["chunk_id"] = chunk_ids[i]
        
        self.metadata.extend(metadata_list)
        
        # Return FAISS indices
        faiss_indices = list(range(start_idx, start_idx + len(vectors)))
        
        logger.info(f"Added {len(vectors)} vectors to FAISS index (total: {self.index.ntotal})")
        return faiss_indices
    
    def search(self, query_vector: np.ndarray, k: int = 5, return_metadata: bool = True) -> Tuple[List[float], List[int], List[Dict[str, Any]]]:
        """
        Search for similar vectors
        
        Args:
            query_vector: Query vector of shape (1, dimension) or (dimension,)
            k: Number of results to return
            return_metadata: Whether to return metadata
        
        Returns:
            Tuple of (similarities, faiss_indices, metadata_list)
        """
        if self.index.ntotal == 0:
            return [], [], []
        
        # Ensure query vector has correct shape
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        
        if query_vector.shape[1] != self.dimension:
            raise ValueError(f"Query vector dimension {query_vector.shape[1]} doesn't match index dimension {self.dimension}")
        
        # Normalize query vector for cosine similarity
        if self.index_type == "IndexFlatIP":
            query_vector = query_vector / np.linalg.norm(query_vector, axis=1, keepdims=True)
        
        # Search
        k = min(k, self.index.ntotal)  # Don't search for more than available
        similarities, faiss_indices = self.index.search(query_vector.astype(np.float32), k)
        
        # Extract results
        similarities = similarities[0].tolist()  # First row
        faiss_indices = faiss_indices[0].tolist()  # First row
        
        # Get metadata
        metadata_list = []
        if return_metadata:
            for idx in faiss_indices:
                if 0 <= idx < len(self.metadata):
                    metadata_list.append(self.metadata[idx])
                else:
                    metadata_list.append({"chunk_id": None, "error": "Invalid index"})
        
        return similarities, faiss_indices, metadata_list
    
    def search_by_chunk_ids(self, query_vector: np.ndarray, filter_chunk_ids: List[int], k: int = 5) -> Tuple[List[float], List[int], List[Dict[str, Any]]]:
        """
        Search within a specific set of chunk IDs
        
        Args:
            query_vector: Query vector
            filter_chunk_ids: Only return results from these chunk IDs
            k: Maximum number of results
        
        Returns:
            Filtered search results
        """
        # Get all results first
        similarities, faiss_indices, metadata_list = self.search(query_vector, k=min(1000, self.index.ntotal), return_metadata=True)
        
        # Filter by chunk IDs
        filtered_results = []
        for sim, f_idx, meta in zip(similarities, faiss_indices, metadata_list):
            if meta.get("chunk_id") in filter_chunk_ids:
                filtered_results.append((sim, f_idx, meta))
                if len(filtered_results) >= k:
                    break
        
        if not filtered_results:
            return [], [], []
        
        # Unpack results
        filtered_similarities, filtered_faiss_indices, filtered_metadata = zip(*filtered_results)
        return list(filtered_similarities), list(filtered_faiss_indices), list(filtered_metadata)
    
    def update_vector(self, faiss_index: int, new_vector: np.ndarray, new_metadata: Dict[str, Any] = None):
        """
        Update a vector at a specific FAISS index
        Note: FAISS doesn't support in-place updates, so this recreates the index
        """
        if faiss_index >= self.index.ntotal:
            raise ValueError(f"FAISS index {faiss_index} out of range (max: {self.index.ntotal - 1})")
        
        logger.warning("Vector update requires recreating FAISS index - this is expensive")
        
        # Get all current vectors (expensive operation)
        all_vectors = []
        for i in range(self.index.ntotal):
            # This is not efficient, but FAISS doesn't provide direct access to vectors
            # In practice, you'd rebuild the index from the database
            pass
        
        # TODO: Implement if needed - requires storing vectors separately or rebuilding from DB
        raise NotImplementedError("Vector updates require rebuilding the index from the database")
    
    def remove_vector(self, faiss_index: int):
        """
        Remove a vector from the index
        Note: FAISS doesn't support removal, so this marks as invalid
        """
        if faiss_index < len(self.metadata):
            self.metadata[faiss_index] = {"chunk_id": None, "deleted": True}
            logger.info(f"Marked vector at FAISS index {faiss_index} as deleted")
    
    def save_index(self):
        """Save the FAISS index and metadata to disk"""
        try:
            # Ensure directory exists
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            
            faiss.write_index(self.index, str(self.index_path))
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.metadata, f)
            logger.info(f"Saved FAISS index with {self.index.ntotal} vectors to {self.index_path}")
        except Exception as e:
            logger.error(f"Error saving FAISS index: {e}")
            raise
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics"""
        active_vectors = sum(1 for meta in self.metadata if not meta.get("deleted", False))
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "active_vectors": active_vectors,
            "embedding_dimension": self.dimension,
            "index_type": self.index_type,
            "index_size_mb": os.path.getsize(self.index_path) / (1024 * 1024) if self.index_path.exists() else 0,
        }
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics (async version for compatibility)"""
        return self.get_stats()
    
    @property
    def embedding_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension
    
    def rebuild_from_database(self, db_session: Session):
        """
        Rebuild FAISS index from database embeddings
        This is useful for recovery or when changing index parameters
        """
        logger.info("Rebuilding FAISS index from database...")
        
        # Create new index
        if self.index_type == "IndexFlatIP":
            self.index = faiss.IndexFlatIP(self.dimension)
        elif self.index_type == "IndexFlatL2":
            self.index = faiss.IndexFlatL2(self.dimension)
        else:
            raise ValueError(f"Unsupported index type for rebuild: {self.index_type}")
        
        self.metadata = []
        
        # Get all embeddings from database
        embeddings_query = db_session.query(Embedding).join(DocumentChunk).order_by(Embedding.id)
        
        batch_size = 1000
        vectors_batch = []
        chunk_ids_batch = []
        metadata_batch = []
        
        count = 0
        for embedding in embeddings_query:
            if embedding.vector_data:
                vector = np.array(embedding.vector_data, dtype=np.float32)
                vectors_batch.append(vector)
                chunk_ids_batch.append(embedding.chunk_id)
                metadata_batch.append({
                    "chunk_id": embedding.chunk_id,
                    "document_id": embedding.chunk.document_id,
                    "embedding_id": embedding.id,
                })
                count += 1
                
                # Process in batches
                if len(vectors_batch) >= batch_size:
                    vectors_array = np.vstack(vectors_batch)
                    self.add_vectors(vectors_array, chunk_ids_batch, metadata_batch)
                    vectors_batch = []
                    chunk_ids_batch = []
                    metadata_batch = []
        
        # Process remaining vectors
        if vectors_batch:
            vectors_array = np.vstack(vectors_batch)
            self.add_vectors(vectors_array, chunk_ids_batch, metadata_batch)
        
        logger.info(f"Rebuilt FAISS index with {count} vectors from database")
        self.save_index()


# Global vector service instance
vector_service = VectorService(dimension=settings.embedding_dimensions)