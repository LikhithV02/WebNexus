"""
Similarity Calculator

Provides cosine similarity calculations for text chunks.
Used in chunking merge decisions (threshold: >=80% similarity).
"""

import re
import math
import logging
from typing import List, Dict, Set, Tuple, Optional
from collections import Counter

logger = logging.getLogger(__name__)


class SimilarityCalculator:
    """
    Calculate semantic similarity between text chunks.

    Uses TF-IDF based cosine similarity for efficient, accurate results.
    Optimized for documentation text with technical terms.
    """

    def __init__(self, use_stemming: bool = False, stop_words: Optional[Set[str]] = None):
        """
        Initialize similarity calculator.

        Args:
            use_stemming: Whether to apply basic stemming (slower but more accurate)
            stop_words: Set of stop words to ignore (defaults to common English words)
        """
        self.use_stemming = use_stemming
        self.stop_words = stop_words or self._get_default_stop_words()

        # Cache for TF-IDF calculations
        self._idf_cache: Dict[str, float] = {}

    def _get_default_stop_words(self) -> Set[str]:
        """Get default set of English stop words"""
        return {
            'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
            'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
            'to', 'was', 'will', 'with', 'this', 'but', 'they', 'have', 'had',
            'what', 'when', 'where', 'who', 'which', 'why', 'how'
        }

    def tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.

        Args:
            text: Text to tokenize

        Returns:
            List of tokens (lowercase, alphanumeric)
        """
        # Convert to lowercase and extract words (including underscores for code)
        tokens = re.findall(r'\b\w+\b', text.lower())

        # Filter out stop words and very short tokens
        tokens = [
            token for token in tokens
            if token not in self.stop_words and len(token) > 1
        ]

        # Apply basic stemming if enabled
        if self.use_stemming:
            tokens = [self._simple_stem(token) for token in tokens]

        return tokens

    def _simple_stem(self, word: str) -> str:
        """
        Apply simple suffix-based stemming.

        Args:
            word: Word to stem

        Returns:
            Stemmed word
        """
        # Remove common suffixes
        suffixes = ['ing', 'ed', 'es', 's', 'ly', 'er', 'est']

        for suffix in suffixes:
            if word.endswith(suffix) and len(word) > len(suffix) + 2:
                return word[:-len(suffix)]

        return word

    def compute_tf(self, tokens: List[str]) -> Dict[str, float]:
        """
        Compute term frequency (TF) for tokens.

        Args:
            tokens: List of tokens

        Returns:
            Dictionary mapping token to TF score
        """
        if not tokens:
            return {}

        token_counts = Counter(tokens)
        max_count = max(token_counts.values())

        # Normalized TF: frequency / max frequency
        tf = {token: count / max_count for token, count in token_counts.items()}

        return tf

    def compute_cosine_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.

        Uses TF-based vector representation (simplified TF-IDF without corpus).

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not text1 or not text2:
            return 0.0

        # Tokenize both texts
        tokens1 = self.tokenize(text1)
        tokens2 = self.tokenize(text2)

        if not tokens1 or not tokens2:
            return 0.0

        # Compute TF for both texts
        tf1 = self.compute_tf(tokens1)
        tf2 = self.compute_tf(tokens2)

        # Get all unique tokens
        all_tokens = set(tf1.keys()) | set(tf2.keys())

        if not all_tokens:
            return 0.0

        # Create vectors
        vec1 = [tf1.get(token, 0.0) for token in all_tokens]
        vec2 = [tf2.get(token, 0.0) for token in all_tokens]

        # Compute cosine similarity
        similarity = self._cosine_similarity(vec1, vec2)

        return similarity

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        if len(vec1) != len(vec2):
            raise ValueError("Vectors must have same length")

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        # Cosine similarity
        similarity = dot_product / (magnitude1 * magnitude2)

        # Clamp to [0, 1] range (should already be, but floating point errors)
        return max(0.0, min(1.0, similarity))

    def compute_jaccard_similarity(self, text1: str, text2: str) -> float:
        """
        Compute Jaccard similarity between two texts.

        Faster but less accurate than cosine similarity.
        Good for quick comparisons.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Jaccard similarity (0.0 to 1.0)
        """
        if not text1 or not text2:
            return 0.0

        tokens1 = set(self.tokenize(text1))
        tokens2 = set(self.tokenize(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)

        return intersection / union if union > 0 else 0.0

    def compute_overlap_coefficient(self, text1: str, text2: str) -> float:
        """
        Compute overlap coefficient between two texts.

        Measures how much smaller set is contained in larger set.
        Useful for detecting if one chunk is a subset of another.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Overlap coefficient (0.0 to 1.0)
        """
        if not text1 or not text2:
            return 0.0

        tokens1 = set(self.tokenize(text1))
        tokens2 = set(self.tokenize(text2))

        if not tokens1 or not tokens2:
            return 0.0

        intersection = len(tokens1 & tokens2)
        min_size = min(len(tokens1), len(tokens2))

        return intersection / min_size if min_size > 0 else 0.0

    def compute_hybrid_similarity(self, text1: str, text2: str) -> float:
        """
        Compute hybrid similarity combining multiple methods.

        Combines cosine, Jaccard, and overlap coefficient for robust similarity.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Hybrid similarity score (0.0 to 1.0)
        """
        cosine_sim = self.compute_cosine_similarity(text1, text2)
        jaccard_sim = self.compute_jaccard_similarity(text1, text2)
        overlap_sim = self.compute_overlap_coefficient(text1, text2)

        # Weighted average (cosine is most important)
        hybrid_score = (
            0.6 * cosine_sim +
            0.2 * jaccard_sim +
            0.2 * overlap_sim
        )

        return hybrid_score

    def are_similar(
        self, text1: str, text2: str,
        threshold: float = 0.80,
        method: str = "cosine"
    ) -> bool:
        """
        Check if two texts are similar above threshold.

        Args:
            text1: First text
            text2: Second text
            threshold: Similarity threshold (default: 0.80 for 80%)
            method: Similarity method ("cosine", "jaccard", "overlap", "hybrid")

        Returns:
            True if similarity >= threshold
        """
        if method == "cosine":
            similarity = self.compute_cosine_similarity(text1, text2)
        elif method == "jaccard":
            similarity = self.compute_jaccard_similarity(text1, text2)
        elif method == "overlap":
            similarity = self.compute_overlap_coefficient(text1, text2)
        elif method == "hybrid":
            similarity = self.compute_hybrid_similarity(text1, text2)
        else:
            raise ValueError(f"Unknown similarity method: {method}")

        return similarity >= threshold

    def batch_similarity(
        self, reference_text: str, candidate_texts: List[str]
    ) -> List[Tuple[int, float]]:
        """
        Compute similarity of multiple candidates against a reference.

        Args:
            reference_text: Reference text
            candidate_texts: List of candidate texts

        Returns:
            List of (index, similarity) tuples, sorted by similarity descending
        """
        similarities = [
            (i, self.compute_cosine_similarity(reference_text, candidate))
            for i, candidate in enumerate(candidate_texts)
        ]

        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        return similarities


# Global similarity calculator instance
default_similarity_calculator = SimilarityCalculator(use_stemming=False)


def calculate_similarity(text1: str, text2: str, threshold: float = 0.80) -> float:
    """
    Convenience function to calculate cosine similarity.

    Args:
        text1: First text
        text2: Second text
        threshold: Threshold for similarity (not used in calculation, for reference)

    Returns:
        Similarity score (0.0 to 1.0)
    """
    return default_similarity_calculator.compute_cosine_similarity(text1, text2)


def are_chunks_similar(text1: str, text2: str, threshold: float = 0.80) -> bool:
    """
    Convenience function to check if chunks are similar.

    Args:
        text1: First text
        text2: Second text
        threshold: Similarity threshold (default: 0.80)

    Returns:
        True if similarity >= threshold
    """
    return default_similarity_calculator.are_similar(text1, text2, threshold=threshold)
