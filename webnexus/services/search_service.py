"""
Search Service

Hybrid search service combining vector similarity and keyword search for WebNexus.
Provides BM25 keyword search, vector similarity search, and hybrid ranking.
Supports multi-index search across different vector indexes.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..config.database import db_config
from ..models.database import Document, DocumentChunk, Embedding
from ..services.vector_service import vector_service
from ..services.embedding_service import embedding_service
from .keyword_extractor import keyword_extractor

logger = logging.getLogger(__name__)

# Import index_manager with lazy loading to avoid circular imports
_index_manager = None

def get_index_manager():
    """Lazy load index_manager to avoid circular imports"""
    global _index_manager
    if _index_manager is None:
        from ..services.index_manager import index_manager
        _index_manager = index_manager
    return _index_manager


@dataclass
class SearchResult:
    """Represents a single search result."""
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


@dataclass
class SearchResponse:
    """Represents the complete search response."""
    results: List[SearchResult]
    total_results: int
    query: str
    search_time_ms: float
    search_strategy: str


class SearchService:
    """
    Hybrid search service combining vector similarity and keyword search.
    
    Features:
    - Vector similarity search using FAISS
    - BM25 keyword search for exact term matching
    - Hybrid ranking combining both scores
    - Document and chunk-level search
    - Configurable result fusion strategies
    """
    
    def __init__(self):
        """Initialize search service."""
        self.bm25_index = None
        self.bm25_documents = []
        self.bm25_metadata = []
        self._last_rebuild = None
        self.rebuild_threshold_minutes = 30  # Rebuild BM25 every 30 minutes
        
    async def _ensure_bm25_index(self) -> None:
        """Ensure BM25 index is built and up-to-date."""
        now = datetime.utcnow()
        
        # Check if rebuild is needed
        if (self.bm25_index is None or 
            self._last_rebuild is None or
            (now - self._last_rebuild).seconds > self.rebuild_threshold_minutes * 60):
            
            await self._rebuild_bm25_index()
    
    async def _rebuild_bm25_index(self) -> None:
        """Rebuild BM25 index from database."""
        logger.info("Rebuilding BM25 index...")
        start_time = datetime.utcnow()
        
        db_session = db_config.get_session()
        try:
            # Get all document chunks for BM25 indexing
            chunks = db_session.query(DocumentChunk).join(Document).all()
            
            documents = []
            metadata = []
            
            for chunk in chunks:
                # Tokenize content for BM25 with sophisticated extraction
                content = chunk.content or ""
                # Extract keywords from document content for better indexing
                keywords = keyword_extractor.extract_keywords(content, max_keywords=50)
                search_terms = keyword_extractor.build_search_terms(keywords)
                # Fallback to simple split if no keywords extracted
                tokens = search_terms if search_terms else content.lower().split()
                documents.append(tokens)
                
                # Store metadata for result mapping
                metadata.append({
                    'chunk_id': chunk.id,
                    'document_id': chunk.document_id,
                    'title': chunk.document.title or "Untitled",
                    'url': chunk.document.url,
                    'content': content,
                    'source_type': chunk.document.crawl_type or "unknown",
                    'metadata': chunk.document.doc_metadata or {}
                })
            
            if documents:
                self.bm25_index = BM25Okapi(documents)
                self.bm25_documents = documents
                self.bm25_metadata = metadata
                self._last_rebuild = datetime.utcnow()
                
                build_time = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"BM25 index rebuilt with {len(documents)} documents in {build_time:.2f}s")
            else:
                logger.warning("No documents found for BM25 indexing")
                
        except Exception as e:
            logger.error(f"Error rebuilding BM25 index: {e}")
            raise
        finally:
            db_session.close()
    
    async def vector_search(
        self,
        query: str,
        top_k: int = 10,
        similarity_threshold: float = 0.0,
        index_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score
            index_name: Optional index name to search in (if None, uses global vector_service)
            
        Returns:
            List of search results with similarity scores
        """
        # Determine which vector service to use
        if index_name:
            index_mgr = get_index_manager()
            target_vector_service = index_mgr.get_vector_service(index_name)
        else:
            target_vector_service = vector_service
        
        try:
            # Generate query embedding
            query_embeddings = await embedding_service.embed_queries([query])
            query_vector = np.array(query_embeddings[0]).reshape(1, -1)
            
            # Search vector index
            similarities, faiss_indices, metadata_list = target_vector_service.search(
                query_vector,
                k=top_k * 2  # Get more results for better filtering
            )
            
            # Convert to result format
            vector_results = []
            for sim, f_idx, meta in zip(similarities, faiss_indices, metadata_list):
                vector_results.append({
                    'chunk_id': meta.get('chunk_id'),
                    'similarity': sim,
                    'faiss_index': f_idx,
                    'metadata': meta
                })
            
            if not vector_results:
                return []
            
            # Get document details from database
            db_session = db_config.get_session()
            try:
                results = []
                
                for result in vector_results:
                    chunk_id = result.get('chunk_id')
                    similarity = result.get('similarity', 0.0)
                    
                    if similarity < similarity_threshold:
                        continue
                    
                    # Get chunk and document details
                    chunk = db_session.query(DocumentChunk).filter(
                        DocumentChunk.id == chunk_id
                    ).first()
                    
                    if chunk and chunk.document:
                        results.append({
                            'chunk_id': chunk.id,
                            'document_id': chunk.document_id,
                            'title': chunk.document.title or "Untitled",
                            'url': chunk.document.url,
                            'content': chunk.content,
                            'similarity_score': similarity,
                            'source_type': chunk.document.crawl_type or "unknown",
                            'metadata': chunk.document.doc_metadata or {}
                        })
                
                return results[:top_k]
                
            finally:
                db_session.close()
                
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    async def keyword_search(
        self, 
        query: str, 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 keyword search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of search results with BM25 scores
        """
        try:
            await self._ensure_bm25_index()
            
            if not self.bm25_index or not self.bm25_documents:
                logger.warning("No BM25 index available")
                return []
            
            # Extract sophisticated keywords using keyword extractor
            keywords = keyword_extractor.extract_keywords(query, max_keywords=15)
            search_terms = keyword_extractor.build_search_terms(keywords)
            query_tokens = search_terms if search_terms else query.lower().split()
            
            # Get BM25 scores
            bm25_scores = self.bm25_index.get_scores(query_tokens)
            
            # Create results with scores
            results_with_scores = []
            for i, score in enumerate(bm25_scores):
                if score > 0 and i < len(self.bm25_metadata):
                    result = self.bm25_metadata[i].copy()
                    result['keyword_score'] = float(score)
                    results_with_scores.append(result)
            
            # Sort by BM25 score and return top results
            results_with_scores.sort(key=lambda x: x['keyword_score'], reverse=True)
            return results_with_scores[:top_k]
            
        except Exception as e:
            logger.error(f"Error in keyword search: {e}")
            return []
    
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.0,
        index_name: Optional[str] = None
    ) -> SearchResponse:
        """
        Perform hybrid search combining vector and keyword search.
        
        Args:
            query: Search query
            top_k: Number of results to return
            vector_weight: Weight for vector similarity scores (0.0-1.0)
            keyword_weight: Weight for keyword scores (0.0-1.0)
            similarity_threshold: Minimum similarity score for vector results
            index_name: Optional index name to search in (if None, searches global index)
            
        Returns:
            SearchResponse with combined results
        """
        start_time = datetime.utcnow()
        
        try:
            # Perform both searches in parallel
            vector_task = asyncio.create_task(
                self.vector_search(query, top_k * 2, similarity_threshold, index_name)
            )
            keyword_task = asyncio.create_task(
                self.keyword_search(query, top_k * 2)
            )
            
            vector_results, keyword_results = await asyncio.gather(
                vector_task, keyword_task
            )
            
            # Combine and rank results
            combined_results = self._combine_results(
                vector_results, 
                keyword_results,
                vector_weight,
                keyword_weight
            )
            
            # Convert to SearchResult objects
            search_results = []
            for result in combined_results[:top_k]:
                search_results.append(SearchResult(
                    document_id=str(result['document_id']),
                    chunk_id=str(result.get('chunk_id')) if result.get('chunk_id') is not None else None,
                    title=result['title'],
                    content=result['content'][:500] + "..." if len(result['content']) > 500 else result['content'],
                    url=result['url'],
                    similarity_score=result.get('similarity_score', 0.0),
                    keyword_score=result.get('keyword_score', 0.0),
                    combined_score=result['combined_score'],
                    metadata=result.get('metadata', {}),
                    source_type=result.get('source_type', 'unknown')
                ))
            
            # Calculate search time
            search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=search_results,
                total_results=len(combined_results),
                query=query,
                search_time_ms=search_time,
                search_strategy="hybrid"
            )
            
        except Exception as e:
            logger.error(f"Error in hybrid search: {e}")
            search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=[],
                total_results=0,
                query=query,
                search_time_ms=search_time,
                search_strategy="hybrid"
            )
    
    def _combine_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        vector_weight: float,
        keyword_weight: float
    ) -> List[Dict[str, Any]]:
        """
        Combine vector and keyword search results with weighted scoring.
        
        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            vector_weight: Weight for vector scores
            keyword_weight: Weight for keyword scores
            
        Returns:
            Combined and ranked results
        """
        # Normalize scores to 0-1 range
        vector_scores = [r.get('similarity_score', 0.0) for r in vector_results]
        keyword_scores = [r.get('keyword_score', 0.0) for r in keyword_results]
        
        # Min-max normalization
        if vector_scores:
            vec_min, vec_max = min(vector_scores), max(vector_scores)
            if vec_max > vec_min:
                for result in vector_results:
                    score = result.get('similarity_score', 0.0)
                    result['similarity_score_norm'] = (score - vec_min) / (vec_max - vec_min)
            else:
                for result in vector_results:
                    result['similarity_score_norm'] = 1.0 if vec_max > 0 else 0.0
        
        if keyword_scores:
            key_min, key_max = min(keyword_scores), max(keyword_scores)
            if key_max > key_min:
                for result in keyword_results:
                    score = result.get('keyword_score', 0.0)
                    result['keyword_score_norm'] = (score - key_min) / (key_max - key_min)
            else:
                for result in keyword_results:
                    result['keyword_score_norm'] = 1.0 if key_max > 0 else 0.0
        
        # Create combined result dictionary
        combined_dict = {}
        
        # Add vector results
        for result in vector_results:
            key = (result['document_id'], result.get('chunk_id'))
            combined_dict[key] = result.copy()
            combined_dict[key]['similarity_score_norm'] = result.get('similarity_score_norm', 0.0)
            combined_dict[key]['keyword_score_norm'] = 0.0
        
        # Add keyword results (merge or add)
        for result in keyword_results:
            key = (result['document_id'], result.get('chunk_id'))
            if key in combined_dict:
                # Merge with existing result
                combined_dict[key]['keyword_score'] = result.get('keyword_score', 0.0)
                combined_dict[key]['keyword_score_norm'] = result.get('keyword_score_norm', 0.0)
            else:
                # Add new result
                combined_dict[key] = result.copy()
                combined_dict[key]['similarity_score'] = 0.0
                combined_dict[key]['similarity_score_norm'] = 0.0
                combined_dict[key]['keyword_score_norm'] = result.get('keyword_score_norm', 0.0)
        
        # Calculate combined scores
        for result in combined_dict.values():
            vec_score = result.get('similarity_score_norm', 0.0)
            key_score = result.get('keyword_score_norm', 0.0)
            result['combined_score'] = (vec_score * vector_weight) + (key_score * keyword_weight)
        
        # Sort by combined score
        combined_results = list(combined_dict.values())
        combined_results.sort(key=lambda x: x['combined_score'], reverse=True)
        
        return combined_results
    
    async def search_documents_by_url(
        self, 
        url_pattern: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search documents by URL pattern.
        
        Args:
            url_pattern: URL pattern to match
            limit: Maximum number of results
            
        Returns:
            List of matching documents
        """
        db_session = db_config.get_session()
        try:
            documents = db_session.query(Document).filter(
                Document.url.like(f"%{url_pattern}%")
            ).limit(limit).all()
            
            results = []
            for doc in documents:
                results.append({
                    'document_id': doc.id,
                    'title': doc.title,
                    'url': doc.url,
                    'source_type': doc.crawl_type,
                    'created_at': doc.created_at.isoformat() if doc.created_at else None,
                    'metadata': doc.doc_metadata or {}
                })
            
            return results
            
        finally:
            db_session.close()
    
    async def hybrid_search_with_reranking(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        similarity_threshold: float = 0.0,
        rerank_strategy: str = "hybrid",
        use_reranking: bool = True,
        index_name: Optional[str] = None
    ) -> SearchResponse:
        """
        Perform hybrid search with optional reranking for improved results.
        
        Args:
            query: Search query
            top_k: Number of results to return
            vector_weight: Weight for vector similarity scores
            keyword_weight: Weight for keyword scores
            similarity_threshold: Minimum similarity score for vector results
            rerank_strategy: Reranking strategy to use ("bm25", "hybrid", "quality")
            use_reranking: Whether to apply reranking to results
            
        Returns:
            SearchResponse with optionally reranked results
        """
        start_time = datetime.utcnow()
        
        try:
            # Perform initial hybrid search with more results for reranking
            initial_top_k = top_k * 3 if use_reranking else top_k
            search_response = await self.hybrid_search(
                query,
                initial_top_k,
                vector_weight,
                keyword_weight,
                similarity_threshold,
                index_name
            )
            
            if not use_reranking or not search_response.results:
                # Return original results without reranking
                search_response.results = search_response.results[:top_k]
                search_response.search_strategy = "hybrid"
                return search_response
            
            # Import reranking service here to avoid circular imports
            from .reranking_service import reranking_service
            
            # Convert SearchResult objects back to dictionaries for reranking
            results_for_rerank = []
            for result in search_response.results:
                results_for_rerank.append({
                    'document_id': result.document_id,
                    'chunk_id': result.chunk_id,
                    'title': result.title,
                    'content': result.content,
                    'url': result.url,
                    'similarity_score': result.similarity_score,
                    'keyword_score': result.keyword_score,
                    'combined_score': result.combined_score,
                    'metadata': result.metadata,
                    'source_type': result.source_type
                })
            
            # Apply reranking
            reranked_results = await reranking_service.rerank_results(
                query,
                results_for_rerank,
                top_k,
                rerank_strategy
            )
            
            # Convert reranked results back to SearchResult objects
            final_results = []
            for rerank_result in reranked_results:
                final_results.append(SearchResult(
                    document_id=str(rerank_result.document_id),
                    chunk_id=str(rerank_result.chunk_id) if rerank_result.chunk_id is not None else None,
                    title=rerank_result.title,
                    content=rerank_result.content,
                    url=rerank_result.url,
                    similarity_score=results_for_rerank[0].get('similarity_score', 0.0),  # Keep original
                    keyword_score=results_for_rerank[0].get('keyword_score', 0.0),  # Keep original
                    combined_score=rerank_result.final_score,  # Use reranked score
                    metadata=rerank_result.metadata,
                    source_type=results_for_rerank[0].get('source_type', 'unknown')
                ))
            
            # Calculate total search time
            total_search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=final_results,
                total_results=len(final_results),
                query=query,
                search_time_ms=total_search_time,
                search_strategy=f"hybrid+{rerank_strategy}_rerank"
            )
            
        except Exception as e:
            logger.error(f"Error in hybrid search with reranking: {e}")
            # Fallback to regular hybrid search
            return await self.hybrid_search(
                query, top_k, vector_weight, keyword_weight, similarity_threshold
            )

    async def search_in_index(
        self,
        index_name: str,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",
        use_reranking: bool = False,
        rerank_strategy: str = "hybrid"
    ) -> SearchResponse:
        """
        Search within a specific vector index.
        
        Args:
            index_name: Name of the vector index to search
            query: Search query
            top_k: Number of results to return
            search_type: Type of search ("vector", "keyword", or "hybrid")
            use_reranking: Whether to apply reranking
            rerank_strategy: Reranking strategy to use
            
        Returns:
            SearchResponse with results from the specified index
        """
        if search_type == "vector":
            results = await self.vector_search(query, top_k, index_name=index_name)
            return SearchResponse(
                results=[SearchResult(
                    document_id=str(r['document_id']),
                    chunk_id=str(r.get('chunk_id')) if r.get('chunk_id') else None,
                    title=r['title'],
                    content=r['content'][:500] + "..." if len(r['content']) > 500 else r['content'],
                    url=r['url'],
                    similarity_score=r.get('similarity_score', 0.0),
                    keyword_score=0.0,
                    combined_score=r.get('similarity_score', 0.0),
                    metadata=r.get('metadata', {}),
                    source_type=r.get('source_type', 'unknown')
                ) for r in results],
                total_results=len(results),
                query=query,
                search_time_ms=0.0,
                search_strategy=f"vector_index:{index_name}"
            )
        elif search_type == "hybrid":
            if use_reranking:
                return await self.hybrid_search_with_reranking(
                    query, top_k, index_name=index_name,
                    rerank_strategy=rerank_strategy, use_reranking=True
                )
            else:
                return await self.hybrid_search(query, top_k, index_name=index_name)
        else:
            # Keyword search doesn't depend on index
            results = await self.keyword_search(query, top_k)
            return SearchResponse(
                results=[SearchResult(
                    document_id=str(r['document_id']),
                    chunk_id=str(r.get('chunk_id')) if r.get('chunk_id') else None,
                    title=r['title'],
                    content=r['content'][:500] + "..." if len(r['content']) > 500 else r['content'],
                    url=r['url'],
                    similarity_score=0.0,
                    keyword_score=r.get('keyword_score', 0.0),
                    combined_score=r.get('keyword_score', 0.0),
                    metadata=r.get('metadata', {}),
                    source_type=r.get('source_type', 'unknown')
                ) for r in results],
                total_results=len(results),
                query=query,
                search_time_ms=0.0,
                search_strategy="keyword"
            )

    async def search_all_indexes(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",
        use_reranking: bool = False,
        rerank_strategy: str = "hybrid"
    ) -> SearchResponse:
        """
        Search across all active vector indexes and combine results.
        
        Args:
            query: Search query
            top_k: Number of results to return
            search_type: Type of search ("vector", "keyword", or "hybrid")
            use_reranking: Whether to apply reranking
            rerank_strategy: Reranking strategy to use
            
        Returns:
            SearchResponse with combined results from all indexes
        """
        start_time = datetime.utcnow()
        
        try:
            index_mgr = get_index_manager()
            indexes = index_mgr.list_indexes(active_only=True)
            
            if not indexes:
                # No indexes, fall back to global search
                return await self.search_in_index(
                    "default", query, top_k, search_type, use_reranking, rerank_strategy
                )
            
            # Search all indexes in parallel
            search_tasks = []
            for index in indexes:
                task = self.search_in_index(
                    str(index.name), query, top_k * 2,  # Get more results for merging
                    search_type, use_reranking=False  # Don't rerank individual results
                )
                search_tasks.append(task)
            
            # Wait for all searches to complete
            all_responses = await asyncio.gather(*search_tasks, return_exceptions=True)
            
            # Combine results from all indexes
            combined_results = []
            for response in all_responses:
                if isinstance(response, SearchResponse):
                    combined_results.extend(response.results)
            
            # Sort by combined score and take top_k
            combined_results.sort(key=lambda x: x.combined_score, reverse=True)
            final_results = combined_results[:top_k]
            
            # Apply reranking if requested
            if use_reranking and final_results:
                from .reranking_service import reranking_service
                
                # Convert to dict format for reranking
                results_for_rerank = [{
                    'document_id': r.document_id,
                    'chunk_id': r.chunk_id,
                    'title': r.title,
                    'content': r.content,
                    'url': r.url,
                    'similarity_score': r.similarity_score,
                    'keyword_score': r.keyword_score,
                    'combined_score': r.combined_score,
                    'metadata': r.metadata,
                    'source_type': r.source_type
                } for r in final_results]
                
                reranked = await reranking_service.rerank_results(
                    query, results_for_rerank, top_k, rerank_strategy
                )
                
                final_results = [SearchResult(
                    document_id=str(r.document_id),
                    chunk_id=str(r.chunk_id) if r.chunk_id else None,
                    title=r.title,
                    content=r.content,
                    url=r.url,
                    similarity_score=r.similarity_score,
                    keyword_score=r.keyword_score,
                    combined_score=r.final_score,
                    metadata=r.metadata,
                    source_type=r.source_type
                ) for r in reranked]
            
            search_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return SearchResponse(
                results=final_results,
                total_results=len(combined_results),
                query=query,
                search_time_ms=search_time,
                search_strategy=f"all_indexes_{search_type}" + (f"+{rerank_strategy}_rerank" if use_reranking else "")
            )
            
        except Exception as e:
            logger.error(f"Error searching all indexes: {e}")
            # Fallback to global search
            return await self.hybrid_search(query, top_k)

    async def get_document_stats(self) -> Dict[str, Any]:
        """
        Get search service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        db_session = db_config.get_session()
        try:
            doc_count = db_session.query(Document).count()
            chunk_count = db_session.query(DocumentChunk).count()
            embedding_count = db_session.query(Embedding).count()
            
            return {
                'total_documents': doc_count,
                'total_chunks': chunk_count,
                'total_embeddings': embedding_count,
                'bm25_indexed_documents': len(self.bm25_documents) if self.bm25_documents else 0,
                'last_bm25_rebuild': self._last_rebuild.isoformat() if self._last_rebuild else None,
                'vector_index_size': vector_service.index.ntotal if vector_service.index else 0
            }
            
        finally:
            db_session.close()


# Global search service instance
search_service = SearchService()