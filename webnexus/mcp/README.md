# 🤖 WebNexus MCP Server

Model Context Protocol (MCP) server providing web crawling and RAG tools for AI agents and coding assistants.

## 📋 Table of Contents

- [What is MCP?](#what-is-mcp)
- [Quick Start](#quick-start)
- [Server Setup](#server-setup)
- [Available Tools](#available-tools)
- [Configuration](#configuration)
- [Integration Guides](#integration-guides)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)

---

## What is MCP?

**Model Context Protocol (MCP)** is an open protocol that enables AI assistants to interact with external tools and data sources. The WebNexus MCP server provides:

- **Web Crawling**: Multi-strategy crawling (single page, batch, recursive, sitemap)
- **Document Search**: Hybrid vector + keyword search with reranking
- **Index Management**: Create and manage topic-specific vector indexes
- **Source Management**: Track and filter crawled documents

### Why Use MCP?

✅ **AI-Native**: Designed specifically for AI agent integration
✅ **Standardized**: Works with any MCP-compatible client
✅ **Stateless**: Each tool call is independent
✅ **JSON-First**: All responses in structured JSON format
✅ **Error Handling**: Graceful error handling with detailed messages

---

## Quick Start

### 1. Start the MCP Server

```bash
# Using uv (recommended)
uv run python webnexus/mcp/server.py --stdio

# Using Python directly
python -m webnexus.mcp.server --stdio

# Test the server
uv run python scripts/test_mcp.py
```

### 2. Connect to Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "webnexus": {
      "command": "/Users/YOUR_USERNAME/Projects/WebNexus/.venv/bin/python",
      "args": [
        "/Users/YOUR_USERNAME/Projects/WebNexus/webnexus/mcp/server.py",
        "--stdio"
      ],
      "cwd": "/Users/YOUR_USERNAME/Projects/WebNexus"
    }
  }
}
```

**Important:** Replace `YOUR_USERNAME` with your actual username, or use full paths.

### 3. Verify Connection

Restart Claude Desktop, then try:
```
List all available vector indexes
```

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

Create a `.env` file:

```env
# Database
DATABASE_URL=sqlite:///./data/webnexus.db

# Embedding Model
EMBEDDING_MODEL=dunzhang/stella_en_400M_v5
EMBEDDING_DEVICE=auto  # auto, cpu, or cuda

# Crawling
MAX_CONCURRENT_CRAWLS=10
MAX_CRAWL_DEPTH=3
CRAWL_TIMEOUT=30

# Search
DEFAULT_SEARCH_LIMIT=5
USE_HYBRID_SEARCH=true
USE_RERANKING=true

# Logging (for MCP server)
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
TRANSFORMERS_VERBOSITY=error
HF_HUB_DISABLE_PROGRESS_BARS=1
```

### Directory Structure

```
webnexus/mcp/
├── README.md          # This file
├── __init__.py
└── server.py         # MCP server implementation (FastMCP)
```

---

## Available Tools

The MCP server provides **6 production-ready tools**:

### 1. 🕷️ `crawl_website`

Crawl websites and store documents for later search.

**Parameters:**
- `url` (string, required): URL to crawl
- `strategy` (string, optional): Crawling strategy
  - `"single_page"`: Crawl only the specified URL (default)
  - `"batch"`: Crawl multiple URLs
  - `"recursive"`: Follow links recursively
  - `"sitemap"`: Crawl from XML sitemap
- `max_depth` (integer, optional): Maximum depth for recursive crawling (default: 2)
- `max_pages` (integer, optional): Maximum pages to crawl (default: 50)
- `store_documents` (boolean, optional): Save documents to database (default: true)
- `index_name` (string, optional): Target vector index (default: "default")

**Example:**
```
Crawl https://docs.python.org/3/ recursively with max depth 2 and store in python-docs index
```

**Response:**
```json
{
  "success": true,
  "session_id": "mcp_crawl_20250103_140532",
  "strategy": "recursive",
  "documents_stored": 23,
  "pages_crawled": 23,
  "message": "Successfully crawled and stored 23 documents. You can now search them using search_documents."
}
```

---

### 2. 🔍 `search_documents`

Search crawled documents using vector similarity, keyword matching, or hybrid search.

**Parameters:**
- `query` (string, required): Search query
- `max_results` (integer, optional): Maximum results to return (default: 10)
- `search_type` (string, optional): Search method
  - `"vector"`: Semantic similarity search
  - `"keyword"`: BM25 keyword search
  - `"hybrid"`: Combined vector + keyword (default)
- `use_reranking` (boolean, optional): Apply advanced reranking (default: true)
- `similarity_threshold` (float, optional): Minimum similarity score (default: 0.1)
- `index_name` (string, optional): Search specific index, or null for all indexes

**Example:**
```
Search for "async programming best practices" using hybrid search with reranking in python-docs index
```

**Response:**
```json
{
  "success": true,
  "results": [
    {
      "title": "Async Programming Guide",
      "content": "Python asyncio provides...",
      "url": "https://docs.python.org/asyncio",
      "similarity_score": 0.94,
      "keyword_score": 0.87,
      "combined_score": 0.91,
      "document_id": "doc_123",
      "chunk_id": "chunk_456"
    }
  ],
  "total_results": 8,
  "search_type": "hybrid+hybrid_rerank",
  "message": "Found 8 relevant documents using hybrid+hybrid_rerank search."
}
```

---

### 3. 📚 `get_sources`

Get information about crawled documents and filter by URL pattern or source type.

**Parameters:**
- `limit` (integer, optional): Maximum documents to return (default: 25)
- `url_pattern` (string, optional): Filter by URL substring (e.g., "github.com")
- `source_type` (string, optional): Filter by source type (e.g., "webpage")
- `index_name` (string, optional): Filter by vector index

**Example:**
```
Get all sources from github.com in the python-docs index
```

**Response:**
```json
{
  "success": true,
  "sources": [
    {
      "document_id": "doc_123",
      "title": "GitHub Documentation",
      "url": "https://github.com/docs",
      "source_type": "webpage",
      "chunk_count": 12,
      "content_length": 8450,
      "created_at": "2025-01-03T14:05:32Z",
      "vector_index": "python-docs"
    }
  ],
  "total_sources": 156,
  "statistics": {
    "total_documents": 156,
    "available_source_types": ["webpage", "pdf", "markdown"]
  },
  "message": "Found 156 document sources."
}
```

---

### 4. 📋 `list_indexes`

List all available vector indexes with metadata.

**Parameters:** None

**Example:**
```
List all vector indexes
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
      "description": "Official Python documentation and tutorials",
      "total_documents": 156,
      "total_chunks": 1847,
      "total_vectors": 1847,
      "index_size_mb": 89.4,
      "is_active": true,
      "created_at": "2025-01-03T14:30:52Z"
    },
    {
      "id": 2,
      "name": "react-docs",
      "display_name": "React Documentation",
      "description": "React library documentation",
      "total_documents": 89,
      "total_chunks": 1024,
      "total_vectors": 1024,
      "index_size_mb": 45.2,
      "is_active": true,
      "created_at": "2025-01-03T15:20:10Z"
    }
  ],
  "total_indexes": 2,
  "message": "Found 2 active vector indexes."
}
```

---

### 5. ➕ `create_index`

Create a new topic-specific vector index.

**Parameters:**
- `name` (string, required): Unique index identifier (lowercase, alphanumeric, hyphens, underscores)
- `display_name` (string, optional): Human-readable name (defaults to name)
- `description` (string, optional): Index description

**Example:**
```
Create a new index called "ml-papers" for machine learning research papers
```

**Response:**
```json
{
  "success": true,
  "index": {
    "id": 3,
    "name": "ml-papers",
    "display_name": "ml-papers",
    "description": "Machine learning research papers",
    "total_documents": 0,
    "is_active": true,
    "created_at": "2025-01-03T16:45:00Z"
  },
  "message": "Successfully created index 'ml-papers'. You can now crawl documents into this index."
}
```

---

### 6. 🗑️ `delete_index`

Delete a vector index and optionally its documents.

**Parameters:**
- `name` (string, required): Index name to delete
- `delete_documents` (boolean, optional): Also delete all documents in index (default: false)

**Example:**
```
Delete the ml-papers index and all its documents
```

**Response:**
```json
{
  "success": true,
  "index_name": "ml-papers",
  "documents_deleted": 45,
  "message": "Successfully deleted index 'ml-papers' and 45 documents."
}
```

---

## Configuration

### Server Configuration

The MCP server uses `FastMCP` for implementation and runs in stdio mode for integration with AI assistants.

#### Logging Configuration

Control logging verbosity:

```bash
# Minimal logging (recommended for AI assistants)
LOG_LEVEL=WARNING python -m webnexus.mcp.server --stdio

