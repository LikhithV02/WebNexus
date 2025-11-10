"""Document chunking utilities for WebNexus"""

import re
import hashlib
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
import logging
import math

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a document chunk"""
    content: str
    start_char: int
    end_char: int
    chunk_index: int
    word_count: int
    char_count: int
    content_hash: str


class DocumentChunker:
    """Advanced document chunking with multiple strategies"""
    
    def __init__(
        self, 
        chunk_size: int = 1000, 
        overlap_size: int = 100,
        respect_boundaries: bool = True,
        min_chunk_size: int = 50,
        max_chunk_size: int = 2000
    ):
        """
        Initialize document chunker
        
        Args:
            chunk_size: Target chunk size in characters
            overlap_size: Overlap between chunks in characters
            respect_boundaries: Whether to respect sentence/paragraph boundaries
            min_chunk_size: Minimum chunk size (chunks smaller than this are merged)
            max_chunk_size: Maximum chunk size (chunks larger are force-split)
        """
        self.chunk_size = chunk_size
        self.overlap_size = overlap_size
        self.respect_boundaries = respect_boundaries
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        
        # Enhanced regex patterns for better boundary detection
        self.sentence_pattern = re.compile(r'[.!?]+\s+(?=[A-Z])')  # Better sentence detection
        self.paragraph_pattern = re.compile(r'\n\s*\n')
        self.section_pattern = re.compile(r'\n#{1,6}\s+[^\n]+\n')  # Markdown headers
        self.list_pattern = re.compile(r'\n[-*+]\s+|\n\d+\.\s+')  # Lists
        self.code_block_pattern = re.compile(r'\n```[\s\S]*?```\n|\n    [^\n]+(?:\n    [^\n]*)*\n')  # Code blocks
    
    def chunk_document(self, content: str, url: str = "", metadata: Optional[Dict[str, Any]] = None) -> List[DocumentChunk]:
        """
        Chunk a document into overlapping segments
        
        Args:
            content: Document content to chunk
            url: Document URL (for logging)
            metadata: Additional metadata
        
        Returns:
            List of DocumentChunk objects
        """
        if not content or len(content.strip()) < self.min_chunk_size:
            return []
        
        content = content.strip()
        chunks = []
        
        if self.respect_boundaries:
            chunks = self._chunk_with_boundaries(content)
        else:
            chunks = self._chunk_fixed_size(content)
        
        # Post-process chunks
        chunks = self._post_process_chunks(chunks)
        
        # Create DocumentChunk objects
        document_chunks = []
        for i, (chunk_content, start_char, end_char) in enumerate(chunks):
            chunk_hash = self._generate_content_hash(chunk_content)
            word_count = len(chunk_content.split())
            char_count = len(chunk_content)
            
            document_chunk = DocumentChunk(
                content=chunk_content,
                start_char=start_char,
                end_char=end_char,
                chunk_index=i,
                word_count=word_count,
                char_count=char_count,
                content_hash=chunk_hash
            )
            document_chunks.append(document_chunk)
        
        logger.info(f"Created {len(document_chunks)} chunks from document {url[:100]}...")
        return document_chunks
    
    def _chunk_with_boundaries(self, content: str) -> List[Tuple[str, int, int]]:
        """Chunk document respecting natural boundaries"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + self.chunk_size
            
            if end >= len(content):
                # Last chunk
                chunk_content = content[start:].strip()
                if len(chunk_content) >= self.min_chunk_size:
                    chunks.append((chunk_content, start, len(content)))
                elif chunks:
                    # Merge small final chunk with previous chunk
                    prev_content, prev_start, prev_end = chunks[-1]
                    merged_content = prev_content + "\n\n" + chunk_content
                    chunks[-1] = (merged_content, prev_start, len(content))
                break
            
            # Find the best boundary within the chunk
            boundary_pos = self._find_best_boundary(content, start, end)
            
            if boundary_pos is None or boundary_pos <= start:
                # No good boundary found, use fixed position
                boundary_pos = end
                # Try to break at word boundary at least
                word_boundary = content.rfind(' ', start, boundary_pos)
                if word_boundary > start:
                    boundary_pos = word_boundary
            
            chunk_content = content[start:boundary_pos].strip()
            if len(chunk_content) >= self.min_chunk_size:
                chunks.append((chunk_content, start, boundary_pos))
            elif chunks and len(chunk_content) > 0:
                # Merge small chunk with previous
                prev_content, prev_start, prev_end = chunks[-1]
                merged_content = prev_content + "\n" + chunk_content
                chunks[-1] = (merged_content, prev_start, boundary_pos)
            
            # Move start with overlap
            start = max(start + 1, boundary_pos - self.overlap_size)
        
        return chunks
    
    def _find_best_boundary(self, content: str, start: int, end: int) -> Optional[int]:
        """Find the best boundary position within a range"""
        # Look for boundaries in order of preference
        search_text = content[start:end + 200]  # Look a bit beyond for boundaries
        
        # 1. Section headers (highest priority)
        section_matches = list(self.section_pattern.finditer(search_text))
        if section_matches:
            # Find the header closest to our target position
            target_pos = end - start
            best_match = min(section_matches, key=lambda m: abs(m.start() - target_pos))
            pos = start + best_match.start()
            if start < pos <= end + 100:  # Allow some flexibility
                return pos
        
        # 2. Code blocks (preserve code integrity)
        code_matches = list(self.code_block_pattern.finditer(search_text))
        for match in code_matches:
            code_start = start + match.start()
            code_end = start + match.end()
            # If chunk boundary would split code block, adjust to preserve it
            if code_start < end < code_end:
                if abs(code_start - end) < abs(code_end - end):
                    if code_start > start:
                        return code_start
                else:
                    return code_end

        # 3. Lists (keep list items together when possible)
        list_matches = list(self.list_pattern.finditer(search_text))
        if list_matches:
            target_pos = end - start
            for match in list_matches:
                pos = start + match.start()
                if abs(pos - end) <= 100 and start < pos <= end + 50:
                    return pos

        # 4. Paragraph breaks
        paragraph_matches = list(self.paragraph_pattern.finditer(search_text))
        if paragraph_matches:
            target_pos = end - start
            best_match = min(paragraph_matches, key=lambda m: abs(m.start() - target_pos))
            pos = start + best_match.end()
            if start < pos <= end + 50:
                return pos
        
        # 5. Sentence boundaries
        sentence_matches = list(self.sentence_pattern.finditer(search_text))
        if sentence_matches:
            target_pos = end - start
            best_match = min(sentence_matches, key=lambda m: abs(m.start() - target_pos))
            pos = start + best_match.end()
            if start < pos <= end + 50:
                return pos
        
        return None
    
    def _chunk_fixed_size(self, content: str) -> List[Tuple[str, int, int]]:
        """Chunk document with fixed size (fallback method)"""
        chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + self.chunk_size, len(content))
            
            # Try to break at word boundary
            if end < len(content):
                word_boundary = content.rfind(' ', start, end)
                if word_boundary > start:
                    end = word_boundary
            
            chunk_content = content[start:end].strip()
            if chunk_content:
                chunks.append((chunk_content, start, end))
            
            # Move start with overlap
            start = max(start + 1, end - self.overlap_size)
        
        return chunks
    
    def _post_process_chunks(self, chunks: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        """Post-process chunks to handle edge cases"""
        if not chunks:
            return chunks
        
        processed_chunks = []
        
        for i, (content, start, end) in enumerate(chunks):
            # Skip empty or too small chunks
            if len(content.strip()) < self.min_chunk_size:
                if processed_chunks:
                    # Merge with previous chunk
                    prev_content, prev_start, prev_end = processed_chunks[-1]
                    merged_content = prev_content + "\n\n" + content
                    processed_chunks[-1] = (merged_content, prev_start, end)
                continue
            
            # Handle oversized chunks
            if len(content) > self.max_chunk_size:
                # Force split large chunks
                sub_chunks = self._force_split_chunk(content, start, self.max_chunk_size)
                processed_chunks.extend(sub_chunks)
            else:
                processed_chunks.append((content, start, end))
        
        return processed_chunks
    
    def _force_split_chunk(self, content: str, start_offset: int, max_size: int) -> List[Tuple[str, int, int]]:
        """Force split a chunk that's too large"""
        sub_chunks = []
        start = 0
        
        while start < len(content):
            end = min(start + max_size, len(content))
            
            # Try to break at sentence or word boundary
            if end < len(content):
                # Look for sentence boundary
                sentence_boundary = content.rfind('.', start, end)
                if sentence_boundary > start:
                    end = sentence_boundary + 1
                else:
                    # Look for word boundary
                    word_boundary = content.rfind(' ', start, end)
                    if word_boundary > start:
                        end = word_boundary
            
            sub_content = content[start:end].strip()
            if sub_content:
                sub_chunks.append((sub_content, start_offset + start, start_offset + end))
            
            start = end
        
        return sub_chunks
    
    def _generate_content_hash(self, content: str) -> str:
        """Generate a hash for chunk content (for deduplication)"""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def get_chunk_context(self, chunks: List[DocumentChunk], chunk_index: int, context_size: int = 200) -> Dict[str, str]:
        """
        Get context around a specific chunk
        
        Args:
            chunks: List of all chunks
            chunk_index: Index of the target chunk
            context_size: Size of context in characters
        
        Returns:
            Dictionary with 'before' and 'after' context
        """
        if not chunks or chunk_index < 0 or chunk_index >= len(chunks):
            return {"before": "", "after": ""}
        
        context = {"before": "", "after": ""}
        
        # Get before context
        if chunk_index > 0:
            prev_chunk = chunks[chunk_index - 1]
            context["before"] = prev_chunk.content[-context_size:] if len(prev_chunk.content) > context_size else prev_chunk.content
        
        # Get after context
        if chunk_index < len(chunks) - 1:
            next_chunk = chunks[chunk_index + 1]
            context["after"] = next_chunk.content[:context_size] if len(next_chunk.content) > context_size else next_chunk.content
        
        return context
    
    def calculate_semantic_similarity(self, chunk1: str, chunk2: str) -> float:
        """
        Calculate simple semantic similarity between chunks
        Uses keyword overlap and structural similarity
        """
        # Simple keyword-based similarity
        words1 = set(re.findall(r'\b\w+\b', chunk1.lower()))
        words2 = set(re.findall(r'\b\w+\b', chunk2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0
    
    def optimize_chunk_boundaries(self, chunks: List[Tuple[str, int, int]]) -> List[Tuple[str, int, int]]:
        """
        Optimize chunk boundaries using semantic similarity
        """
        if len(chunks) < 2:
            return chunks
        
        optimized = []
        i = 0
        
        while i < len(chunks):
            current_chunk = chunks[i]
            
            # Look ahead to see if next chunk should be merged
            if i < len(chunks) - 1:
                next_chunk = chunks[i + 1]
                
                # Check if chunks are too similar (might be artificially split)
                similarity = self.calculate_semantic_similarity(current_chunk[0], next_chunk[0])
                combined_size = len(current_chunk[0]) + len(next_chunk[0])
                
                # Merge if very similar and combined size is reasonable
                if similarity > 0.7 and combined_size < self.max_chunk_size:
                    merged_content = current_chunk[0] + "\n\n" + next_chunk[0]
                    merged_chunk = (merged_content, current_chunk[1], next_chunk[2])
                    optimized.append(merged_chunk)
                    i += 2  # Skip next chunk as it's been merged
                    continue
            
            optimized.append(current_chunk)
            i += 1
        
        return optimized


class SpecializedChunkers:
    """Specialized chunkers for different content types"""
    
    @staticmethod
    def chunk_code(content: str, language: str = None) -> List[DocumentChunk]:
        """Chunk code content preserving function/class boundaries"""
        chunker = DocumentChunker(
            chunk_size=800,
            overlap_size=50,
            respect_boundaries=True,
            min_chunk_size=100,
            max_chunk_size=1500
        )
        
        # Enhanced code-specific boundary patterns
        if language in ["python", "py"]:
            # Python: functions, classes, imports, decorators
            chunker.section_pattern = re.compile(r'\n(?:@\w+\s+)*(?:def |class |import |from |async def )')
            chunker.code_block_pattern = re.compile(r'\n    [^\n]+(?:\n    [^\n]*)*\n')  # Indented blocks
        elif language in ["javascript", "js", "typescript", "ts"]:
            # JS/TS: functions, classes, imports, exports
            chunker.section_pattern = re.compile(r'\n(?:export\s+)?(?:async\s+)?(?:function\s+\w+|class\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=|var\s+\w+\s*=|import\s|export\s)')
        elif language in ["java", "c", "cpp", "csharp", "cs"]:
            # C-style: functions, classes, methods
            chunker.section_pattern = re.compile(r'\n(?:public|private|protected|static)?\s*(?:class|interface|struct|enum|\w+\s+\w+\s*\()')
        elif language in ["go"]:
            # Go: functions, types, methods
            chunker.section_pattern = re.compile(r'\n(?:func\s+|type\s+|package\s+|import\s+)')
        elif language in ["rust", "rs"]:
            # Rust: functions, structs, enums, impls
            chunker.section_pattern = re.compile(r'\n(?:fn\s+|struct\s+|enum\s+|impl\s+|trait\s+|mod\s+|use\s+)')
        elif language in ["php"]:
            # PHP: functions, classes, methods
            chunker.section_pattern = re.compile(r'\n(?:<?php|class\s+|function\s+|public\s+|private\s+|protected\s+)')
        
        return chunker.chunk_document(content)
    
    @staticmethod
    def chunk_markdown(content: str) -> List[DocumentChunk]:
        """Chunk markdown content preserving section structure"""
        chunker = DocumentChunker(
            chunk_size=1200,
            overlap_size=100,
            respect_boundaries=True,
            min_chunk_size=100,
            max_chunk_size=2000
        )
        
        # Enhanced markdown-specific patterns
        chunker.section_pattern = re.compile(r'\n#{1,6}\s+[^\n]+\n')  # Headers
        chunker.list_pattern = re.compile(r'\n(?:[-*+]\s+|\d+\.\s+)[^\n]+(?:\n\s+[^\n]+)*')  # Lists
        chunker.code_block_pattern = re.compile(r'\n```[\w]*\n[\s\S]*?\n```\n|\n    [^\n]+(?:\n    [^\n]*)*\n')  # Code blocks
        
        # Additional markdown patterns
        chunker.table_pattern = re.compile(r'\n\|[^\n]+\|\n\|[-\s\|]+\|\n(?:\|[^\n]+\|\n)*')  # Tables
        chunker.quote_pattern = re.compile(r'\n>[^\n]+(?:\n>[^\n]+)*\n')  # Block quotes
        
        return chunker.chunk_document(content)
    
    @staticmethod
    def chunk_plain_text(content: str) -> List[DocumentChunk]:
        """Chunk plain text with paragraph preservation"""
        chunker = DocumentChunker(
            chunk_size=1000,
            overlap_size=100,
            respect_boundaries=True,
            min_chunk_size=50,
            max_chunk_size=1800
        )
        
        return chunker.chunk_document(content)
    
    @staticmethod
    def chunk_html(content: str) -> List[DocumentChunk]:
        """Chunk HTML content preserving element structure"""
        chunker = DocumentChunker(
            chunk_size=1000,
            overlap_size=80,
            respect_boundaries=True,
            min_chunk_size=100,
            max_chunk_size=1800
        )
        
        # HTML-specific patterns
        chunker.section_pattern = re.compile(r'</?(?:div|section|article|header|footer|main|aside|nav)[^>]*>')  # Block elements
        chunker.paragraph_pattern = re.compile(r'</?(?:p|br|hr)[^>]*>')  # Paragraph elements
        
        return chunker.chunk_document(content)
    
    @staticmethod
    def chunk_structured_data(content: str, data_type: str = "json") -> List[DocumentChunk]:
        """Chunk structured data (JSON, XML, YAML) preserving structure"""
        chunker = DocumentChunker(
            chunk_size=800,
            overlap_size=50,
            respect_boundaries=True,
            min_chunk_size=100,
            max_chunk_size=1500
        )
        
        if data_type.lower() == "json":
            # JSON: objects and arrays
            chunker.section_pattern = re.compile(r'\n\s*[{}\[\]]\s*,?\s*\n')
        elif data_type.lower() in ["xml", "html"]:
            # XML/HTML: elements
            chunker.section_pattern = re.compile(r'</?\w+[^>]*>')
        elif data_type.lower() in ["yaml", "yml"]:
            # YAML: top-level keys
            chunker.section_pattern = re.compile(r'\n\w+:\s*\n')
        
        return chunker.chunk_document(content)


# Default chunker instances with optimized settings
default_chunker = DocumentChunker(
    chunk_size=1000,
    overlap_size=100, 
    respect_boundaries=True,
    min_chunk_size=50,
    max_chunk_size=2000
)

# Semantic chunker for better content understanding
semantic_chunker = DocumentChunker(
    chunk_size=800,
    overlap_size=80,
    respect_boundaries=True,
    min_chunk_size=100,
    max_chunk_size=1500
)