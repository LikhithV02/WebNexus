"""Document storage and retrieval service"""

import hashlib
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import numpy as np

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from ..config.database import db_config
from ..models.database import Document, DocumentChunk as DBDocumentChunk, Embedding, CodeExample, CrawlSession
from ..services.embedding_service import embedding_service
from ..services.vector_service import vector_service
from ..utils.chunking import default_chunker, SpecializedChunkers, DocumentChunk as ChunkingDocumentChunk
from ..utils.original_chunking import original_adapter
from ..utils.document_processing import DocumentProcessor
from ..utils.documentation_chunking import DocumentationChunker, DocumentationChunk

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


class StorageService:
    """Service for storing and retrieving documents with vector embeddings"""
    
    def __init__(self):
        """Initialize storage service"""
        self.db_config = db_config
        self.embedding_service = embedding_service
        self.vector_service = vector_service
        self.document_processor = DocumentProcessor()
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.db_config.get_session()
    
    async def store_document(
        self,
        url: str,
        content: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        crawl_type: str = "webpage",
        source_id: Optional[str] = None,
        process_immediately: bool = True,
        index_name: str = "default"
    ) -> Document:
        """
        Store a document with optional immediate processing
        
        Args:
            url: Document URL
            content: Document content
            title: Document title
            metadata: Additional metadata
            crawl_type: Type of crawl (webpage, sitemap, text_file)
            source_id: Source identifier
            process_immediately: Whether to process chunks and embeddings immediately
            index_name: Name of the vector index to store document in
        
        Returns:
            Stored Document instance
        """
        # Validate that the specified index exists
        index_mgr = get_index_manager()
        vector_index = index_mgr.get_index(index_name)
        if not vector_index:
            raise ValueError(f"Vector index '{index_name}' does not exist. Create it first with index_manager.create_index()")
        
        if not content or len(content.strip()) < 10:
            raise ValueError("Content is too short or empty")
        
        # Generate content hash for deduplication
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # Extract metadata
        if not metadata:
            metadata = {}
        
        doc_metadata = self.document_processor.extract_metadata(content, url)
        metadata.update(doc_metadata)
        
        # Parse URL for source_id if not provided
        if not source_id:
            parsed_url = urlparse(url)
            source_id = parsed_url.netloc or parsed_url.path
        
        db_session = self.get_session()
        doc_id = None
        try:
            # Check if document already exists
            existing_doc = db_session.query(Document).filter(
                or_(Document.url == url, Document.content_hash == content_hash)
            ).first()
            
            if existing_doc:
                logger.info(f"Document already exists: {url}")
                return existing_doc
            
            # Create new document with vector_index_id
            document = Document(
                url=url,
                title=title or metadata.get("title", ""),
                content=content,
                content_hash=content_hash,
                source_id=source_id,
                domain=metadata.get("domain", ""),
                word_count=metadata.get("word_count", 0),
                char_count=metadata.get("char_count", 0),
                crawl_type=crawl_type,
                metadata=metadata,
                is_processed=False,
                vector_index_id=vector_index.id
            )
            
            db_session.add(document)
            db_session.commit()
            db_session.refresh(document)
            
            logger.info(f"Stored document: {url} (ID: {document.id})")
            
            # Get document ID for later processing
            doc_id = document.id
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error storing document {url}: {e}")
            raise
        finally:
            db_session.close()
        
        # Process immediately if requested (with its own session)
        # This must happen AFTER the session is closed
        if process_immediately and doc_id:
            try:
                await self.process_document(doc_id, index_name=index_name)
            except Exception as e:
                logger.error(f"Error processing document {doc_id}: {e}")
                # Don't fail the store operation if processing fails
        
        # Retrieve the document again to return it (with a fresh session)
        db_session2 = self.get_session()
        try:
            document = db_session2.query(Document).filter(Document.id == doc_id).first()
            return document
        finally:
            db_session2.close()
    
    async def process_document(self, document_id: int, db_session: Optional[Session] = None, index_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a document: chunk, embed, and store vectors
        
        Args:
            document_id: Document ID to process
            db_session: Optional database session
            index_name: Optional index name (if not provided, uses document's vector_index)
        
        Returns:
            Processing results
        """
        if db_session is None:
            db_session = self.get_session()
            should_close = True
        else:
            should_close = False
        
        try:
            # Get document
            document = db_session.query(Document).filter(Document.id == document_id).first()
            if not document:
                raise ValueError(f"Document not found: {document_id}")
            
            if document.is_processed:
                logger.info(f"Document already processed: {document_id}")
                return {"status": "already_processed", "chunks": 0}
            
            # Determine which vector index to use
            if index_name:
                # Use specified index
                index_mgr = get_index_manager()
                vector_index = index_mgr.get_index(index_name)
                if not vector_index:
                    raise ValueError(f"Vector index '{index_name}' does not exist")
                target_vector_service = index_mgr.get_vector_service(index_name)
            elif document.vector_index_id:
                # Use document's assigned index
                from ..models.database import VectorIndex
                vector_index = db_session.query(VectorIndex).filter(VectorIndex.id == document.vector_index_id).first()
                if not vector_index:
                    raise ValueError(f"Document's vector index (ID: {document.vector_index_id}) not found")
                index_mgr = get_index_manager()
                target_vector_service = index_mgr.get_vector_service(str(vector_index.name))
            else:
                # Fallback to default global vector_service (backward compatibility)
                target_vector_service = self.vector_service
                logger.warning(f"Document {document_id} has no vector_index_id, using global vector_service")
            
            logger.info(f"Processing document: {document.url} (ID: {document_id})")
            
            # Choose chunking strategy based on configuration
            from ..config.settings import settings
            chunking_strategy = settings.chunking_strategy
            
            logger.info(f"Using chunking strategy: {chunking_strategy}")
            
            if chunking_strategy == "original":
                # Use original project's chunking strategy (5000 char chunks, no overlap)
                chunking_result = original_adapter.prepare_for_storage(
                    document.content, 
                    document.url,
                    {
                        "source_id": document.source_id,
                        "crawl_type": document.crawl_type,
                        "document_id": document_id
                    }
                )
                
                if not chunking_result["success"]:
                    logger.warning(f"Original chunking failed for document: {document_id}")
                    document.is_processed = True
                    document.processing_error = chunking_result.get("error", "Chunking failed")
                    db_session.commit()
                    return {"status": "chunking_failed", "chunks": 0}
                
                # Convert to our chunk format
                chunks = []
                for chunk_data in chunking_result["chunks"]:
                    chunk = ChunkingDocumentChunk(
                        content=chunk_data["content"],
                        start_char=chunk_data["start_char"],
                        end_char=chunk_data["end_char"],
                        chunk_index=chunk_data["chunk_index"],
                        word_count=chunk_data["word_count"],
                        char_count=chunk_data["char_count"],
                        content_hash=chunk_data["content_hash"]
                    )
                    chunks.append(chunk)
            elif chunking_strategy == "specialized":
                # Use specialized chunkers for specific content types
                if document.crawl_type == "text_file" and document.url.endswith(('.py', '.js', '.java', '.cpp')):
                    language = document.url.split('.')[-1]
                    chunks = SpecializedChunkers.chunk_code(document.content, language)
                elif document.content.startswith('#') or '##' in document.content:
                    chunks = SpecializedChunkers.chunk_markdown(document.content)
                else:
                    chunks = default_chunker.chunk_document(document.content, document.url)
            
            elif chunking_strategy == "advanced":
                # Use advanced chunker with boundary detection and overlap
                chunks = default_chunker.chunk_document(document.content, document.url)

            elif chunking_strategy == "documentation":
                # Use documentation chunker for package documentation
                # Token-based, no overlap, markdown-aware, smart merging
                doc_chunker = DocumentationChunker(
                    max_tokens=settings.documentation_max_tokens,
                    similarity_threshold=settings.documentation_similarity_threshold,
                    max_level_difference=settings.documentation_max_level_difference,
                    enable_merging=settings.documentation_enable_merging,
                    similarity_method=settings.documentation_similarity_method
                )

                doc_chunks = doc_chunker.chunk_document(
                    document.content,
                    document.url,
                    {
                        "source_id": document.source_id,
                        "crawl_type": document.crawl_type,
                        "document_id": document_id
                    }
                )

                # Convert DocumentationChunk to ChunkingDocumentChunk format
                chunks = []
                for doc_chunk in doc_chunks:
                    chunk = ChunkingDocumentChunk(
                        content=doc_chunk.content,
                        start_char=doc_chunk.start_char,
                        end_char=doc_chunk.end_char,
                        chunk_index=doc_chunk.chunk_index,
                        word_count=doc_chunk.word_count,
                        char_count=doc_chunk.char_count,
                        content_hash=doc_chunk.content_hash
                    )
                    chunks.append(chunk)

            else:
                # Default fallback to original strategy
                logger.warning(f"Unknown chunking strategy '{chunking_strategy}', falling back to original")
                chunking_result = original_adapter.prepare_for_storage(
                    document.content, 
                    document.url,
                    {
                        "source_id": document.source_id,
                        "crawl_type": document.crawl_type,
                        "document_id": document_id
                    }
                )
                
                if chunking_result["success"]:
                    chunks = []
                    for chunk_data in chunking_result["chunks"]:
                        chunk = ChunkingDocumentChunk(
                            content=chunk_data["content"],
                            start_char=chunk_data["start_char"],
                            end_char=chunk_data["end_char"],
                            chunk_index=chunk_data["chunk_index"],
                            word_count=chunk_data["word_count"],
                            char_count=chunk_data["char_count"],
                            content_hash=chunk_data["content_hash"]
                        )
                        chunks.append(chunk)
                else:
                    chunks = []
            
            if not chunks:
                logger.warning(f"No chunks created for document: {document_id}")
                document.is_processed = True
                document.processing_error = "No chunks created"
                db_session.commit()
                return {"status": "no_chunks", "chunks": 0}
            
            # Store chunks in database
            chunk_objects = []
            chunk_texts = []
            
            for chunk_data in chunks:
                # Check for duplicate chunk
                existing_chunk = db_session.query(DBDocumentChunk).filter(
                    DBDocumentChunk.content_hash == chunk_data.content_hash
                ).first()
                
                if existing_chunk:
                    continue
                
                chunk_obj = DBDocumentChunk(
                    document_id=document_id,
                    content=chunk_data.content,
                    content_hash=chunk_data.content_hash,
                    chunk_index=chunk_data.chunk_index,
                    start_char=chunk_data.start_char,
                    end_char=chunk_data.end_char,
                    word_count=chunk_data.word_count,
                    char_count=chunk_data.char_count
                )
                
                db_session.add(chunk_obj)
                chunk_objects.append(chunk_obj)
                chunk_texts.append(chunk_data.content)
            
            db_session.commit()
            
            # Refresh chunk objects to get IDs
            for chunk_obj in chunk_objects:
                db_session.refresh(chunk_obj)
            
            # Create embeddings
            if chunk_texts:
                logger.info(f"Creating embeddings for {len(chunk_texts)} chunks")
                embeddings = await self.embedding_service.embed_documents(chunk_texts)
                
                # Store embeddings and vectors
                embedding_objects = []
                vectors = []
                chunk_ids = []
                
                for chunk_obj, embedding_vector in zip(chunk_objects, embeddings):
                    # Store embedding metadata in database
                    embedding_obj = Embedding(
                        chunk_id=chunk_obj.id,
                        model_name=self.embedding_service.model_name,
                        embedding_dimension=len(embedding_vector),
                        vector_data=embedding_vector  # Optional backup
                    )
                    
                    db_session.add(embedding_obj)
                    embedding_objects.append(embedding_obj)
                    vectors.append(embedding_vector)
                    chunk_ids.append(chunk_obj.id)
                
                db_session.commit()
                
                # Store vectors in FAISS (using the target vector service)
                if vectors:
                    vectors_array = np.array(vectors)
                    faiss_indices = target_vector_service.add_vectors(
                        vectors_array,
                        chunk_ids,
                        [{"document_id": document_id, "chunk_id": chunk_id} for chunk_id in chunk_ids]
                    )
                    
                    # Update chunks with FAISS indices
                    for chunk_obj, faiss_idx in zip(chunk_objects, faiss_indices):
                        chunk_obj.faiss_index = faiss_idx
                    
                    db_session.commit()
                    
                    # Save FAISS index
                    target_vector_service.save_index()
            
            # Mark document as processed
            document.is_processed = True
            db_session.commit()
            
            logger.info(f"Successfully processed document {document_id}: {len(chunk_objects)} chunks")
            
            return {
                "status": "success",
                "chunks": len(chunk_objects),
                "embeddings": len(embeddings) if chunk_texts else 0,
                "document_id": document_id
            }
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error processing document {document_id}: {e}")
            
            # Mark document as failed
            document = db_session.query(Document).filter(Document.id == document_id).first()
            if document:
                document.is_processed = True
                document.processing_error = str(e)
                db_session.commit()
            
            raise
        finally:
            if should_close:
                db_session.close()
    
    async def store_code_example(
        self, 
        document_id: int, 
        code: str, 
        language: Optional[str] = None,
        summary: Optional[str] = None,
        context_before: Optional[str] = None,
        context_after: Optional[str] = None,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None
    ) -> CodeExample:
        """Store a code example"""
        db_session = self.get_session()
        try:
            code_example = CodeExample(
                document_id=document_id,
                code=code,
                language=language,
                summary=summary,
                context_before=context_before,
                context_after=context_after,
                start_line=start_line,
                end_line=end_line
            )
            
            db_session.add(code_example)
            db_session.commit()
            db_session.refresh(code_example)
            
            # Create embedding for code example (for code search)
            code_text = f"{summary or ''}\n{code}"
            embedding = await self.embedding_service.embed_documents([code_text])
            
            if embedding:
                # Get document to determine which vector index to use
                document = db_session.query(Document).filter(Document.id == document_id).first()
                
                # Determine target vector service
                if document and hasattr(document, 'vector_index_id') and document.vector_index_id:
                    from ..models.database import VectorIndex
                    vector_index = db_session.query(VectorIndex).filter(VectorIndex.id == document.vector_index_id).first()
                    if vector_index:
                        index_mgr = get_index_manager()
                        target_vector_service = index_mgr.get_vector_service(str(vector_index.name))
                    else:
                        target_vector_service = self.vector_service
                else:
                    target_vector_service = self.vector_service
                
                # Store in FAISS for code search
                vectors_array = np.array(embedding)
                faiss_indices = target_vector_service.add_vectors(
                    vectors_array,
                    [code_example.id],
                    [{"document_id": document_id, "code_example_id": code_example.id, "type": "code"}]
                )
                
                if faiss_indices:
                    code_example.faiss_index = faiss_indices[0]
                    db_session.commit()
            
            return code_example
            
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error storing code example: {e}")
            raise
        finally:
            db_session.close()
    
    def get_document(self, document_id: int) -> Optional[Document]:
        """Get document by ID"""
        db_session = self.get_session()
        try:
            return db_session.query(Document).filter(Document.id == document_id).first()
        finally:
            db_session.close()
    
    def get_documents_by_source(self, source_id: str, limit: int = 100) -> List[Document]:
        """Get documents by source ID"""
        db_session = self.get_session()
        try:
            return db_session.query(Document).filter(
                Document.source_id == source_id
            ).order_by(Document.created_at.desc()).limit(limit).all()
        finally:
            db_session.close()
    
    def search_documents(
        self, 
        query: Optional[str] = None,
        source_id: Optional[str] = None,
        crawl_type: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Document]:
        """Search documents with filters"""
        db_session = self.get_session()
        try:
            query_obj = db_session.query(Document)
            
            # Apply filters
            if query:
                query_obj = query_obj.filter(
                    or_(
                        Document.title.ilike(f'%{query}%'),
                        Document.content.ilike(f'%{query}%'),
                        Document.url.ilike(f'%{query}%')
                    )
                )
            
            if source_id:
                query_obj = query_obj.filter(Document.source_id == source_id)
            
            if crawl_type:
                query_obj = query_obj.filter(Document.crawl_type == crawl_type)
            
            return query_obj.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()
            
        finally:
            db_session.close()
    
    def get_chunk_with_context(self, chunk_id: int) -> Dict[str, Any]:
        """Get chunk with surrounding context"""
        db_session = self.get_session()
        try:
            chunk = db_session.query(DBDocumentChunk).filter(DBDocumentChunk.id == chunk_id).first()
            if not chunk:
                return None
            
            # Get document for full context
            document = chunk.document
            
            # Get surrounding chunks
            prev_chunk = db_session.query(DBDocumentChunk).filter(
                and_(
                    DBDocumentChunk.document_id == chunk.document_id,
                    DBDocumentChunk.chunk_index == chunk.chunk_index - 1
                )
            ).first()
            
            next_chunk = db_session.query(DBDocumentChunk).filter(
                and_(
                    DBDocumentChunk.document_id == chunk.document_id,
                    DBDocumentChunk.chunk_index == chunk.chunk_index + 1
                )
            ).first()
            
            return {
                "chunk": chunk.to_dict(),
                "document": {
                    "id": document.id,
                    "url": document.url,
                    "title": document.title,
                    "source_id": document.source_id,
                    "domain": document.domain
                },
                "context": {
                    "before": prev_chunk.content if prev_chunk else "",
                    "after": next_chunk.content if next_chunk else ""
                }
            }
            
        finally:
            db_session.close()
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        db_session = self.get_session()
        try:
            doc_count = db_session.query(func.count(Document.id)).scalar()
            chunk_count = db_session.query(func.count(DBDocumentChunk.id)).scalar()
            embedding_count = db_session.query(func.count(Embedding.id)).scalar()
            code_count = db_session.query(func.count(CodeExample.id)).scalar()
            
            # Get source distribution
            sources = db_session.query(
                Document.source_id,
                func.count(Document.id).label('count')
            ).group_by(Document.source_id).all()
            
            # Get crawl type distribution
            crawl_types = db_session.query(
                Document.crawl_type,
                func.count(Document.id).label('count')
            ).group_by(Document.crawl_type).all()
            
            return {
                "total_documents": doc_count,
                "total_chunks": chunk_count,
                "total_embeddings": embedding_count,
                "code_examples": code_count,
                "sources": {source: count for source, count in sources},
                "crawl_types": {ctype: count for ctype, count in crawl_types},
                "vector_stats": self.vector_service.get_stats()
            }
            
        finally:
            db_session.close()


# Global storage service instance
storage_service = StorageService()