# Debug logging (for troubleshooting)
LOG_LEVEL=DEBUG python -m webnexus.mcp.server --stdio

# No logging (cleanest output)
LOG_LEVEL=CRITICAL python -m webnexus.mcp.server --stdio
```

#### Performance Tuning

```env
# Reduce memory usage
EMBEDDING_BATCH_SIZE=50
MAX_CONCURRENT_CRAWLS=5

# Use CPU instead of GPU
EMBEDDING_DEVICE=cpu

# Disable model progress bars
HF_HUB_DISABLE_PROGRESS_BARS=1
TRANSFORMERS_VERBOSITY=error
```

---

## Integration Guides

### Claude Desktop

**macOS Configuration:**

1. Open configuration file:
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

2. Add WebNexus server:
```json
{
  "mcpServers": {
    "webnexus": {
      "command": "/full/path/to/.venv/bin/python",
      "args": [
        "/full/path/to/webnexus/mcp/server.py",
        "--stdio"
      ],
      "cwd": "/full/path/to/WebNexus"
    }
  }
}
```

3. Restart Claude Desktop

4. Test connection:
```
List all available vector indexes
```

**Windows Configuration:**

Configuration file location:
```
%APPDATA%\Claude\claude_desktop_config.json
```

```json
{
  "mcpServers": {
    "webnexus": {
      "command": "C:\\path\\to\\WebNexus\\.venv\\Scripts\\python.exe",
      "args": [
        "C:\\path\\to\\WebNexus\\webnexus\\mcp\\server.py",
        "--stdio"
      ],
      "cwd": "C:\\path\\to\\WebNexus"
    }
  }
}
```

---

### Claude Code

**Claude Code Configuration:**

Claude Code is Anthropic's official CLI tool with built-in MCP support.

#### Quick Setup with CLI (Recommended)

```bash
# Add WebNexus MCP server using Claude Code CLI
claude mcp add --transport stdio webnexus \
  --env TRANSFORMERS_VERBOSITY=error \
  --env HF_HUB_DISABLE_PROGRESS_BARS=1 \
  -- uv run python /Users/likhithv/Projects/WebNexus/webnexus/mcp/server.py --stdio
