"""
Documentation-Focused Markdown Chunking Strategy

Specialized chunking for package documentation with:
- 4000 token chunks (no overlap)
- Markdown structure preservation (code blocks, tables, lists, headers)
- Header hierarchy analysis
- Smart merging (token limit + hierarchy + ≥80% similarity)
- Minimal splitting (only when exceeding token limit)
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from .token_counter import TokenCounter, default_token_counter
from .markdown_parser import MarkdownParser, MarkdownElement, ElementType, markdown_parser
from .header_hierarchy import HierarchyAnalyzer, create_hierarchy_analyzer
from .similarity_calculator import SimilarityCalculator, default_similarity_calculator

logger = logging.getLogger(__name__)


@dataclass
class DocumentationChunk:
    """
    Represents a documentation chunk.

    Attributes:
        content: Chunk text content
        start_char: Start position in original document
        end_char: End position in original document
        chunk_index: Index of chunk in document
        token_count: Number of tokens in chunk
        char_count: Number of characters
        word_count: Number of words
        content_hash: MD5 hash of content
        metadata: Additional metadata (headers, element types, etc.)
    """
    content: str
    start_char: int
    end_char: int
    chunk_index: int
    token_count: int
    char_count: int
    word_count: int
    content_hash: str
    metadata: Dict[str, Any]


class DocumentationChunker:
    """
    Specialized chunker for documentation with markdown structure awareness.

    Features:
    - Token-based chunking (4000 tokens, no overlap)
    - Preserves markdown structure (code blocks, tables, lists)
    - New chunk at each header
    - Header hierarchy analysis
    - Smart merging (token limit + hierarchy + similarity ≥80%)
    - Minimal splitting (only when exceeding limit)
    """

    def __init__(
        self,
        max_tokens: int = 4000,
        similarity_threshold: float = 0.80,
        max_level_difference: int = 0,
        enable_merging: bool = True,
        similarity_method: str = "cosine"
    ):
        """
        Initialize documentation chunker.

        Args:
            max_tokens: Maximum tokens per chunk (default: 4000)
            similarity_threshold: Minimum similarity for merging (default: 0.80)
            max_level_difference: Max header level difference for same hierarchy (default: 0)
            enable_merging: Whether to enable chunk merging (default: True)
            similarity_method: Similarity calculation method (default: "cosine")
        """
        self.max_tokens = max_tokens
        self.similarity_threshold = similarity_threshold
        self.max_level_difference = max_level_difference
        self.enable_merging = enable_merging
        self.similarity_method = similarity_method

        # Initialize utilities
        self.token_counter = default_token_counter
        self.markdown_parser = markdown_parser
        self.similarity_calculator = default_similarity_calculator

        logger.info(f"Initialized DocumentationChunker: max_tokens={max_tokens}, "
                   f"similarity_threshold={similarity_threshold}")

    def chunk_document(self, content: str, url: str = "", metadata: Optional[Dict[str, Any]] = None) -> List[DocumentationChunk]:
        """
        Chunk a markdown document intelligently.

        Pipeline:
        1. Parse markdown into structural elements
        2. Build header hierarchy
        3. Create initial element-based chunks
        4. Merge chunks based on criteria
        5. Split oversized chunks if needed

        Args:
            content: Markdown content to chunk
            url: Document URL (for logging)
            metadata: Additional metadata

        Returns:
            List of DocumentationChunk objects
        """
        if not content or len(content.strip()) < 10:
            logger.warning(f"Content too short for chunking: {url}")
            return []

        logger.info(f"Starting documentation chunking for: {url[:100]}...")

        # Phase 1: Parse markdown structure
        elements = self.markdown_parser.parse(content)
        if not elements:
            logger.warning(f"No markdown elements found in: {url}")
            return []

        logger.info(f"Parsed {len(elements)} markdown elements")

        # Phase 2: Build header hierarchy
        hierarchy_analyzer = create_hierarchy_analyzer(elements)

        # Phase 3: Create initial chunks from elements
        initial_chunks = self._create_initial_chunks(elements, hierarchy_analyzer)
        logger.info(f"Created {len(initial_chunks)} initial chunks")

        # Phase 4: Merge chunks if enabled
        if self.enable_merging and len(initial_chunks) > 1:
            merged_chunks = self._merge_chunks(initial_chunks, hierarchy_analyzer)
            logger.info(f"After merging: {len(merged_chunks)} chunks")
        else:
            merged_chunks = initial_chunks

        # Phase 5: Split oversized chunks
        final_chunks = self._split_oversized_chunks(merged_chunks)
        logger.info(f"Final chunk count: {len(final_chunks)}")

        # Phase 6: Create DocumentationChunk objects with metadata
        documentation_chunks = self._create_documentation_chunks(
            final_chunks, url, metadata
        )

        # Log statistics
        self._log_chunk_statistics(documentation_chunks)

        return documentation_chunks

    def _create_initial_chunks(
        self, elements: List[MarkdownElement], hierarchy_analyzer: HierarchyAnalyzer
    ) -> List[Dict[str, Any]]:
        """
        Create initial chunks from markdown elements.

        Strategy:
        - New chunk at each header
        - Code blocks in separate chunks
        - Tables in separate chunks
        - Lists in separate chunks
        - Group consecutive paragraphs together

        Args:
            elements: Parsed markdown elements
            hierarchy_analyzer: Header hierarchy analyzer

        Returns:
            List of chunk dictionaries
        """
        chunks = []
        current_chunk_elements = []
        current_start_pos = 0

        for elem in elements:
            # Decide if this element should start a new chunk
            should_start_new_chunk = self._should_start_new_chunk(
                elem, current_chunk_elements
            )

            if should_start_new_chunk and current_chunk_elements:
                # Save current chunk
                chunk = self._elements_to_chunk(
                    current_chunk_elements, current_start_pos
                )
                if chunk:
                    chunks.append(chunk)

                # Start new chunk
                current_chunk_elements = [elem]
                current_start_pos = elem.start_pos
            else:
                # Add to current chunk
                if not current_chunk_elements:
                    current_start_pos = elem.start_pos
                current_chunk_elements.append(elem)

        # Save final chunk
        if current_chunk_elements:
            chunk = self._elements_to_chunk(current_chunk_elements, current_start_pos)
            if chunk:
                chunks.append(chunk)

        return chunks

    def _should_start_new_chunk(
        self, elem: MarkdownElement, current_elements: List[MarkdownElement]
    ) -> bool:
        """
        Determine if element should start a new chunk.

        Args:
            elem: Current element
            current_elements: Elements in current chunk

        Returns:
            True if should start new chunk
        """
        # No current chunk, start first chunk
        if not current_elements:
            return False

        # Headers always start new chunk
        if elem.type == ElementType.HEADER:
            return True

        # Code blocks always start new chunk
        if elem.type == ElementType.CODE_BLOCK:
            return True

        # Tables always start new chunk
        if elem.type == ElementType.TABLE:
            return True

        # Lists start new chunk (unless current chunk is also a list)
        if elem.type == ElementType.LIST:
            # Check if current chunk ends with a list
            if current_elements and current_elements[-1].type == ElementType.LIST:
                # Same list type? Can continue
                current_list_type = current_elements[-1].metadata.get("list_type")
                new_list_type = elem.metadata.get("list_type")
                if current_list_type == new_list_type:
                    return False
            return True

        # Paragraphs can be grouped together
        return False

    def _elements_to_chunk(
        self, elements: List[MarkdownElement], start_pos: int
    ) -> Optional[Dict[str, Any]]:
        """
        Convert elements to chunk dictionary.

        Args:
            elements: List of elements
            start_pos: Start position

        Returns:
            Chunk dictionary or None if invalid
        """
        if not elements:
            return None

        # Combine element contents
        content_parts = [elem.content for elem in elements]
        content = "\n\n".join(content_parts)

        # Calculate end position
        end_pos = elements[-1].end_pos

        # Count tokens
        token_count = self.token_counter.count_tokens(content)

        # Extract metadata
        element_types = [elem.type.value for elem in elements]
        headers = [
            elem.metadata.get("title", "")
            for elem in elements
            if elem.type == ElementType.HEADER
        ]

        chunk_metadata = {
            "element_types": element_types,
            "element_count": len(elements),
            "has_header": ElementType.HEADER in [e.type for e in elements],
            "has_code": ElementType.CODE_BLOCK in [e.type for e in elements],
            "has_table": ElementType.TABLE in [e.type for e in elements],
            "has_list": ElementType.LIST in [e.type for e in elements],
            "headers": headers,
        }

        return {
            "content": content,
            "start_pos": start_pos,
            "end_pos": end_pos,
            "token_count": token_count,
            "elements": elements,
            "metadata": chunk_metadata
        }

    def _merge_chunks(
        self, chunks: List[Dict[str, Any]], hierarchy_analyzer: HierarchyAnalyzer
    ) -> List[Dict[str, Any]]:
        """
        Merge chunks based on criteria:
        1. Combined tokens < max_tokens
        2. Under same header hierarchy
        3. Cosine similarity >= threshold

        Args:
            chunks: List of chunk dictionaries
            hierarchy_analyzer: Header hierarchy analyzer

        Returns:
            List of merged chunks
        """
        if len(chunks) <= 1:
            return chunks

        merged = []
        i = 0

        while i < len(chunks):
            current_chunk = chunks[i]

            # Try to merge with next chunk
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]

                if self._can_merge_chunks(current_chunk, next_chunk, hierarchy_analyzer):
                    # Merge the chunks
                    merged_chunk = self._merge_two_chunks(current_chunk, next_chunk)
                    merged.append(merged_chunk)
                    i += 2  # Skip next chunk as it's been merged
                    logger.debug(f"Merged chunks at index {i-1} and {i}")
                    continue

            # Can't merge, add current chunk as-is
            merged.append(current_chunk)
            i += 1

        # If we merged anything, try another pass
        if len(merged) < len(chunks):
            logger.debug(f"Merge pass: {len(chunks)} -> {len(merged)} chunks")
            return self._merge_chunks(merged, hierarchy_analyzer)

        return merged

    def _can_merge_chunks(
        self, chunk1: Dict[str, Any], chunk2: Dict[str, Any],
        hierarchy_analyzer: HierarchyAnalyzer
    ) -> bool:
        """
        Check if two chunks can be merged.

        Criteria:
        1. Combined tokens < max_tokens
        2. Under same header hierarchy
        3. Cosine similarity >= threshold

        Args:
            chunk1: First chunk
            chunk2: Second chunk
            hierarchy_analyzer: Header hierarchy analyzer

        Returns:
            True if chunks can be merged
        """
        # Criterion 1: Token limit
        combined_tokens = chunk1["token_count"] + chunk2["token_count"]
        if combined_tokens > self.max_tokens:
            return False

        # Criterion 2: Header hierarchy
        pos1 = chunk1["start_pos"]
        pos2 = chunk2["start_pos"]

        same_hierarchy = hierarchy_analyzer.are_under_same_hierarchy(
            pos1, pos2, max_level_difference=self.max_level_difference
        )

        if not same_hierarchy:
            return False

        # Criterion 3: Similarity
        similarity = self.similarity_calculator.compute_cosine_similarity(
            chunk1["content"], chunk2["content"]
        )

        if similarity < self.similarity_threshold:
            return False

        logger.debug(f"Can merge: tokens={combined_tokens}, similarity={similarity:.2f}")
        return True

    def _merge_two_chunks(
        self, chunk1: Dict[str, Any], chunk2: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merge two chunks into one.

        Args:
            chunk1: First chunk
            chunk2: Second chunk

        Returns:
            Merged chunk dictionary
        """
        # Combine contents
        merged_content = chunk1["content"] + "\n\n" + chunk2["content"]

        # Combine elements
        merged_elements = chunk1["elements"] + chunk2["elements"]

        # Recalculate token count
        token_count = self.token_counter.count_tokens(merged_content)

        # Merge metadata
        merged_metadata = {
            "element_types": chunk1["metadata"]["element_types"] + chunk2["metadata"]["element_types"],
            "element_count": chunk1["metadata"]["element_count"] + chunk2["metadata"]["element_count"],
            "has_header": chunk1["metadata"]["has_header"] or chunk2["metadata"]["has_header"],
            "has_code": chunk1["metadata"]["has_code"] or chunk2["metadata"]["has_code"],
            "has_table": chunk1["metadata"]["has_table"] or chunk2["metadata"]["has_table"],
            "has_list": chunk1["metadata"]["has_list"] or chunk2["metadata"]["has_list"],
            "headers": chunk1["metadata"]["headers"] + chunk2["metadata"]["headers"],
            "merged": True
        }

        return {
            "content": merged_content,
            "start_pos": chunk1["start_pos"],
            "end_pos": chunk2["end_pos"],
            "token_count": token_count,
            "elements": merged_elements,
            "metadata": merged_metadata
        }

    def _split_oversized_chunks(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Split chunks that exceed token limit.

        Strategy:
        1. Split at paragraph boundaries
        2. Split at sentence boundaries
        3. Split at word boundaries (last resort)

        Args:
            chunks: List of chunk dictionaries

        Returns:
            List of chunks with oversized ones split
        """
        result = []

        for chunk in chunks:
            if chunk["token_count"] <= self.max_tokens:
                result.append(chunk)
            else:
                # Split oversized chunk
                logger.warning(f"Splitting oversized chunk: {chunk['token_count']} tokens")
                split_chunks = self._split_chunk(chunk)
                result.extend(split_chunks)

        return result

    def _split_chunk(self, chunk: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Split a single oversized chunk.

        Args:
            chunk: Chunk to split

        Returns:
            List of smaller chunks
        """
        content = chunk["content"]
        start_pos = chunk["start_pos"]

        # Try splitting at paragraph boundaries first
        paragraphs = content.split("\n\n")

        if len(paragraphs) > 1:
            return self._split_by_paragraphs(paragraphs, start_pos, chunk["metadata"])

        # Try splitting at sentence boundaries
        sentences = self._split_into_sentences(content)

        if len(sentences) > 1:
            return self._split_by_sentences(sentences, start_pos, chunk["metadata"])

        # Last resort: split at word boundaries
        return self._split_by_words(content, start_pos, chunk["metadata"])

    def _split_by_paragraphs(
        self, paragraphs: List[str], start_pos: int, base_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Split content by paragraphs, respecting token limit"""
        chunks = []
        current_parts = []
        current_tokens = 0
        current_start = start_pos

        for para in paragraphs:
            para_tokens = self.token_counter.count_tokens(para)

            if current_tokens + para_tokens <= self.max_tokens:
                current_parts.append(para)
                current_tokens += para_tokens
            else:
                # Save current chunk
                if current_parts:
                    content = "\n\n".join(current_parts)
                    chunk = self._create_split_chunk(
                        content, current_start, current_tokens, base_metadata, "paragraph"
                    )
                    chunks.append(chunk)

                # Start new chunk
                current_parts = [para]
                current_tokens = para_tokens
                current_start += len("\n\n".join(current_parts[:-1])) + 2

        # Save final chunk
        if current_parts:
            content = "\n\n".join(current_parts)
            chunk = self._create_split_chunk(
                content, current_start, current_tokens, base_metadata, "paragraph"
            )
            chunks.append(chunk)

        return chunks

    def _split_by_sentences(
        self, sentences: List[str], start_pos: int, base_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Split content by sentences, respecting token limit"""
        chunks = []
        current_parts = []
        current_tokens = 0
        current_start = start_pos

        for sentence in sentences:
            sentence_tokens = self.token_counter.count_tokens(sentence)

            if current_tokens + sentence_tokens <= self.max_tokens:
                current_parts.append(sentence)
                current_tokens += sentence_tokens
            else:
                # Save current chunk
                if current_parts:
                    content = " ".join(current_parts)
                    chunk = self._create_split_chunk(
                        content, current_start, current_tokens, base_metadata, "sentence"
                    )
                    chunks.append(chunk)

                # Start new chunk
                current_parts = [sentence]
                current_tokens = sentence_tokens
                current_start += len(" ".join(current_parts[:-1])) + 1

        # Save final chunk
        if current_parts:
            content = " ".join(current_parts)
            chunk = self._create_split_chunk(
                content, current_start, current_tokens, base_metadata, "sentence"
            )
            chunks.append(chunk)

        return chunks

    def _split_by_words(
        self, content: str, start_pos: int, base_metadata: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Split content by words, respecting token limit (last resort)"""
        chunks = []
        words = content.split()
        current_words = []
        current_tokens = 0
        current_start = start_pos

        for word in words:
            word_tokens = self.token_counter.count_tokens(word)

            if current_tokens + word_tokens <= self.max_tokens:
                current_words.append(word)
                current_tokens += word_tokens
            else:
                # Save current chunk
                if current_words:
                    content_text = " ".join(current_words)
                    chunk = self._create_split_chunk(
                        content_text, current_start, current_tokens, base_metadata, "word"
                    )
                    chunks.append(chunk)

                # Start new chunk
                current_words = [word]
                current_tokens = word_tokens
                current_start += len(" ".join(current_words[:-1])) + 1

        # Save final chunk
        if current_words:
            content_text = " ".join(current_words)
            chunk = self._create_split_chunk(
                content_text, current_start, current_tokens, base_metadata, "word"
            )
            chunks.append(chunk)

        return chunks

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        import re
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def _create_split_chunk(
        self, content: str, start_pos: int, token_count: int,
        base_metadata: Dict[str, Any], split_type: str
    ) -> Dict[str, Any]:
        """Create a chunk from split content"""
        metadata = base_metadata.copy()
        metadata["split"] = True
        metadata["split_type"] = split_type

        return {
            "content": content,
            "start_pos": start_pos,
            "end_pos": start_pos + len(content),
            "token_count": token_count,
            "elements": [],  # No element tracking for split chunks
            "metadata": metadata
        }

    def _create_documentation_chunks(
        self, chunks: List[Dict[str, Any]], url: str, base_metadata: Optional[Dict[str, Any]]
    ) -> List[DocumentationChunk]:
        """
        Create final DocumentationChunk objects.

        Args:
            chunks: List of chunk dictionaries
            url: Document URL
            base_metadata: Base metadata

        Returns:
            List of DocumentationChunk objects
        """
        documentation_chunks = []

        for i, chunk_dict in enumerate(chunks):
            content = chunk_dict["content"]
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

            # Merge metadata
            metadata = chunk_dict["metadata"].copy()
            if base_metadata:
                metadata.update(base_metadata)
            metadata["url"] = url
            metadata["chunk_strategy"] = "documentation"

            chunk = DocumentationChunk(
                content=content,
                start_char=chunk_dict["start_pos"],
                end_char=chunk_dict["end_pos"],
                chunk_index=i,
                token_count=chunk_dict["token_count"],
                char_count=len(content),
                word_count=len(content.split()),
                content_hash=content_hash,
                metadata=metadata
            )

            documentation_chunks.append(chunk)

        return documentation_chunks

    def _log_chunk_statistics(self, chunks: List[DocumentationChunk]):
        """Log statistics about created chunks"""
        if not chunks:
            return

        token_counts = [c.token_count for c in chunks]
        avg_tokens = sum(token_counts) / len(token_counts)
        max_tokens = max(token_counts)
        min_tokens = min(token_counts)

        has_code = sum(1 for c in chunks if c.metadata.get("has_code", False))
        has_table = sum(1 for c in chunks if c.metadata.get("has_table", False))
        has_list = sum(1 for c in chunks if c.metadata.get("has_list", False))
        merged = sum(1 for c in chunks if c.metadata.get("merged", False))
        split = sum(1 for c in chunks if c.metadata.get("split", False))

        logger.info(f"Chunk Statistics:")
        logger.info(f"  Total chunks: {len(chunks)}")
        logger.info(f"  Token count - avg: {avg_tokens:.0f}, min: {min_tokens}, max: {max_tokens}")
        logger.info(f"  Chunks with code: {has_code}")
        logger.info(f"  Chunks with tables: {has_table}")
        logger.info(f"  Chunks with lists: {has_list}")
        logger.info(f"  Merged chunks: {merged}")
        logger.info(f"  Split chunks: {split}")


# Default documentation chunker instance
default_documentation_chunker = DocumentationChunker(
    max_tokens=4000,
    similarity_threshold=0.80,
    max_level_difference=0,
    enable_merging=True
)
