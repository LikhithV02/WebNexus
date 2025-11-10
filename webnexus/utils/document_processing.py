"""Document processing utilities"""

import re
from typing import List, Dict, Any
from pathlib import Path


class DocumentProcessor:
    """Utility class for document processing operations"""
    
    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> List[str]:
        """Split text into overlapping chunks"""
        if not text or chunk_size <= 0:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            # Find the end of the chunk
            end = start + chunk_size
            
            # If we're not at the end of the text, try to break at a sentence or word boundary
            if end < len(text):
                # Look for sentence boundary
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start:
                    end = sentence_end + 1
                else:
                    # Look for word boundary
                    word_end = text.rfind(' ', start, end)
                    if word_end > start:
                        end = word_end
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # Move start position with overlap
            start = max(start + 1, end - overlap)
            
            # Avoid infinite loop
            if start >= len(text):
                break
        
        return chunks
    
    @staticmethod
    def extract_metadata(content: str, url: str = "") -> Dict[str, Any]:
        """Extract metadata from document content"""
        metadata = {
            "url": url,
            "word_count": len(content.split()),
            "char_count": len(content),
        }
        
        # Extract title from content (first heading or first line)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            metadata["title"] = title_match.group(1).strip()
        elif content:
            # Use first line as title
            first_line = content.split('\n')[0].strip()
            metadata["title"] = first_line[:100] + "..." if len(first_line) > 100 else first_line
        
        # Extract domain from URL
        if url:
            try:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                metadata["domain"] = parsed.netloc
            except Exception:
                metadata["domain"] = ""
        
        return metadata
    
    @staticmethod
    def clean_text(text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.\,\!\?\-\:\;]', ' ', text)
        
        # Remove excessive punctuation
        text = re.sub(r'[\.]{2,}', '.', text)
        text = re.sub(r'[\!\?]{2,}', '!', text)
        
        return text.strip()
    
    @staticmethod
    def is_valid_content(content: str, min_length: int = 50) -> bool:
        """Check if content is valid and substantial enough"""
        if not content or not isinstance(content, str):
            return False
        
        cleaned = DocumentProcessor.clean_text(content)
        return len(cleaned) >= min_length