```

**Important:** Replace `/Users/likhithv/Projects/WebNexus` with your actual project path.

#### Manual Configuration

**1. Configuration File Location:**

- **macOS/Linux**: `~/.claude-code/settings.json`
- **Windows**: `%APPDATA%\claude-code\settings.json`

**2. Add WebNexus MCP Server:**

Option A - Via UI:
```
1. Open Claude Code settings (Cmd+, on macOS or Ctrl+, on Windows/Linux)
2. Search for "MCP" in settings
3. Click "Edit in settings.json" next to "MCP Servers"
4. Add the WebNexus configuration (see below)
```

Option B - Direct File Edit:
```bash
# macOS/Linux
code ~/.claude-code/settings.json

# Windows
notepad %APPDATA%\claude-code\settings.json
```

**3. Configuration:**

```json
{
  "mcp.servers": {
    "webnexus": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "/Users/likhithv/Projects/WebNexus/webnexus/mcp/server.py",
        "--stdio"
      ],
      "cwd": "/Users/likhithv/Projects/WebNexus",
      "env": {
        "TRANSFORMERS_VERBOSITY": "error",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1"
      }
    }
  }
}
```

**Important:** Replace `/Users/likhithv/Projects/WebNexus` with your actual project path.

**Alternative configuration using full Python path:**
```json
{
  "mcp.servers": {
    "webnexus": {
      "command": "/full/path/to/WebNexus/.venv/bin/python",
      "args": [
        "/full/path/to/WebNexus/webnexus/mcp/server.py",
        "--stdio"
      ],
      "cwd": "/full/path/to/WebNexus",
      "env": {
        "TRANSFORMERS_VERBOSITY": "error",
        "HF_HUB_DISABLE_PROGRESS_BARS": "1"
      }
    }
  }
}
```

#### Verify Installation

**1. Check MCP server status:**

In Claude Code, use the command:
```
/mcp
```

You should see the WebNexus server listed with all available tools:
- `crawl_website` - Multi-strategy web crawling
- `search_documents` - Hybrid RAG search
- `get_sources` - Document management
- `list_indexes` - Show all vector indexes
- `create_index` - Create new topic index
- `delete_index` - Remove vector index

**2. Test the integration:**

Try asking Claude Code:
```
Crawl https://example.com and store it in the default index
```

Or:
```
List all available vector indexes
```

Or:
```
Search for "machine learning" in all documents
```

#### Managing the Server

```bash
# List all configured MCP servers
claude mcp list

# Get WebNexus server details
claude mcp get webnexus

