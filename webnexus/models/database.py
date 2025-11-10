"""Database models for WebNexus"""

from datetime import datetime
from typing import Optional, Dict, Any, List
import json

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()


class VectorIndex(Base):
    """Multiple vector indexes for topic/project separation"""
    __tablename__ = "vector_indexes"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    
    # Index configuration
    index_type = Column(String, default="IndexFlatIP")
    embedding_dimension = Column(Integer, default=1024)
    embedding_model = Column(String, default="dunzhang/stella_en_400M_v5")
    
    # File paths (relative to data/)
    index_path = Column(String, nullable=False)
    metadata_path = Column(String, nullable=False)
    
    # Statistics
    total_documents = Column(Integer, default=0)
    total_chunks = Column(Integer, default=0)
    total_vectors = Column(Integer, default=0)
    index_size_mb = Column(Float, default=0.0)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_indexed_at = Column(DateTime, nullable=True)
    
    # Additional settings
    config = Column(JSON, default=dict)
    
    # Relationships
    documents = relationship("Document", back_populates="vector_index")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "index_type": self.index_type,
            "embedding_dimension": self.embedding_dimension,
            "embedding_model": self.embedding_model,
            "index_path": self.index_path,
            "metadata_path": self.metadata_path,
            "total_documents": self.total_documents,
            "total_chunks": self.total_chunks,
            "total_vectors": self.total_vectors,
            "index_size_mb": self.index_size_mb,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_indexed_at": self.last_indexed_at.isoformat() if self.last_indexed_at else None,
            "config": self.config,
        }


class Document(Base):
    """Document storage model"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    content_hash = Column(String, index=True, nullable=False)  # For deduplication
    
    # Metadata
    source_id = Column(String, index=True, nullable=False)  # Domain or source identifier
    domain = Column(String, index=True, nullable=True)
    word_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    
    # Crawl metadata
    crawl_type = Column(String, nullable=True)  # webpage, sitemap, text_file
    crawl_timestamp = Column(DateTime, default=datetime.utcnow)
    
    # NEW: Vector index reference
    vector_index_id = Column(Integer, ForeignKey("vector_indexes.id"), nullable=True, index=True)
    
    # Additional metadata stored as JSON
    doc_metadata = Column(JSON, default=dict)
    
    # Status tracking
    is_processed = Column(Boolean, default=False)
    processing_error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    vector_index = relationship("VectorIndex", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    code_examples = relationship("CodeExample", back_populates="document", cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "url": self.url,
            "title": self.title,
            "content": self.content[:500] + "..." if len(self.content) > 500 else self.content,
            "source_id": self.source_id,
            "domain": self.domain,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "crawl_type": self.crawl_type,
            "crawl_timestamp": self.crawl_timestamp.isoformat() if self.crawl_timestamp else None,
            "metadata": self.doc_metadata,
            "is_processed": self.is_processed,
            "vector_index_id": self.vector_index_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DocumentChunk(Base):
    """Document chunks for RAG retrieval"""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    
    # Chunk content
    content = Column(Text, nullable=False)
    content_hash = Column(String, index=True, nullable=False)  # For deduplication
    chunk_index = Column(Integer, nullable=False)  # Order within document
    
    # Chunk metadata
    start_char = Column(Integer, nullable=True)  # Character position in original document
    end_char = Column(Integer, nullable=True)
    word_count = Column(Integer, default=0)
    char_count = Column(Integer, default=0)
    
    # Vector storage reference (FAISS index)
    faiss_index = Column(Integer, nullable=True)  # Index in FAISS vector store
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False, cascade="all, delete-orphan")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "word_count": self.word_count,
            "char_count": self.char_count,
            "faiss_index": self.faiss_index,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Embedding(Base):
    """Embedding vectors for document chunks"""
    __tablename__ = "embeddings"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id"), nullable=False, unique=True, index=True)
    
    # Embedding metadata
    model_name = Column(String, nullable=False)  # e.g., "dunzhang/stella_en_400M_v5"
    embedding_dimension = Column(Integer, nullable=False)  # e.g., 1024
    
    # Vector data stored as JSON (for backup/metadata - main vectors in FAISS)
    vector_data = Column(JSON, nullable=True)  # Optional backup of vector
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    chunk = relationship("DocumentChunk", back_populates="embedding")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "model_name": self.model_name,
            "embedding_dimension": self.embedding_dimension,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CodeExample(Base):
    """Code examples extracted from documents"""
    __tablename__ = "code_examples"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False, index=True)
    
    # Code content
    code = Column(Text, nullable=False)
    language = Column(String, nullable=True)  # Programming language
    summary = Column(Text, nullable=True)  # AI-generated summary
    
    # Context information
    context_before = Column(Text, nullable=True)  # Text before code block
    context_after = Column(Text, nullable=True)   # Text after code block
    
    # Position in document
    start_line = Column(Integer, nullable=True)
    end_line = Column(Integer, nullable=True)
    
    # Vector storage reference (FAISS index for code search)
    faiss_index = Column(Integer, nullable=True)
    
    # Metadata
    example_metadata = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    document = relationship("Document", back_populates="code_examples")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "code": self.code,
            "language": self.language,
            "summary": self.summary,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "faiss_index": self.faiss_index,
            "metadata": self.example_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CrawlSession(Base):
    """Track crawling sessions and their progress"""
    __tablename__ = "crawl_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True, nullable=False)  # UUID
    
    # Crawl configuration
    start_url = Column(String, nullable=False)
    crawl_type = Column(String, nullable=False)  # webpage, sitemap, text_file
    max_depth = Column(Integer, default=1)
    max_pages = Column(Integer, nullable=True)
    
    # Status tracking
    status = Column(String, default="started")  # started, running, completed, failed, cancelled
    
    # Progress metrics
    pages_discovered = Column(Integer, default=0)
    pages_crawled = Column(Integer, default=0)
    pages_processed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    code_examples_found = Column(Integer, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Configuration and results
    config = Column(JSON, default=dict)
    results = Column(JSON, default=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "start_url": self.start_url,
            "crawl_type": self.crawl_type,
            "max_depth": self.max_depth,
            "max_pages": self.max_pages,
            "status": self.status,
            "pages_discovered": self.pages_discovered,
            "pages_crawled": self.pages_crawled,
            "pages_processed": self.pages_processed,
            "chunks_created": self.chunks_created,
            "code_examples_found": self.code_examples_found,
            "error_message": self.error_message,
            "error_count": self.error_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "config": self.config,
            "results": self.results,
        }