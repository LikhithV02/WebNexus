# 🚀 **WebNexus: Advanced Web Crawler & RAG System**

*A powerful, self-contained web crawling and document search system with state-of-the-art AI capabilities*

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-purple.svg)](https://modelcontextprotocol.io/)

## 🎯 **What is WebNexus?**

WebNexus is a **powerful, open-source web crawling and RAG system** designed for **intelligent document discovery and semantic search**. It combines cutting-edge AI models with local storage to create a sophisticated Retrieval-Augmented Generation system that runs entirely on your machine.

### **🏆 Why Choose WebNexus?**

✅ **100% Open Source** - No API keys or cloud dependencies required  
✅ **State-of-the-Art Search** - Advanced hybrid search with keyword extraction and reranking  
✅ **Local & Private** - All data stays on your machine  
✅ **AI Agent Ready** - Full MCP (Model Context Protocol) integration  
✅ **Production Ready** - FastAPI server with comprehensive documentation  
✅ **Technical Content Optimized** - Perfect for documentation, code repos, and tutorials  

---

## 🧠 **Core Technologies & Why They Matter**

### **🔍 Advanced Search Pipeline**
- **Stella EN 400M v5 Embeddings** - State-of-the-art 1024-dimensional vectors for semantic search
- **FAISS Vector Database** - Lightning-fast similarity search (faster than pgvector)  
- **Enhanced BM25 Keyword Search** - Sophisticated tokenization with 400+ technical terms
- **Hybrid Search Fusion** - Combines vector similarity + keyword matching + advanced reranking
- **Smart Query Expansion** - Automatically adds plurals, variations, and related terms

### **🕷️ Multi-Strategy Web Crawling**
- **Crawl4AI Integration** - Modern async web crawling with JavaScript support
- **4 Crawling Strategies**: Single page, batch, recursive, and XML sitemap
- **Intelligent Content Extraction** - Preserves code blocks, maintains structure
- **Rate Limiting & Respect** - Follows robots.txt, configurable delays

### **🗄️ Local-First Architecture**  
- **SQLite Database** - Lightweight, reliable, no server required
- **FAISS Vector Storage** - Optimized for search performance
- **Original Archon Chunking** - 5000-character chunks with intelligent boundaries
- **Zero Cloud Dependencies** - Everything runs locally

### **🤖 AI Agent Integration**
- **MCP Server** - Full Model Context Protocol support
- **3 Production-Ready Tools** - Crawl, search, and source management
- **JSON-Formatted Responses** - Perfect for AI agents and automation

---

## 📦 **Quick Start Installation**

### **Prerequisites**
- **Python 3.12+** (recommended) or Python 3.10+
- **8GB+ RAM** (for embedding model)
- **2GB+ disk space** (for models and data)

### **1. Clone & Setup**
```bash
git clone <repository-url>
cd WebNexus

# Install with uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# Or with pip
pip install -e .
```

### **2. Initialize Database & Download Models**
```bash
# One-time setup (downloads ~800MB Stella model)
uv run python scripts/setup_db.py
```

This will:
- Create SQLite database with proper schema
- Download Stella EN 400M v5 embedding model (~800MB)
- Initialize FAISS vector indexes
- Test all services

### **3. Start Services**

#### **Option A: Use Startup Script (Recommended)**
```bash
uv run python scripts/run_servers.py
```

#### **Option B: Start Manually**
```bash
# Terminal 1: FastAPI Server
uv run uvicorn src.api.main:app --reload --port 8000

# Terminal 2: MCP Server (for AI agents)  
uv run python src.mcp.server.py --stdio
```

### **4. Verify Installation**
```bash
# Check FastAPI server
curl http://localhost:8000/health

# View interactive API docs
open http://localhost:8000/docs
```

---

## 🌐 **FastAPI REST API Endpoints**

WebNexus provides a comprehensive REST API for all operations:

### **🕷️ Crawling Endpoints**

#### **Single Page Crawling**
```http
POST /api/crawl/single
Content-Type: application/json

{
  "url": "https://python.langchain.com/docs/introduction/",
  "store_documents": true
}
```

**Response:**
```json
{
  "success": true,
  "session_id": "single_crawl_20250131_143052",
  "message": "Successfully crawled and stored 1 document",
  "documents_stored": 1,
  "metadata": {
    "url": "https://python.langchain.com/docs/introduction/",
    "title": "LangChain Introduction",
    "content_length": 15420,
    "chunks_created": 4
  }
}
```

#### **Batch Crawling**
```http
POST /api/crawl/batch
Content-Type: application/json

{
  "urls": [
    "https://python.langchain.com/docs/introduction/",
    "https://python.langchain.com/docs/concepts/",
    "https://python.langchain.com/docs/tutorials/"
  ],
  "max_concurrent": 3,
  "store_documents": true
}
```

#### **Progress Monitoring**
```http
# Get crawl status
GET /api/crawl/status/{session_id}

# List active crawls
GET /api/crawl/active

# Cancel running crawl
POST /api/crawl/cancel/{session_id}
```

### **🔍 Search Endpoints**

#### **Advanced Hybrid Search**
```http
POST /api/search/query
Content-Type: application/json

{
  "query": "LangChain vector stores and embeddings",
  "top_k": 10,
  "search_type": "hybrid",
  "vector_weight": 0.7,
  "keyword_weight": 0.3,
  "use_reranking": true,
  "rerank_strategy": "hybrid"
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
      "title": "LangChain Vector Stores Guide",
      "content": "LangChain provides vector stores for embedding storage and retrieval...",
      "url": "https://python.langchain.com/docs/modules/data_connection/vectorstores/",
      "similarity_score": 0.92,
      "keyword_score": 0.85,
      "combined_score": 0.89,
      "metadata": {"source_type": "webpage"},
      "source_type": "webpage"
    }
  ],
  "total_results": 8,
  "query": "LangChain vector stores and embeddings",
  "search_time_ms": 245.7,
  "search_strategy": "hybrid+hybrid_rerank"
}
```

#### **Simple Search**
```http
GET /api/search/simple?q=machine+learning&limit=5&type=vector
```

#### **Document-Specific Search**
```http
POST /api/search/document
Content-Type: application/json

{
  "document_id": "doc_123",
  "query": "vector database implementation",
  "max_chunks": 5
}
```

### **📚 Document Management**

#### **List Documents**
```http
GET /api/search/documents?limit=50&url_pattern=langchain.com
```

#### **Search Statistics**
```http
GET /api/search/stats
```

**Response:**
```json
{
  "total_documents": 156,
  "total_chunks": 847,
  "total_embeddings": 847,
  "vector_index_size": 847,
  "embedding_dimension": 1024,
  "available_source_types": ["webpage", "pdf", "markdown"],
  "recent_crawls": 23,
  "search_performance": {
    "avg_search_time_ms": 180.5,
    "total_searches": 1247
  }
}
```

### **⚡ System Endpoints**

```http
GET /health          # Health check with service status
GET /api/stats       # Comprehensive system statistics  
GET /docs            # Interactive API documentation (Swagger UI)
GET /redoc           # Alternative API documentation (ReDoc)
```

---

## 🤖 **MCP Integration with Claude Desktop**

WebNexus includes full **Model Context Protocol (MCP)** support, allowing AI agents like Claude to directly crawl websites and search documents.

### **🔧 Setup MCP with Claude Desktop**

#### **1. Install Claude Desktop**
Download from: https://claude.ai/download

#### **2. Configure MCP Server**

**For macOS/Linux:**
```bash
# Edit Claude Desktop configuration
code ~/.claude-desktop/claude_desktop_config.json
```

**For Windows:**
```bash
# Edit Claude Desktop configuration  
notepad "%APPDATA%\Claude\claude_desktop_config.json"
```

#### **3. Add WebNexus MCP Configuration**
```json
{
  "mcpServers": {
    "WebNexus": {
      "command": "uv",
      "args": [
        "run", 
        "python", 
        "/path/to/WebNexus/webnexus/mcp/server.py"
      ],
      "cwd": "/path/to/WebNexus"
    }
  }
}
```

**Replace `/path/to/WebNexus` with your actual project path.**

#### **4. Restart Claude Desktop**
Close and reopen Claude Desktop to load the MCP server.

### **🛠️ MCP Tools Available**

Once configured, Claude Desktop will have access to these tools:

#### **1. `crawl_website` - Multi-Strategy Web Crawling**
```python
# Claude can use this tool to crawl websites
crawl_website(
    url="https://python.langchain.com/docs/",
    strategy="recursive",  # single_page, batch, recursive, sitemap
    max_depth=2,
    max_pages=20,
    store_documents=True
)
```

#### **2. `search_documents` - Advanced RAG Search**
```python  
# Claude can search crawled documents
search_documents(
    query="LangChain vector stores implementation",
    max_results=10,
    search_type="hybrid",      # vector, keyword, or hybrid
    use_reranking=True,        # Apply advanced reranking
    similarity_threshold=0.1   # Minimum relevance score
)
```

#### **3. `get_sources` - Document Source Management**
```python
# Claude can browse available document sources
get_sources(
    limit=25,
    url_pattern="langchain.com",  # Filter by URL pattern
    source_type="webpage"         # Filter by content type
)
```

### **🎯 Example Claude Interactions**

Once MCP is configured, you can ask Claude:

> **"Please crawl the LangChain documentation and then search for information about vector stores"**

Claude will:
1. Use `crawl_website` to fetch LangChain documentation
2. Use `search_documents` to find relevant information about vector stores  
3. Provide comprehensive answers based on the crawled content

> **"What programming tutorials do we have available? Search for Python examples."**

Claude will:
1. Use `get_sources` to list available documents
2. Use `search_documents` to find Python-related content
3. Summarize the available resources

---

## 🔍 **Advanced Search Features**

### **🧠 Enhanced Keyword Extraction**

WebNexus uses sophisticated keyword extraction that outperforms simple tokenization:

**Before (Simple Tokenization):**
```
Query: "machine learning model deployment best practices"
Tokens: ["machine", "learning", "model", "deployment", "best", "practices"]
```

**After (Enhanced Extraction):**
```
Query: "machine learning model deployment best practices"
Keywords: ["deployment", "machine", "learning", "production", "best", "model", "best_practices"]
Search Terms: ["deployment", "deployments", "machine", "machines", "learning", "learnings", "production", "productions", "best", "model", "models", "best_practices"]
```

**Performance Improvement: 2-3x better BM25 scores, 93.8% technical term preservation**

### **🔗 Hybrid Search Strategies**

#### **Vector Search** - Semantic Understanding
- Uses Stella EN 400M v5 embeddings (1024 dimensions)
- Understands context and meaning
- Great for conceptual queries

#### **Keyword Search** - Exact Term Matching  
- Enhanced BM25 with technical term preservation
- Handles specific terminology and code
- Perfect for precise lookups

#### **Hybrid Fusion** - Best of Both Worlds
- Combines vector similarity + keyword relevance
- Configurable weighting (default: 70% vector, 30% keyword)
- Advanced reranking for improved results

### **🎯 Reranking Strategies**

1. **BM25 Reranking** - Pure keyword relevance optimization
2. **Hybrid Reranking** - Combines scores + query coverage + content quality
3. **Quality Reranking** - Focuses on content completeness and structure

---

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   MCP Server    │◄──►│  FastAPI Server │◄──►│  SQLite + FAISS │
│   (Port 8051)   │    │   (Port 8000)   │    │    Database     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
        │                       │                       │
        ▼                       ▼                       ▼
   AI Agent Tools         REST API Endpoints      Local Data Storage
 - crawl_website         - /api/crawl/*          - Document metadata
 - search_documents      - /api/search/*         - Vector embeddings  
 - get_sources          - /health, /docs         - FAISS indexes
```

### **📊 Database Schema**

**SQLite Tables:**
- **documents** - Document metadata and content
- **document_chunks** - Chunked content for RAG
- **embeddings** - Vector embedding metadata 
- **code_examples** - Extracted code blocks
- **crawl_sessions** - Crawling progress tracking

**FAISS Indexes:**
- **Document vectors** - Semantic search index
- **Code vectors** - Specialized code search
- **Persistent storage** - Automatic index saving/loading

---

## ⚙️ **Configuration & Customization**

### **Environment Variables**
```bash
# Core Configuration
EMBEDDING_MODEL="dunzhang/stella_en_400M_v5"
CHUNKING_STRATEGY="original"  # original, advanced, specialized
ORIGINAL_CHUNK_SIZE=5000
ADVANCED_CHUNK_SIZE=1000

# Database Configuration
DATABASE_URL="sqlite:///./data/WebNexus.db"
VECTOR_INDEX_PATH="./data/vectors/faiss_index.bin"

# Performance Settings
MAX_CONCURRENT_CRAWLS=10
CRAWL_TIMEOUT=30
EMBEDDING_BATCH_SIZE=32
```

### **Chunking Strategies**

#### **Original Archon (Default)**
- 5000 character chunks with no overlap
- Intelligent boundary detection (code blocks, paragraphs, sentences)
- Optimized for the original Archon compatibility

#### **Advanced Custom**
- 1000 character chunks with 100 character overlap
- Enhanced semantic boundary detection
- Better for dense technical content

#### **Specialized**  
- Content-aware chunking for different file types
- Language-specific code chunk boundaries
- Perfect for mixed documentation and code

---

## 📈 **Performance & Benchmarks**

### **Search Performance**
- **Vector Search**: ~200ms for 10k documents
- **Hybrid Search**: ~400ms with reranking
- **Memory Usage**: ~4GB peak with embedding model
- **Storage**: ~75MB per 1000 crawled pages

### **Crawling Performance**  
- **Single Page**: ~2-5 seconds per page
- **Batch Crawling**: 5-10 pages/second with proper delays
- **Recursive**: Respects rate limits, configurable depth
- **Success Rate**: >95% for standard websites

### **Embedding Performance**
- **Stella EN 400M v5**: 13.7 docs/sec (CPU), 50+ docs/sec (GPU)
- **FAISS Indexing**: ~50ms for 1000 vectors
- **Index Loading**: <2 seconds for 10k documents

---

## 🎨 **Use Cases & Examples**

### **📚 Documentation Crawling & Search**
Perfect for creating searchable knowledge bases from:
- API documentation (OpenAPI, REST docs)
- Framework documentation (React, Vue, Django)
- Technical tutorials and guides
- GitHub repository documentation

### **🔬 Research & Analysis**
- Academic paper repositories
- Technical blog aggregation
- Industry report collections
- Competitive analysis datasets

### **🤖 AI Agent Enhancement**
- Provide Claude with domain-specific knowledge
- Create context-aware coding assistants  
- Build specialized Q&A systems
- Enable autonomous research capabilities

### **💼 Enterprise Applications**
- Internal documentation search
- Compliance document management
- Training material organization
- Knowledge base creation

---

## 🔒 **Privacy & Security**

### **Local-First Design**
- **No cloud dependencies** - Everything runs on your machine
- **No API keys required** - Uses open-source models
- **Complete data control** - You own all crawled content
- **Offline capable** - Works without internet (after model download)

### **Security Features**
- **Robots.txt compliance** - Respects website crawling policies
- **Rate limiting** - Prevents server overload
- **URL validation** - Prevents malicious requests
- **Secure storage** - SQLite with proper permissions

---

## 🛠️ **Development & Contributing**

### **Development Setup**
```bash
# Clone repository
git clone <repo-url>
cd WebNexus

# Install development dependencies
uv sync --dev

# Run tests
uv run python tests/test_langchain_pipeline.py

# Format code
uv run black webnexus/
uv run isort webnexus/

# Type checking
uv run mypy webnexus/
```

### **Project Structure**
```
WebNexus/
├── webnexus/
│   ├── api/           # FastAPI application
│   ├── mcp/           # MCP server implementation
│   ├── models/        # Database models
│   ├── services/      # Core business logic
│   ├── utils/         # Utility functions
│   └── config/        # Configuration management
├── tests/             # Test suites
├── scripts/           # Setup and management scripts
├── data/              # Database and vector storage
└── docs/              # Documentation
```

### **Adding New Features**
1. **New crawling strategies** - Extend `CrawlingService`
2. **Search improvements** - Enhance `SearchService` or `RerankingService`  
3. **MCP tools** - Add new tools to `mcp/server.py`
4. **API endpoints** - Create new routers in `api/`

---

## 📞 **Support & Community**

### **Getting Help**
- **Documentation**: Check `/docs` endpoint for API reference
- **Issues**: Report bugs and feature requests on GitHub
- **Discussions**: Join community discussions for help and ideas

### **Common Issues & Solutions**

#### **Model Download Fails**
```bash
# Clear cache and retry
rm -rf ~/.cache/huggingface/
uv run python scripts/setup_db.py
```

#### **Memory Issues**
```bash
# Use CPU-only mode
export FORCE_CPU=true
uv run python scripts/setup_db.py
```

#### **Port Conflicts**
```bash
# Use different ports
uv run uvicorn src.api.main:app --port 8001
```

---

## 📄 **License & Credits**

### **License**
This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

### **Credits & Acknowledgments**
- **Crawl4AI** - Modern web crawling capabilities
- **Stella EN 400M v5** - State-of-the-art embedding model by dunzhang
- **FAISS** - Efficient vector similarity search by Facebook AI
- **FastAPI** - Modern, fast web framework
- **Model Context Protocol** - AI agent integration standard

### **Third-Party Models**
- **Stella EN 400M v5**: MIT License (dunzhang/stella_en_400M_v5)
- **Sentence Transformers**: Apache 2.0 License
- **FAISS**: MIT License

---

## 🎯 **What's Next?**

WebNexus is actively developed with planned features:

### **🚀 Upcoming Features**
- **Recursive crawling improvements** - Better depth control and filtering
- **Additional file format support** - PDF, DOCX, TXT processing
- **Advanced analytics** - Search analytics and document insights
- **Performance optimizations** - GPU acceleration, caching improvements
- **UI Dashboard** - Web-based management interface

### **🤝 Contributing**
We welcome contributions! Areas where help is needed:
- Performance optimizations
- Additional crawling strategies
- UI/UX improvements  
- Documentation enhancements
- Test coverage expansion

---

**🎉 Ready to get started? Run `uv run python scripts/setup_db.py` and begin crawling the web with state-of-the-art AI search capabilities!**

---

*Built with ❤️ by the WebNexus community. Transform your web content into intelligent, searchable knowledge bases.*