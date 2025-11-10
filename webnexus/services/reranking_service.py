"""
Reranking Service

Advanced reranking service for WebNexus using multiple strategies.
Combines BM25 keyword scoring with vector similarity for improved ranking.
"""

import logging
import math
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

import numpy as np
from rank_bm25 import BM25Okapi
from .keyword_extractor import keyword_extractor

logger = logging.getLogger(__name__)


@dataclass
class RerankResult:
    """Represents a reranked result."""
    document_id: str
    chunk_id: Optional[str]
    title: str
    content: str
    url: str
    original_score: float
    rerank_score: float
    final_score: float
    rank_position: int
    metadata: Dict[str, Any]


class RerankingService:
    """
    Advanced reranking service that improves search result ordering.
    
    Features:
    - BM25-based keyword relevance scoring
    - Vector similarity score fusion
    - Query-document relevance analysis
    - Position-aware score normalization
    - Configurable ranking strategies
    """
    
    def __init__(self):
        """Initialize reranking service."""
        self.bm25_cache = {}
        self.cache_ttl = 3600  # 1 hour cache
        
    def _create_bm25_index(self, documents: List[str]) -> BM25Okapi:
        """
        Create BM25 index for a set of documents.
        
        Args:
            documents: List of document texts
            
        Returns:
            BM25Okapi index
        """
        try:
            # Tokenize documents with sophisticated keyword extraction
            tokenized_docs = []
            for doc in documents:
                # Enhanced tokenization using keyword extractor
                keywords = keyword_extractor.extract_keywords(doc, max_keywords=50)
                search_terms = keyword_extractor.build_search_terms(keywords)
                tokens = search_terms if search_terms else doc.lower().split()
                tokenized_docs.append(tokens)
            
            return BM25Okapi(tokenized_docs)
            
        except Exception as e:
            logger.error(f"Error creating BM25 index: {e}")
            return None
    
    def _calculate_query_coverage(self, query: str, content: str) -> float:
        """
        Calculate how well the content covers the query terms.
        
        Args:
            query: Search query
            content: Document content
            
        Returns:
            Coverage score between 0 and 1
        """
        try:
            # Extract meaningful keywords for both query and content
            query_keywords = keyword_extractor.extract_keywords(query, max_keywords=15)
            query_terms = keyword_extractor.build_search_terms(query_keywords)
            query_tokens = set(query_terms if query_terms else query.lower().split())
            
            content_keywords = keyword_extractor.extract_keywords(content, max_keywords=50)
            content_terms = keyword_extractor.build_search_terms(content_keywords)
            content_tokens = set(content_terms if content_terms else content.lower().split())
            
            if not query_tokens:
                return 0.0
            
            # Calculate term coverage
            covered_terms = query_tokens.intersection(content_tokens)
            coverage = len(covered_terms) / len(query_tokens)
            
            return coverage
            
        except Exception as e:
            logger.warning(f"Error calculating query coverage: {e}")
            return 0.0
    
    def _calculate_content_quality_score(self, content: str) -> float:
        """
        Calculate a content quality score based on various factors.
        
        Args:
            content: Document content
            
        Returns:
            Quality score between 0 and 1
        """
        try:
            if not content:
                return 0.0
            
            # Factors for content quality
            length_score = min(len(content) / 1000, 1.0)  # Favor longer content up to 1000 chars
            word_count = len(content.split())
            word_score = min(word_count / 200, 1.0)  # Favor more words up to 200
            
            # Penalty for very short content
            if len(content) < 50:
                return 0.1
            
            # Average the scores
            quality_score = (length_score + word_score) / 2
            return quality_score
            
        except Exception as e:
            logger.warning(f"Error calculating content quality: {e}")
            return 0.5
    
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """
        Normalize scores to 0-1 range using min-max normalization.
        
        Args:
            scores: List of scores to normalize
            
        Returns:
            Normalized scores
        """
        if not scores:
            return []
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            # All scores are the same
            return [1.0] * len(scores)
        
        # Min-max normalization
        normalized = [(score - min_score) / (max_score - min_score) for score in scores]
        return normalized
    
    async def rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10,
        strategy: str = "hybrid"
    ) -> List[RerankResult]:
        """
        Rerank search results using the specified strategy.
        
        Args:
            query: Original search query
            results: List of search results to rerank
            top_k: Number of top results to return
            strategy: Reranking strategy ("bm25", "hybrid", "quality")
            
        Returns:
            List of reranked results
        """
        if not results:
            return []
        
        try:
            start_time = datetime.utcnow()
            
            # Extract content for reranking
            documents = [result.get('content', '') for result in results]
            
            # Calculate different scoring components
            rerank_scores = []
            
            if strategy in ["bm25", "hybrid"]:
                # BM25 relevance scores
                bm25_index = self._create_bm25_index(documents)
                if bm25_index:
                    # Enhanced query tokenization
                    query_keywords = keyword_extractor.extract_keywords(query, max_keywords=15)
                    query_terms = keyword_extractor.build_search_terms(query_keywords)
                    query_tokens = query_terms if query_terms else query.lower().split()
                    bm25_scores = bm25_index.get_scores(query_tokens)
                    bm25_scores = self._normalize_scores(bm25_scores.tolist())
                else:
                    bm25_scores = [0.5] * len(results)
            else:
                bm25_scores = [0.5] * len(results)
            
            # Calculate additional scoring factors
            coverage_scores = []
            quality_scores = []
            
            for i, result in enumerate(results):
                content = result.get('content', '')
                
                # Query coverage score
                coverage = self._calculate_query_coverage(query, content)
                coverage_scores.append(coverage)
                
                # Content quality score
                quality = self._calculate_content_quality_score(content)
                quality_scores.append(quality)
            
            # Combine scores based on strategy
            for i, result in enumerate(results):
                original_score = result.get('combined_score', 
                                         result.get('similarity_score', 
                                                   result.get('keyword_score', 0.0)))
                
                if strategy == "bm25":
                    # Pure BM25 reranking
                    final_score = bm25_scores[i]
                elif strategy == "quality":
                    # Focus on content quality
                    final_score = (original_score * 0.4 + 
                                 coverage_scores[i] * 0.3 + 
                                 quality_scores[i] * 0.3)
                else:  # hybrid (default)
                    # Hybrid approach combining all factors
                    final_score = (original_score * 0.4 +
                                 bm25_scores[i] * 0.3 +
                                 coverage_scores[i] * 0.2 +
                                 quality_scores[i] * 0.1)
                
                rerank_scores.append(final_score)
            
            # Create reranked results
            reranked_items = []
            for i, (result, score) in enumerate(zip(results, rerank_scores)):
                reranked_items.append({
                    'result': result,
                    'rerank_score': score,
                    'original_index': i
                })
            
            # Sort by rerank score
            reranked_items.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            # Convert to RerankResult objects
            rerank_results = []
            for rank_pos, item in enumerate(reranked_items[:top_k]):
                result = item['result']
                rerank_results.append(RerankResult(
                    document_id=result.get('document_id', ''),
                    chunk_id=result.get('chunk_id'),
                    title=result.get('title', ''),
                    content=result.get('content', '')[:500] + "..." if len(result.get('content', '')) > 500 else result.get('content', ''),
                    url=result.get('url', ''),
                    original_score=result.get('combined_score', 
                                           result.get('similarity_score', 
                                                     result.get('keyword_score', 0.0))),
                    rerank_score=item['rerank_score'],
                    final_score=item['rerank_score'],
                    rank_position=rank_pos + 1,
                    metadata=result.get('metadata', {})
                ))
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.info(f"Reranked {len(results)} results in {processing_time:.3f}s using {strategy} strategy")
            
            return rerank_results
            
        except Exception as e:
            logger.error(f"Error in reranking: {e}")
            # Return original results as fallback
            fallback_results = []
            for i, result in enumerate(results[:top_k]):
                fallback_results.append(RerankResult(
                    document_id=result.get('document_id', ''),
                    chunk_id=result.get('chunk_id'),
                    title=result.get('title', ''),
                    content=result.get('content', '')[:500] + "..." if len(result.get('content', '')) > 500 else result.get('content', ''),
                    url=result.get('url', ''),
                    original_score=result.get('combined_score', 
                                           result.get('similarity_score', 
                                                     result.get('keyword_score', 0.0))),
                    rerank_score=result.get('combined_score', 0.0),
                    final_score=result.get('combined_score', 0.0),
                    rank_position=i + 1,
                    metadata=result.get('metadata', {})
                ))
            return fallback_results
    
    async def rerank_with_query_expansion(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 10
    ) -> List[RerankResult]:
        """
        Rerank results with query expansion for better relevance.
        
        Args:
            query: Original search query
            results: Search results to rerank
            top_k: Number of results to return
            
        Returns:
            Reranked results with expanded query matching
        """
        try:
            # Enhanced query expansion using keyword extraction
            initial_keywords = keyword_extractor.extract_keywords(query, max_keywords=10)
            expanded_terms = set(keyword_extractor.build_search_terms(initial_keywords))
            
            # Extract frequent terms from top 3 results for expansion
            for result in results[:3]:
                content = result.get('content', '').lower()
                words = content.split()
                # Add words that appear multiple times and are longer than 3 chars
                word_counts = {}
                for word in words:
                    if len(word) > 3:
                        word_counts[word] = word_counts.get(word, 0) + 1
                
                # Add frequent words as expansion terms
                for word, count in word_counts.items():
                    if count >= 2 and word not in expanded_terms:
                        expanded_terms.add(word)
                        if len(expanded_terms) >= len(query.split()) * 3:  # Limit expansion
                            break
            
            expanded_query = ' '.join(expanded_terms)
            logger.info(f"Expanded query: '{query}' -> '{expanded_query}'")
            
            # Rerank with expanded query
            return await self.rerank_results(
                expanded_query, 
                results, 
                top_k, 
                strategy="hybrid"
            )
            
        except Exception as e:
            logger.error(f"Error in query expansion reranking: {e}")
            # Fallback to regular reranking
            return await self.rerank_results(query, results, top_k)
    
    def get_reranking_stats(self) -> Dict[str, Any]:
        """
        Get reranking service statistics.
        
        Returns:
            Dictionary with service statistics
        """
        return {
            'cache_size': len(self.bm25_cache),
            'cache_ttl_seconds': self.cache_ttl,
            'available_strategies': ["bm25", "hybrid", "quality"],
            'features': [
                "BM25 keyword relevance",
                "Query coverage analysis", 
                "Content quality scoring",
                "Hybrid score fusion",
                "Query expansion"
            ]
        }


# Global reranking service instance
reranking_service = RerankingService()