# Remove the server
claude mcp remove webnexus
```

#### Troubleshooting

**Server not appearing:**
- Ensure you've restarted Claude Code after configuration
- Verify the paths are absolute and correct
- Check that `uv` is in your PATH: `which uv`

**Connection issues:**
- Verify database is initialized: `ls -la data/webnexus.db`
- Run setup if needed: `uv run python scripts/setup_db.py`
- Check server logs for errors

**Environment variables:**
- The `TRANSFORMERS_VERBOSITY` and `HF_HUB_DISABLE_PROGRESS_BARS` settings prevent stdout pollution that can cause JSON parsing errors in MCP clients

---

### Cline / Continue / Other MCP Clients

Most MCP clients follow similar configuration patterns. General format:

```json
{
  "mcpServers": {
    "webnexus": {
      "command": "/path/to/python",
      "args": ["/path/to/webnexus/mcp/server.py", "--stdio"],
      "cwd": "/path/to/WebNexus"
    }
  }
}
```

Refer to your MCP client's documentation for specific configuration file locations.

---

## Usage Examples

### Example Conversations with AI Assistants

#### Crawling and Searching Documentation

**You:**
```
Crawl the Python asyncio documentation at https://docs.python.org/3/library/asyncio.html recursively and store it in the python-docs index
```

**AI Assistant:**
```
I'll crawl the Python asyncio documentation for you.

[Uses crawl_website tool]

Successfully crawled 23 pages from the Python asyncio documentation and stored them in the python-docs index. You can now search this content.
```

**You:**
```
Search for "event loop best practices" in the python-docs index
```

**AI Assistant:**
```
[Uses search_documents tool]

Here are the most relevant results:

1. **Event Loop** (score: 0.91)
   - URL: https://docs.python.org/3/library/asyncio-eventloop.html
   - Summary: The event loop is the core of every asyncio application...

2. **asyncio Best Practices** (score: 0.87)
   - URL: https://docs.python.org/3/library/asyncio-dev.html
   - Summary: This section provides best practices for asyncio development...

[Shows detailed excerpts from search results]
```

---

#### Managing Multiple Knowledge Bases

**You:**
```
Create three new indexes: python-docs, react-docs, and ml-papers
```

**AI Assistant:**
```
[Uses create_index tool 3 times]

Created 3 new indexes:
1. python-docs - Ready for Python documentation
2. react-docs - Ready for React documentation
3. ml-papers - Ready for machine learning research papers

You can now crawl content into these indexes separately.
```

**You:**
```
Show me all my indexes
```

**AI Assistant:**
```
[Uses list_indexes tool]

You have 4 active indexes:

1. **default** (156 documents, 89.4 MB)
   - General purpose index

2. **python-docs** (0 documents, 0 MB)
   - Python Documentation

3. **react-docs** (0 documents, 0 MB)
   - React Documentation

4. **ml-papers** (0 documents, 0 MB)
   - Machine learning research papers
```

---

#### Batch Crawling Multiple Sites

**You:**
```
Crawl these three React tutorial sites and store them in the react-docs index:
- https://react.dev/learn
- https://react.dev/reference
- https://react.dev/blog
```

**AI Assistant:**
```
[Uses crawl_website tool with batch strategy]

Successfully crawled all three React sites:
- react.dev/learn: 45 pages
- react.dev/reference: 89 pages
- react.dev/blog: 23 pages

Total: 157 documents stored in the react-docs index. Ready for searching!
```

---

### Programmatic Access (Python)

```python
import subprocess
import json

