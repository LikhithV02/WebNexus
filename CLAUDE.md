# WebNexus: Simplified Web Crawler & RAG System

A production-ready web crawler and RAG system with multi-strategy crawling, hybrid search, and complete MCP integration—powered by open-source models and local storage.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Server    │◄──►│  FastAPI Server │◄──►│  SQLite + Vector│
│   (Port 8051)   │    │   (Port 8000)   │    │    Database     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   MCP Tools              Web Crawling              Document Storage
 - crawl_website         - All 4 strategies          - Embeddings
 - search_docs          - Progress tracking         - Chunking
 - get_sources          - Error handling            - Vector search
```

## Core Features

- **Multi-Strategy Web Crawling**: Single page, batch, recursive, and sitemap crawling
- **Hybrid RAG**: Vector + keyword search with BM25 reranking
- **Open-Source Models**: Stella EN 400M v5 embeddings (no API keys needed)
- **MCP Integration**: Tools for AI agents and coding assistants
- **Local Database**: SQLite + FAISS for full local operation
- **Multi-Index Support**: Organize documents into topic-specific vector indexes

## Quick Start

### 1. Dependencies

Full dependency list in `pyproject.toml`. Key dependencies:
- **Web Crawling**: crawl4ai, httpx
- **AI/ML**: sentence-transformers, torch, transformers
- **Database**: SQLAlchemy, FAISS, rank-bm25
- **API**: FastAPI, uvicorn, MCP

```bash
uv sync  # Install all dependencies
```

### 2. Database Setup

```bash
# Initialize database and download models (one-time setup)
uv run python scripts/setup_db.py

# This will:
# - Create SQLite database with proper schema
# - Download Stella EN 400M v5 embedding model (~800MB)
# - Initialize FAISS vector indexes
# - Test all services
```

### 3. Start Services

```bash
# Option 1: Use the startup script (recommended)
uv run python scripts/run_servers.py

# Option 2: Start servers individually
# Terminal 1: FastAPI server
uv run uvicorn src.api.main:app --reload --port 8000

# Terminal 2: MCP server (for AI agents)
uv run python src.mcp/server.py --stdio
```

### 4. Verify System

```bash
# Check health
curl http://localhost:8000/health

# Interactive API docs
curl http://localhost:8000/docs

# Test crawling
curl -X POST http://localhost:8000/api/crawl/single \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "store_documents": true}'

# Test search
curl -X POST http://localhost:8000/api/search/query \
  -H "Content-Type: application/json" \
  -d '{"query": "test search", "search_type": "hybrid"}'
```

### 5. Test MCP Server

```bash
# Run comprehensive MCP tests
uv run python scripts/test_mcp.py
```

## Document Chunking Strategies

WebNexus supports three chunking strategies. Default is "original" (matches Archon project).

### Strategy Comparison

| Feature | Original Archon | Advanced Custom | Specialized |
|---------|------------------|------------------|-------------|
| **Chunk Size** | 5000 chars | 1000 chars | Variable |
| **Overlap** | None | 100 chars | None |
| **Boundaries** | 3 types | 5+ types | Content-aware |
| **Performance** | Fast | Moderate | Fast |
| **Quality** | Good | High | Excellent |
| **Use Case** | General docs | RAG optimization | Code/structured data |

### Configuration

```python
# In settings.py or environment variables
CHUNKING_STRATEGY=original     # Default - matches Archon
CHUNKING_STRATEGY=advanced     # Better for RAG
CHUNKING_STRATEGY=specialized  # Best for code/markdown

# Runtime switching
from src.config.settings import settings
settings.chunking_strategy = "advanced"
```

**Original Archon Strategy:**
- 5000 character chunks (no overlap)
- Intelligent boundaries: code blocks → paragraphs → sentences
- 30% minimum chunk size rule
- Same metadata extraction as original project

**Advanced Strategy:**
- 1000 character chunks with 100 character overlap
- Complex boundary detection (headers, code blocks, lists, paragraphs)
- Semantic similarity optimization
- Context preservation between chunks

**Specialized Strategy:**
- Language-specific chunking for code (Python, JavaScript, Java, C++)
- Markdown structure preservation (headers, lists, tables)
- HTML element boundary detection
- JSON/XML structure awareness

## API Reference

### Crawling Endpoints (`webnexus/api/crawl.py`)

```python
# Single page crawling
POST /api/crawl/single
{
  "url": "https://example.com",
  "store_documents": true,
  "index_name": "my-docs"  # Optional: specify target index
}

# Batch crawling (up to 100 URLs)
POST /api/crawl/batch
{
  "urls": ["https://site1.com", "https://site2.com"],
  "max_concurrent": 5,
  "store_documents": true,
  "index_name": "my-docs"  # Optional
}

# Progress monitoring
GET  /api/crawl/status/{session_id}
GET  /api/crawl/active
POST /api/crawl/cancel/{session_id}
POST /api/crawl/cleanup
```

### Search Endpoints (`webnexus/api/search.py`)

```python
# Hybrid search with reranking
POST /api/search/query
{
  "query": "machine learning algorithms",
  "top_k": 10,
  "search_type": "hybrid",  // vector, keyword, or hybrid
  "vector_weight": 0.7,
  "keyword_weight": 0.3,
  "use_reranking": true,
  "rerank_strategy": "hybrid",  // bm25, hybrid, or quality
  "index_name": "my-docs"  // Optional: search specific index
}

# Simple search
GET /api/search/simple?q=machine+learning&limit=5&type=hybrid

# Search within document
POST /api/search/document
{
  "document_id": "doc_123",
  "query": "specific topic",
  "max_chunks": 5
}

