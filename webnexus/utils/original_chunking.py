"""
Original Archon Project Chunking Strategy

This implements the exact smart_chunk_text strategy from the original project,
adapted for our WebNexus implementation.
"""

import hashlib
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OriginalChunk:
    """Represents a document chunk using original project structure"""
    content: str
    chunk_index: int
    char_count: int
    word_count: int
    content_hash: str
    metadata: Dict[str, Any]


class OriginalArchonChunker:
    """
    Exact replication of the original Archon project's chunking strategy.
    
    This uses the smart_chunk_text approach from BaseStorageService:
    - Default chunk size: 5000 characters
    - Priority: code blocks -> paragraphs -> sentences
    - No overlap between chunks
    - Simple, effective boundary detection
    """
    
    def __init__(self, chunk_size: int = 5000):
        """
        Initialize with original project defaults
        
        Args:
            chunk_size: Maximum chunk size (default: 5000 to match original)
        """
        self.chunk_size = chunk_size
        
    def smart_chunk_text(self, text: str) -> List[str]:
        """
        Split text into chunks intelligently, preserving context.
        
        This is the EXACT implementation from the original project's BaseStorageService.
        
        Priority for break points:
        1. Code blocks (```) - highest priority  
        2. Paragraph breaks (\\n\\n)
        3. Sentence boundaries (. )
        4. Force split if necessary
        
        Args:
            text: Text to chunk
            
        Returns:
            List of text chunks
        """
        if not text or not isinstance(text, str):
            logger.warning("Invalid text provided for chunking")
            return []

        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Determine the end of this chunk
            end = start + self.chunk_size

            # If we're at the end of the text, take what's left
            if end >= text_length:
                chunk = text[start:].strip()
                if chunk:
                    chunks.append(chunk)
                break

            # Try to find a good break point
            chunk = text[start:end]

            # First, try to break at a code block boundary
            code_block_pos = chunk.rfind("```")
            if code_block_pos != -1 and code_block_pos > self.chunk_size * 0.3:
                end = start + code_block_pos

            # If no code block, try paragraph break
            elif "\n\n" in chunk:
                last_break = chunk.rfind("\n\n")
                if last_break > self.chunk_size * 0.3:
                    end = start + last_break

            # If no paragraph break, try sentence break
            elif ". " in chunk:
                last_period = chunk.rfind(". ")
                if last_period > self.chunk_size * 0.3:
                    end = start + last_period + 1

            # Extract chunk and clean it up
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)

            # Move start position for next chunk (NO OVERLAP)
            start = end

        return chunks
    
    def extract_metadata(self, chunk: str, base_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Extract metadata from a text chunk using original project approach.
        
        Args:
            chunk: Text chunk to analyze
            base_metadata: Optional base metadata to extend
            
        Returns:
            Dictionary containing metadata
        """
        import re
        
        # Extract headers (same as original)
        headers = re.findall(r"^(#+)\s+(.+)$", chunk, re.MULTILINE)
        header_str = "; ".join([f"{h[0]} {h[1]}" for h in headers]) if headers else ""

        # Extract basic stats (same as original)
        metadata = {
            "headers": header_str,
            "char_count": len(chunk),
            "word_count": len(chunk.split()),
            "line_count": len(chunk.splitlines()),
            "has_code": "```" in chunk,
            "has_links": "http" in chunk or "www." in chunk,
        }

        # Merge with base metadata if provided (same as original)
        if base_metadata:
            metadata.update(base_metadata)

        return metadata
    
    def chunk_document(self, content: str, url: str = "", base_metadata: Optional[Dict[str, Any]] = None) -> List[OriginalChunk]:
        """
        Chunk a document using the original project's approach.
        
        Args:
            content: Document content to chunk
            url: Document URL (for logging)
            base_metadata: Base metadata to include in all chunks
            
        Returns:
            List of OriginalChunk objects
        """
        if not content or len(content.strip()) < 10:
            logger.warning(f"Content too short for chunking: {url}")
            return []
        
        # Use original chunking strategy
        text_chunks = self.smart_chunk_text(content)
        
        if not text_chunks:
            logger.warning(f"No chunks created for document: {url}")
            return []
        
        # Create OriginalChunk objects with metadata
        document_chunks = []
        for i, chunk_content in enumerate(text_chunks):
            # Generate content hash for deduplication
            content_hash = hashlib.md5(chunk_content.encode('utf-8')).hexdigest()
            
            # Extract metadata using original approach
            metadata = self.extract_metadata(chunk_content, base_metadata)
            
            chunk = OriginalChunk(
                content=chunk_content,
                chunk_index=i,
                char_count=len(chunk_content),
                word_count=len(chunk_content.split()),
                content_hash=content_hash,
                metadata=metadata
            )
            document_chunks.append(chunk)
        
        logger.info(f"Created {len(document_chunks)} chunks using original strategy for: {url[:100]}...")
        return document_chunks


class OriginalStorageAdapter:
    """
    Adapter to integrate original chunking with our storage system.
    
    This bridges the original project's chunking approach with our
    SQLite + FAISS storage implementation.
    """
    
    def __init__(self, chunk_size: int = 5000):
        """Initialize with original project settings"""
        self.chunker = OriginalArchonChunker(chunk_size)
    
    def prepare_for_storage(self, content: str, url: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Prepare content for storage using original chunking strategy.
        
        Returns data structure compatible with our storage service.
        """
        # Use original chunking
        chunks = self.chunker.chunk_document(content, url, metadata)
        
        if not chunks:
            return {
                "success": False,
                "chunks": [],
                "total_chunks": 0,
                "error": "No chunks could be created"
            }
        
        # Convert to format expected by our storage service
        prepared_chunks = []
        for chunk in chunks:
            prepared_chunk = {
                "content": chunk.content,
                "chunk_index": chunk.chunk_index,
                "char_count": chunk.char_count,
                "word_count": chunk.word_count,
                "content_hash": chunk.content_hash,
                "metadata": chunk.metadata,
                # Additional fields for our storage system
                "start_char": 0,  # Original project doesn't track positions
                "end_char": chunk.char_count,
            }
            prepared_chunks.append(prepared_chunk)
        
        return {
            "success": True,
            "chunks": prepared_chunks,
            "total_chunks": len(chunks),
            "chunking_strategy": "original_archon",
            "chunk_size": self.chunker.chunk_size,
            "url": url,
            "metadata": metadata or {}
        }


# Default instance using original project settings
original_chunker = OriginalArchonChunker(chunk_size=5000)
original_adapter = OriginalStorageAdapter(chunk_size=5000)