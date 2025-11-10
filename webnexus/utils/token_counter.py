"""
Token Counter Utility

Provides token counting functionality for chunking strategies.
Uses tiktoken for accurate token counts compatible with modern LLMs.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import tiktoken, fall back to simple word-based counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, falling back to approximate token counting")


class TokenCounter:
    """
    Token counter that supports multiple tokenization methods.

    Preferred: tiktoken (accurate, fast, compatible with GPT models)
    Fallback: Word-based approximation (1 token ≈ 0.75 words)
    """

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        Initialize token counter.

        Args:
            encoding_name: Tiktoken encoding name
                - "cl100k_base": GPT-4, GPT-3.5-turbo (recommended)
                - "p50k_base": GPT-3, Codex
                - "r50k_base": GPT-2, GPT-3 base
        """
        self.encoding_name = encoding_name
        self.encoder = None

        if TIKTOKEN_AVAILABLE:
            try:
                self.encoder = tiktoken.get_encoding(encoding_name)
                logger.info(f"Initialized TokenCounter with {encoding_name} encoding")
            except Exception as e:
                logger.warning(f"Failed to load tiktoken encoding: {e}, using fallback")
                self.encoder = None
        else:
            logger.info("TokenCounter using word-based approximation")

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        if not text:
            return 0

        if self.encoder is not None:
            try:
                return len(self.encoder.encode(text))
            except Exception as e:
                logger.warning(f"Error encoding text: {e}, falling back to approximation")
                return self._approximate_tokens(text)
        else:
            return self._approximate_tokens(text)

    def _approximate_tokens(self, text: str) -> int:
        """
        Approximate token count using word-based heuristic.

        Rule of thumb: 1 token ≈ 0.75 words or 4 characters
        This is a conservative estimate that works reasonably well.

        Args:
            text: Text to approximate tokens for

        Returns:
            Approximate token count
        """
        # Count words
        words = len(text.split())

        # Apply 0.75 multiplier (more words = more tokens, but not 1:1)
        # Also consider character count for non-English or code
        char_estimate = len(text) / 4
        word_estimate = words * 1.3  # Words tend to be more than 1 token each

        # Take the average of both estimates
        return int((char_estimate + word_estimate) / 2)

    def count_tokens_batch(self, texts: list[str]) -> list[int]:
        """
        Count tokens for multiple texts efficiently.

        Args:
            texts: List of texts to count tokens for

        Returns:
            List of token counts
        """
        return [self.count_tokens(text) for text in texts]

    def truncate_to_token_limit(self, text: str, max_tokens: int, from_end: bool = False) -> str:
        """
        Truncate text to fit within token limit.

        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens
            from_end: If True, truncate from the end instead of start

        Returns:
            Truncated text
        """
        if not text:
            return ""

        current_tokens = self.count_tokens(text)

        if current_tokens <= max_tokens:
            return text

        if self.encoder is not None:
            try:
                tokens = self.encoder.encode(text)

                if from_end:
                    truncated_tokens = tokens[-max_tokens:]
                else:
                    truncated_tokens = tokens[:max_tokens]

                return self.encoder.decode(truncated_tokens)
            except Exception as e:
                logger.warning(f"Error truncating text: {e}, using approximation")
                return self._approximate_truncate(text, max_tokens, from_end)
        else:
            return self._approximate_truncate(text, max_tokens, from_end)

    def _approximate_truncate(self, text: str, max_tokens: int, from_end: bool = False) -> str:
        """
        Approximate truncation using character-based estimation.

        Args:
            text: Text to truncate
            max_tokens: Maximum number of tokens
            from_end: If True, truncate from the end

        Returns:
            Truncated text
        """
        # Approximate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4

        if len(text) <= max_chars:
            return text

        if from_end:
            return text[-max_chars:]
        else:
            return text[:max_chars]

    def get_encoding_name(self) -> str:
        """Get the encoding name being used"""
        return self.encoding_name if self.encoder else "word_approximation"

    def is_available(self) -> bool:
        """Check if tiktoken encoder is available"""
        return self.encoder is not None


# Default global token counter instance
default_token_counter = TokenCounter(encoding_name="cl100k_base")


def count_tokens(text: str) -> int:
    """
    Convenience function to count tokens in text.

    Args:
        text: Text to count tokens for

    Returns:
        Number of tokens
    """
    return default_token_counter.count_tokens(text)


def count_tokens_batch(texts: list[str]) -> list[int]:
    """
    Convenience function to count tokens for multiple texts.

    Args:
        texts: List of texts

    Returns:
        List of token counts
    """
    return default_token_counter.count_tokens_batch(texts)