# Document management
GET  /api/search/documents?limit=50&url_pattern=github.com
GET  /api/search/stats
```

### Search Response Format

```json
{
  "success": true,
  "results": [
    {
      "document_id": "doc_123",
      "chunk_id": "chunk_456",
      "title": "Machine Learning Guide",
      "content": "Machine learning algorithms...",
      "url": "https://example.com/ml-guide",
      "similarity_score": 0.89,
      "keyword_score": 0.76,
      "combined_score": 0.84
    }
  ],
  "total_results": 15,
  "query": "machine learning algorithms",
  "search_time_ms": 245.7,
  "search_strategy": "hybrid+hybrid_rerank"
}
```

### Index Management Endpoints (`webnexus/api/indexes.py`)

```python
# Create new index
POST /api/indexes
{
  "name": "python-docs",
  "description": "Python documentation and tutorials"
}

# List all indexes
GET /api/indexes

# Get specific index
GET /api/indexes/{index_name}

# Delete index
DELETE /api/indexes/{index_name}?delete_documents=true

# Get index statistics
GET /api/indexes/{index_name}/stats
```

## MCP Tools

Complete Model Context Protocol server with 6 production-ready tools.

### 1. crawl_website

Multi-strategy web crawling for AI agents.

```python
await crawl_website(
    url="https://docs.python.org",
    strategy="recursive",     # single_page, batch, recursive, sitemap
    max_depth=2,
    max_pages=50,
    store_documents=True,
    index_name="python-docs"  # Optional: target index
)

# Returns:
{
  "success": true,
  "session_id": "mcp_crawl_20250131_140532",
  "strategy": "recursive",
  "documents_stored": 23,
  "pages_crawled": 23
}
```

### 2. search_documents

Advanced RAG search with hybrid ranking.

```python
await search_documents(
    query="Python async programming best practices",
    max_results=10,
    search_type="hybrid",
    use_reranking=True,
    similarity_threshold=0.1,
    index_name="python-docs"  # Optional: search specific index
)

# Returns ranked results with scores
```

### 3. get_sources

Document source management and filtering.

```python
await get_sources(
    limit=25,
    url_pattern="github.com",
    source_type="webpage",
    index_name="python-docs"  # Optional: filter by index
)

# Returns source inventory with metadata
```

### 4. list_indexes

List all vector indexes with metadata.

```python
await list_indexes()

# Returns: List of all indexes with document counts and metadata
```

### 5. create_index

Create a new topic-specific vector index.

```python
await create_index(
    name="python-docs",
    description="Python documentation and tutorials"
)
```

### 6. delete_index

Delete a vector index and optionally its documents.

```python
await delete_index(
    name="python-docs",
    delete_documents=True
)
```

## Multi-Index Architecture

Organize documents into separate, topic-specific vector indexes for better search precision.

### What is Multi-Index Support?

Create and manage multiple independent FAISS vector indexes, each containing documents for specific topics:
- `python-docs`: All Python documentation
- `react-tutorials`: React learning resources
- `company-wiki`: Internal company documentation

### Key Benefits

1. **Improved Search Precision**: Search within specific domains reduces noise
2. **Better Organization**: Logical separation of knowledge domains
3. **Faster Queries**: Smaller indexes = faster searches
4. **Easy Management**: Delete, backup, or share topic indexes independently
5. **Resource Efficiency**: Load only the indexes you need

### Quick Start Example

```bash
# 1. Create topic-specific index
curl -X POST http://localhost:8000/api/indexes \
  -H "Content-Type: application/json" \
  -d '{"name": "python-docs", "description": "Python documentation"}'

# 2. Crawl into the new index
curl -X POST http://localhost:8000/api/crawl/single \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://docs.python.org",
    "index_name": "python-docs",
    "store_documents": true
  }'

# 3. Search within the index
curl -X POST http://localhost:8000/api/search/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "async programming",
    "index_name": "python-docs",
    "search_type": "hybrid"
  }'
```

### Organization Strategies

1. **By Topic**: `python-docs`, `javascript-docs`, `devops-docs`
2. **By Project**: `project-alpha`, `project-beta`, `project-gamma`
3. **By Client**: `client-acme`, `client-globex`, `client-initech`
4. **By Content Type**: `tutorials`, `api-references`, `blog-posts`

### Migration from Single-Index

```bash
# Migrate existing documents to multi-index system
uv run python scripts/migrate_to_multi_index.py

# Creates default "general" index and migrates all existing documents
```

## Configuration & Resources

### Environment Variables

```bash
CHUNKING_STRATEGY=original  # original, advanced, or specialized
DATABASE_URL=sqlite:///./data/webnexus.db
FAISS_INDEX_DIR=./data/faiss_indexes
EMBEDDING_MODEL=dunzhang/stella_en_400M_v5
```

### Performance Metrics

- **Vector Search**: ~200ms for 10k documents
- **BM25 Search**: ~100ms with automatic caching
- **Hybrid Search**: ~400ms
- **Reranking**: +100-200ms
- **Memory Usage**: ~4-5GB RAM (includes embedding model)
- **Crawl Speed**: 5-10 pages/sec

### Documentation Links

- [Crawl4AI Documentation](https://crawl4ai.com/)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [sentence-transformers Models](https://huggingface.co/sentence-transformers)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

### System Architecture

- **Database**: SQLAlchemy models + FAISS vector storage
- **Embeddings**: Stella EN 400M v5 (1024 dimensions)
- **Search**: Hybrid vector similarity + BM25 keyword search
- **Reranking**: Multi-strategy (BM25, hybrid, quality-based)
- **API**: FastAPI with async support and OpenAPI docs
- **MCP**: FastMCP framework with 6 production-ready tools
