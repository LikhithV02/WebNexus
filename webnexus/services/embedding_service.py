"""Embedding service using sentence-transformers (Stella EN 400M v5)"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
import torch

from sentence_transformers import SentenceTransformer

from ..config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Stella EN 400M v5 embedding service with query/document prompt support"""
    
    def __init__(self, 
                 model_name: str = "dunzhang/stella_en_400M_v5",
                 device: str = "auto",
                 dimension: int = 1024,
                 batch_size: int = 100):
        """
        Initialize the embedding service
        
        Args:
            model_name: HuggingFace model name
            device: Device to use (auto, cpu, cuda)
            dimension: Embedding dimension
            batch_size: Batch size for processing
        """
        self.model_name = model_name
        self.dimension = dimension
        self.batch_size = batch_size
        self.model = None
        
        # Device selection
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Model cache directory - use absolute path from project root
        project_root = Path(__file__).parent.parent.parent
        self.cache_dir = project_root / "data" / "models"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self._stats = {
            "total_embeddings": 0,
            "total_time": 0.0,
            "model_load_time": 0.0,
            "last_batch_time": 0.0,
        }
        
        logger.info(f"Initialized EmbeddingService with model: {model_name} on {self.device}")
    
    def _load_model(self):
        """Load the sentence-transformers model"""
        if self.model is not None:
            return
        
        start_time = time.time()
        logger.info(f"Loading model: {self.model_name} on {self.device}")
        
        try:
            if self.device == "cuda":
                # GPU configuration
                self.model = SentenceTransformer(
                    self.model_name, 
                    trust_remote_code=True,
                    cache_folder=str(self.cache_dir)
                ).cuda()
            else:
                # CPU configuration with memory optimizations
                self.model = SentenceTransformer(
                    self.model_name,
                    trust_remote_code=True,
                    device="cpu",
                    cache_folder=str(self.cache_dir),
                    config_kwargs={
                        "use_memory_efficient_attention": False, 
                        "unpad_inputs": False
                    }
                )
            
            load_time = time.time() - start_time
            self._stats["model_load_time"] = load_time
            
            logger.info(f"Model loaded successfully in {load_time:.2f}s")
            
            # Verify model dimension
            test_embedding = self.model.encode(["test"], convert_to_numpy=True)
            actual_dim = test_embedding.shape[1]
            
            if actual_dim != self.dimension:
                logger.warning(f"Model dimension {actual_dim} != expected {self.dimension}")
                self.dimension = actual_dim
            
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise RuntimeError(f"Failed to load embedding model: {e}")
    
    async def embed_queries(self, queries: List[str]) -> List[List[float]]:
        """
        Embed query texts using s2p_query prompt (sentence-to-passage)
        
        Args:
            queries: List of query strings
        
        Returns:
            List of embedding vectors
        """
        if not queries:
            return []
        
        self._load_model()
        
        start_time = time.time()
        
        try:
            # Use s2p_query prompt for better retrieval performance
            embeddings = self.model.encode(
                queries, 
                prompt_name="s2p_query",
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(queries) > 10
            )
            
            # Convert to list of lists
            result = embeddings.tolist()
            
            # Update stats
            elapsed = time.time() - start_time
            self._stats["total_embeddings"] += len(queries)
            self._stats["total_time"] += elapsed
            self._stats["last_batch_time"] = elapsed
            
            logger.info(f"Embedded {len(queries)} queries in {elapsed:.2f}s ({len(queries)/elapsed:.1f} queries/s)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to embed queries: {e}")
            raise RuntimeError(f"Query embedding failed: {e}")
    
    async def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """
        Embed document texts (no prompt needed for documents)
        
        Args:
            documents: List of document strings
        
        Returns:
            List of embedding vectors
        """
        if not documents:
            return []
        
        self._load_model()
        
        start_time = time.time()
        
        try:
            # Documents don't need prompts in Stella model
            embeddings = self.model.encode(
                documents,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(documents) > 10
            )
            
            # Convert to list of lists
            result = embeddings.tolist()
            
            # Update stats
            elapsed = time.time() - start_time
            self._stats["total_embeddings"] += len(documents)
            self._stats["total_time"] += elapsed
            self._stats["last_batch_time"] = elapsed
            
            logger.info(f"Embedded {len(documents)} documents in {elapsed:.2f}s ({len(documents)/elapsed:.1f} docs/s)")
            return result
            
        except Exception as e:
            logger.error(f"Failed to embed documents: {e}")
            raise RuntimeError(f"Document embedding failed: {e}")
    
    async def embed_batch(
        self, 
        texts: List[str], 
        text_type: str = "document",
        progress_callback: Optional[callable] = None
    ) -> List[List[float]]:
        """
        Embed a batch of texts with progress tracking
        
        Args:
            texts: List of text strings
            text_type: "query" or "document" (affects prompting)
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        if text_type == "query":
            return await self.embed_queries(texts)
        else:
            # Process in batches for better memory management
            all_embeddings = []
            total_batches = (len(texts) + self.batch_size - 1) // self.batch_size
            
            for i in range(0, len(texts), self.batch_size):
                batch_texts = texts[i:i + self.batch_size]
                batch_embeddings = await self.embed_documents(batch_texts)
                all_embeddings.extend(batch_embeddings)
                
                # Progress callback
                if progress_callback:
                    batch_num = i // self.batch_size + 1
                    progress = (batch_num / total_batches) * 100
                    await progress_callback(
                        f"Processed batch {batch_num}/{total_batches}",
                        progress
                    )
            
            return all_embeddings
    
    def compute_similarity(self, embeddings1: List[List[float]], embeddings2: List[List[float]]) -> np.ndarray:
        """
        Compute cosine similarity between two sets of embeddings
        
        Args:
            embeddings1: First set of embeddings
            embeddings2: Second set of embeddings
        
        Returns:
            Similarity matrix
        """
        if not self.model:
            self._load_model()
        
        # Convert to tensors
        emb1 = torch.tensor(embeddings1)
        emb2 = torch.tensor(embeddings2)
        
        # Use model's similarity function if available
        if hasattr(self.model, 'similarity'):
            similarities = self.model.similarity(emb1, emb2)
            return similarities.cpu().numpy()
        else:
            # Manual cosine similarity
            emb1_norm = emb1 / emb1.norm(dim=1, keepdim=True)
            emb2_norm = emb2 / emb2.norm(dim=1, keepdim=True)
            similarities = torch.mm(emb1_norm, emb2_norm.transpose(0, 1))
            return similarities.cpu().numpy()
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model"""
        if not self.model:
            self._load_model()
        
        return {
            "model_name": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "max_sequence_length": getattr(self.model, 'max_seq_length', 'unknown'),
            "supports_prompts": True,  # Stella model supports prompts
            "prompt_names": ["s2p_query", "s2s_query"] if "stella" in self.model_name.lower() else [],
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        stats = self._stats.copy()
        
        # Calculate derived metrics
        if stats["total_time"] > 0:
            stats["avg_embeddings_per_second"] = stats["total_embeddings"] / stats["total_time"]
        else:
            stats["avg_embeddings_per_second"] = 0
        
        if stats["last_batch_time"] > 0:
            stats["last_batch_embeddings_per_second"] = self.batch_size / stats["last_batch_time"]
        else:
            stats["last_batch_embeddings_per_second"] = 0
        
        # Memory usage (if CUDA available)
        if torch.cuda.is_available() and self.device == "cuda":
            stats["gpu_memory_allocated"] = torch.cuda.memory_allocated() / (1024**3)  # GB
            stats["gpu_memory_reserved"] = torch.cuda.memory_reserved() / (1024**3)    # GB
        
        return stats
    
    def clear_cache(self):
        """Clear model cache and free memory"""
        if self.model is not None:
            del self.model
            self.model = None
            
            # Clear GPU cache if available
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Model cache cleared")
    
    async def warmup(self, sample_texts: Optional[List[str]] = None):
        """
        Warm up the model with sample texts
        
        Args:
            sample_texts: Optional sample texts. If None, uses default samples
        """
        if sample_texts is None:
            sample_texts = [
                "This is a sample document for warming up the embedding model.",
                "Another example text to ensure the model is properly loaded.",
                "What is the main purpose of this document?",  # Query example
            ]
        
        logger.info("Warming up embedding model...")
        
        # Warm up with documents
        await self.embed_documents(sample_texts[:2])
        
        # Warm up with queries
        await self.embed_queries([sample_texts[2]])
        
        logger.info("Model warmup completed")


# Global embedding service instance
embedding_service = EmbeddingService(
    model_name=settings.embedding_model,
    device=settings.embedding_device,
    dimension=settings.embedding_dimensions,
    batch_size=settings.embedding_batch_size
)