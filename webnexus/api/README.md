# 🚀 WebNexus FastAPI Server

REST API server for web crawling and document search with hybrid RAG capabilities.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Server Setup](#server-setup)
- [API Endpoints](#api-endpoints)
- [Configuration](#configuration)
- [Usage Examples](#usage-examples)
- [Authentication](#authentication)
- [Error Handling](#error-handling)
- [Monitoring](#monitoring)

---

## Quick Start

### Start the Server

```bash
# Development mode (with auto-reload)
uv run uvicorn webnexus.api.main:app --reload --port 8000

# Production mode
uv run uvicorn webnexus.api.main:app --host 0.0.0.0 --port 8000 --workers 4

# With environment variables
PORT=8001 LOG_LEVEL=DEBUG uv run uvicorn webnexus.api.main:app --reload
```

### Access API Documentation

Once the server is running:

- **Interactive Docs (Swagger UI)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

---

## Server Setup

### Prerequisites

```bash
# Install dependencies
uv sync

# Initialize database and download models
uv run python scripts/setup_db.py
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Server Settings
HOST=0.0.0.0
PORT=8000
API_PORT=8000
LOG_LEVEL=INFO
DEBUG=false

# Database
DATABASE_URL=sqlite:///./data/webnexus.db

# Embedding Model
EMBEDDING_MODEL=dunzhang/stella_en_400M_v5
EMBEDDING_DIMENSIONS=1024
EMBEDDING_BATCH_SIZE=100
EMBEDDING_DEVICE=auto  # auto, cpu, or cuda

# Crawling
MAX_CONCURRENT_CRAWLS=10
MAX_CRAWL_DEPTH=3
CRAWL_TIMEOUT=30

# Search
DEFAULT_SEARCH_LIMIT=5
USE_HYBRID_SEARCH=true
USE_RERANKING=true

# Chunking
CHUNKING_STRATEGY=original  # original, advanced, or specialized
ORIGINAL_CHUNK_SIZE=5000
ADVANCED_CHUNK_SIZE=1000
CHUNK_OVERLAP=100

# CORS
CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:3000"]
```

### Directory Structure

```
webnexus/api/
├── README.md           # This file
├── __init__.py
├── main.py            # FastAPI app with lifespan management
├── crawl.py           # Crawling endpoints
└── search.py          # Search and RAG endpoints
```

---

## API Endpoints

### Core Endpoints

#### Health Check
```http
GET /health
```
Returns server health status and service availability.

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "database": "connected",
    "embedding_service": "loaded",
    "vector_service": "ready"
  }
}
```

#### System Statistics
```http
GET /api/stats
```
Returns comprehensive system statistics.

**Response:**
```json
{
  "documents": 156,
  "chunks": 1847,
  "vectors": 1847,
  "indexes": 3,
  "storage_size_mb": 245.7
}
```

---

### Crawling Endpoints

#### 1. Single Page Crawl
```http
POST /api/crawl/single
Content-Type: application/json

{
  "url": "https://example.com",
  "store_documents": true,
  "index_name": "my-docs"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "crawl_20250103_143052",
  "documents_stored": 1,
  "document_id": "doc_123",
  "url": "https://example.com",
  "title": "Example Domain"
}
```

#### 2. Batch Crawl
```http
POST /api/crawl/batch
Content-Type: application/json

{
  "urls": [
    "https://site1.com",
    "https://site2.com",
    "https://site3.com"
  ],
  "max_concurrent": 5,
  "store_documents": true,
  "index_name": "my-docs"  // Optional
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "batch_20250103_143052",
  "message": "Successfully crawled 3 URLs",
  "documents_stored": 3,
  "errors": [],
  "metadata": {
    "urls_processed": 3,
    "successful_crawls": 3,
    "failed_crawls": 0
  }
}
```

#### 3. Crawl Status
```http
GET /api/crawl/status/{session_id}
```

**Response:**
```json
{
  "session_id": "batch_20250103_143052",
  "status": "running",
  "progress_percent": 67.0,
  "current_item": 2,
  "total_items": 3,
  "started_at": "2025-01-03T14:30:52Z",
  "updated_at": "2025-01-03T14:31:15Z"
}
```

#### 4. Active Crawls
```http
GET /api/crawl/active
```

#### 5. Cancel Crawl
```http
POST /api/crawl/cancel/{session_id}
```

#### 6. Cleanup Old Tasks
```http
POST /api/crawl/cleanup?max_age_hours=24
```

---

### Search Endpoints

#### 1. Hybrid Search Query
```http
POST /api/search/query
Content-Type: application/json

{
  "query": "machine learning algorithms",
  "top_k": 10,
  "search_type": "hybrid",  // vector, keyword, or hybrid
  "vector_weight": 0.7,
  "keyword_weight": 0.3,
  "use_reranking": true,
  "rerank_strategy": "hybrid",  // bm25, hybrid, or quality
  "index_name": "ml-docs",  // Optional: search specific index
  "similarity_threshold": 0.1
}
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "document_id": "doc_123",
      "chunk_id": "chunk_456",
      "title": "Machine Learning Guide",
      "content": "Machine learning algorithms are...",
      "url": "https://example.com/ml-guide",
      "similarity_score": 0.89,
      "keyword_score": 0.76,
      "combined_score": 0.84,
      "metadata": {
        "source_type": "webpage",
        "crawl_timestamp": "2025-01-03T14:30:52Z"
      }
    }
  ],
  "total_results": 15,
  "query": "machine learning algorithms",
  "search_time_ms": 245.7,
  "search_strategy": "hybrid+hybrid_rerank"
}
```

#### 2. Simple Search (GET)
```http
GET /api/search/simple?q=machine+learning&limit=5&type=hybrid
```

#### 3. Search Within Document
```http
POST /api/search/document
Content-Type: application/json

{
  "document_id": "doc_123",
  "query": "specific topic",
  "max_chunks": 5
}
```

#### 4. List Documents
```http
GET /api/search/documents?limit=50&url_pattern=github.com&source_type=webpage
```

**Response:**
```json
{
  "success": true,
  "documents": [
    {
      "id": "doc_123",
      "title": "GitHub Documentation",
      "url": "https://github.com/docs",
      "source_type": "webpage",
      "chunk_count": 12,
      "created_at": "2025-01-03T14:30:52Z"
    }
  ],
  "total": 156
}
```

#### 5. Search Statistics
```http
GET /api/search/stats
```

---

### Index Management Endpoints

#### 1. Create Index
```http
POST /api/indexes
Content-Type: application/json

{
  "name": "python-docs",
  "display_name": "Python Documentation",
  "description": "Official Python documentation and tutorials"
}
```

#### 2. List Indexes
```http
GET /api/indexes?active_only=true&limit=100
```

**Response:**
```json
{
  "success": true,
  "indexes": [
    {
      "id": 1,
      "name": "python-docs",
      "display_name": "Python Documentation",
      "description": "Official Python documentation",
      "total_documents": 156,
      "total_chunks": 1847,
      "total_vectors": 1847,
      "index_size_mb": 89.4,
      "is_active": true,
      "created_at": "2025-01-03T14:30:52Z"
    }
  ],
  "total": 3
}
```

#### 3. Get Index Details
```http
GET /api/indexes/{index_name}
```

#### 4. Get Index Statistics
```http
GET /api/indexes/{index_name}/stats
```

#### 5. Delete Index
```http
DELETE /api/indexes/{index_name}?delete_documents=true
```

---

## Configuration

### Server Configuration

#### Development Mode
```bash
# Auto-reload on code changes
uvicorn webnexus.api.main:app --reload --host 127.0.0.1 --port 8000

# With debug logging
LOG_LEVEL=DEBUG uvicorn webnexus.api.main:app --reload
```

#### Production Mode
```bash
# Multiple workers for better performance
uvicorn webnexus.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info \
  --access-log

# With Gunicorn (recommended for production)
gunicorn webnexus.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### CORS Configuration

Edit `webnexus/config/settings.py`:

```python
cors_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://yourdomain.com"
]
```

Or set via environment:

```env
CORS_ORIGINS=["http://localhost:3000","https://yourdomain.com"]
```

---

## Usage Examples

### Python Client

```python
import httpx

# Base URL
BASE_URL = "http://localhost:8000"

# Health check
response = httpx.get(f"{BASE_URL}/health")
print(response.json())

# Crawl a website
response = httpx.post(
    f"{BASE_URL}/api/crawl/single",
    json={
        "url": "https://example.com",
        "store_documents": True,
        "index_name": "my-docs"
    }
)
print(response.json())

# Search documents
response = httpx.post(
    f"{BASE_URL}/api/search/query",
    json={
        "query": "machine learning",
        "top_k": 5,
        "search_type": "hybrid",
        "use_reranking": True
    }
)
results = response.json()
for result in results["results"]:
    print(f"Title: {result['title']}")
    print(f"Score: {result['combined_score']}")
    print(f"Content: {result['content'][:200]}...")
```

### cURL Examples

```bash
# Health check
curl http://localhost:8000/health

# Crawl single page
curl -X POST http://localhost:8000/api/crawl/single \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "store_documents": true
  }'

# Search with hybrid mode
curl -X POST http://localhost:8000/api/search/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "web crawling best practices",
    "top_k": 5,
    "search_type": "hybrid",
    "use_reranking": true
  }'

# List all indexes
curl http://localhost:8000/api/indexes

# Create new index
curl -X POST http://localhost:8000/api/indexes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "python-docs",
    "display_name": "Python Documentation",
    "description": "Python docs and tutorials"
  }'
```

### JavaScript/TypeScript

```typescript
// Using fetch API
async function searchDocuments(query: string) {
  const response = await fetch('http://localhost:8000/api/search/query', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query: query,
      top_k: 10,
      search_type: 'hybrid',
      use_reranking: true
    })
  });

  const data = await response.json();
  return data.results;
}

// Usage
const results = await searchDocuments('machine learning');
console.log(results);
```

---

## Authentication

Currently, the API does not require authentication. For production deployments, consider:

### Adding API Key Authentication

```python
# webnexus/api/main.py
from fastapi import Security, HTTPException
from fastapi.security.api_key import APIKeyHeader

API_KEY = os.getenv("API_KEY", "your-secret-key")
api_key_header = APIKeyHeader(name="X-API-Key")

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

# Apply to endpoints
@app.post("/api/crawl/single", dependencies=[Depends(get_api_key)])
async def crawl_single(request: CrawlRequest):
    # ...
```

### Using JWT Tokens

```python
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401)
        return username
    except JWTError:
        raise HTTPException(status_code=401)
```

---

## Error Handling

### Standard Error Response Format

```json
{
  "detail": "Error message describing what went wrong",
  "status_code": 400
}
```

### Common HTTP Status Codes

- **200 OK**: Request successful
- **400 Bad Request**: Invalid input parameters
- **404 Not Found**: Resource not found
- **422 Unprocessable Entity**: Validation error
- **500 Internal Server Error**: Server-side error

### Error Examples

```bash
# Invalid URL
curl -X POST http://localhost:8000/api/crawl/single \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-url"}'

# Response
{
  "detail": "Invalid URL format",
  "status_code": 400
}
```

---

## Monitoring

### Health Monitoring

```bash
# Check health every 30 seconds
watch -n 30 'curl -s http://localhost:8000/health | jq'

# Monitor with Prometheus (if configured)
curl http://localhost:8000/metrics
```

### Logging

Logs are written to stdout/stderr. Configure log level:

```bash
LOG_LEVEL=INFO uvicorn webnexus.api.main:app
# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
```

### Performance Monitoring

```bash
# Check system stats
curl http://localhost:8000/api/stats | jq

# Monitor active crawls
watch -n 5 'curl -s http://localhost:8000/api/crawl/active | jq'
```

---

## Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -i :8000

# Try different port
PORT=8001 uvicorn webnexus.api.main:app
```

### Database Errors

```bash
# Reinitialize database
rm -f data/webnexus.db
uv run python scripts/setup_db.py
```

### Model Download Issues

```bash
# Manually download embedding model
python -c "from webnexus.services.embedding_service import embedding_service; embedding_service._load_model()"
```

### Memory Issues

```bash
# Reduce concurrent crawls
MAX_CONCURRENT_CRAWLS=5 uvicorn webnexus.api.main:app

# Use CPU instead of GPU
EMBEDDING_DEVICE=cpu uvicorn webnexus.api.main:app
```

---

## Additional Resources

- **Main Documentation**: [../../README.md](../../README.md)
- **MCP Server**: [../mcp/README.md](../mcp/README.md)
- **Docker Deployment**: [../../DOCKER.md](../../DOCKER.md)
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **OpenAPI Specification**: http://localhost:8000/openapi.json (when running)

---

## Support

For issues and questions:
- GitHub Issues: https://github.com/WebNexus/WebNexus/issues
- Documentation: https://WebNexus.readthedocs.io