def call_mcp_tool(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool via subprocess."""
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    process = subprocess.Popen(
        ["python", "-m", "webnexus.mcp.server", "--stdio"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    stdout, stderr = process.communicate(json.dumps(request).encode())
    return json.loads(stdout)

# Example: List indexes
result = call_mcp_tool("list_indexes", {})
print(result)

# Example: Search documents
result = call_mcp_tool("search_documents", {
    "query": "machine learning",
    "search_type": "hybrid",
    "max_results": 5
})
print(result)
```

---

## Troubleshooting

### MCP Server Won't Start

**Issue:** Server fails to initialize

**Solutions:**

```bash
# Check if database is initialized
ls -la data/webnexus.db

# If missing, initialize:
uv run python scripts/setup_db.py

# Check for import errors
python -c "import webnexus; print('OK')"

# Run test script
uv run python scripts/test_mcp.py
```

---

### JSON Parse Errors in Claude Desktop

**Issue:** Claude Desktop shows JSON parsing errors

**Cause:** Stdout pollution from libraries (crawl4ai, transformers)

**Solution:** The server automatically suppresses stdout. Ensure you're using the latest version:

```bash
# Check server.py has suppress_stdout context manager
grep "suppress_stdout" webnexus/mcp/server.py

# Verify environment variables are set
grep "TRANSFORMERS_VERBOSITY" webnexus/mcp/server.py
```

---

### Tools Not Appearing in Claude Desktop

**Issue:** MCP tools don't show up in Claude Desktop

**Solutions:**

1. **Check configuration path:**
```bash
# Verify file exists and is valid JSON
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | jq
```

2. **Use absolute paths:**
```json
{
  "mcpServers": {
    "webnexus": {
      "command": "/Users/yourusername/Projects/WebNexus/.venv/bin/python",
      "args": [
        "/Users/yourusername/Projects/WebNexus/webnexus/mcp/server.py",
        "--stdio"
      ],
      "cwd": "/Users/yourusername/Projects/WebNexus"
    }
  }
}
```

3. **Check logs:**
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Look for error messages
```

4. **Restart Claude Desktop completely** (Quit, not just close window)

---

### Crawling Fails

**Issue:** Crawl operations timeout or fail

**Solutions:**

```bash
# Increase timeout
CRAWL_TIMEOUT=60 python -m webnexus.mcp.server --stdio

# Reduce concurrent crawls
MAX_CONCURRENT_CRAWLS=3 python -m webnexus.mcp.server --stdio

# Check network connectivity
curl -I https://example.com
```

---

### Memory Issues

**Issue:** Server uses too much memory

**Solutions:**

```bash
# Use CPU instead of GPU
EMBEDDING_DEVICE=cpu python -m webnexus.mcp.server --stdio

# Reduce batch size
EMBEDDING_BATCH_SIZE=50 python -m webnexus.mcp.server --stdio

# Reduce concurrent operations
MAX_CONCURRENT_CRAWLS=3 python -m webnexus.mcp.server --stdio
```

---

### Import Errors

**Issue:** `ModuleNotFoundError: No module named 'webnexus'`

**Solutions:**

```bash
# Ensure package is installed
uv sync

# Check Python path
which python
/path/to/WebNexus/.venv/bin/python --version

# Verify in config file
# Use full path to venv Python, not system Python
```

---

## Testing

### Automated Testing

```bash
# Run comprehensive MCP test suite
uv run python scripts/test_mcp.py
```

**Expected Output:**
```
🚀 WebNexus MCP Server Testing
========================================
🔄 Testing server initialization...
✅ Server initialization successful

🔄 Testing tool registration...
✅ 6 tools registered

🔄 Testing crawl_website tool...
✅ crawl_website tool working

🔄 Testing search_documents tool...
✅ search_documents tool working - 3 search types tested

🔄 Testing get_sources tool...
✅ get_sources tool working - 3 parameter sets tested

🎯 Overall Status:
   Working Tools: 3/3
   Server Functional: Yes
   MCP Server Ready: ✅ Yes
```

### Manual Testing

```bash
# Start server in test mode
python -m webnexus.mcp.server --stdio

# Send test request (in separate terminal)
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | \
  python -m webnexus.mcp.server --stdio
```

---

## Performance

### Benchmarks

Typical performance on modern hardware:

- **Server Startup**: 8-12 seconds (model loading)
- **Tool Registration**: < 1 second
- **Crawl (single page)**: 2-5 seconds
- **Search (hybrid)**: 200-400ms for 10k documents
- **Index Creation**: < 100ms

### Optimization Tips

1. **Pre-download models:**
```bash
python -c "from webnexus.services.embedding_service import embedding_service"
```

2. **Use GPU if available:**
```env
EMBEDDING_DEVICE=cuda
```

3. **Adjust search limits:**
```env
DEFAULT_SEARCH_LIMIT=5  # Fewer results = faster
```

---

## Additional Resources

- **Main Documentation**: [../../README.md](../../README.md)
- **FastAPI Server**: [../api/README.md](../api/README.md)
- **Docker Deployment**: [../../DOCKER.md](../../DOCKER.md)
- **MCP Protocol Spec**: https://modelcontextprotocol.io/
- **FastMCP Library**: https://github.com/jlowin/fastmcp

---

## Support

For issues and questions:
- **GitHub Issues**: https://github.com/WebNexus/WebNexus/issues
- **MCP Community**: https://modelcontextprotocol.io/community
- **Documentation**: https://WebNexus.readthedocs.io
