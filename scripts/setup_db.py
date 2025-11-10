#!/usr/bin/env python3
"""
Database Setup Script for WebNexus

Initializes the SQLite database with proper tables and indexes.
Creates the vector storage directory and initializes FAISS indexes.
"""

import os
import sys
import logging
import asyncio
from pathlib import Path

# Add src to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))

from webnexus.config.database import db_config
from webnexus.config.settings import settings
from webnexus.services.vector_service import vector_service
from webnexus.services.embedding_service import embedding_service
from webnexus.models.database import Base, Document, DocumentChunk, Embedding, CodeExample, CrawlSession

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_data_directories():
    """Create necessary data directories."""
    logger.info("Creating data directories...")
    
    # Create main data directory
    data_dir = project_root / "data"
    data_dir.mkdir(exist_ok=True)
    logger.info(f"Created data directory: {data_dir}")
    
    # Create vector storage directory
    vector_dir = data_dir / "vectors"
    vector_dir.mkdir(exist_ok=True)
    logger.info(f"Created vector directory: {vector_dir}")
    
    # Create database directory
    db_dir = data_dir / "db"
    db_dir.mkdir(exist_ok=True)
    logger.info(f"Created database directory: {db_dir}")
    
    return data_dir, vector_dir, db_dir


def initialize_database():
    """Initialize the SQLite database with all tables."""
    logger.info("Initializing SQLite database...")
    
    try:
        # Initialize the database engine and create tables
        db_config.initialize()
        logger.info("Database tables created successfully")
        
        # Test database connection
        session = db_config.get_session()
        try:
            # Verify we can query the database
            from webnexus.models.database import Document
            count = session.query(Document).count()
            logger.info(f"Database connection verified. Current document count: {count}")
        finally:
            session.close()
            
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        return False


async def initialize_services():
    """Initialize core services."""
    logger.info("Initializing services...")
    
    try:
        # Initialize embedding service (download model if needed)
        logger.info("Loading embedding model...")
        embedding_service._load_model()
        logger.info("Embedding service initialized")
        
        # Initialize vector service (create FAISS index)
        logger.info("Initializing vector service...")
        vector_service._initialize_index()
        logger.info("Vector service initialized")
        
        # Test services
        logger.info("Testing services...")
        test_text = ["This is a test document for verification."]
        embeddings = await embedding_service.embed_documents(test_text)
        logger.info(f"Service test successful. Generated embedding dimension: {len(embeddings[0])}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        return False


def print_configuration():
    """Print current configuration."""
    logger.info("=== WebNexus Configuration ===")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    logger.info(f"Chunking Strategy: {settings.chunking_strategy}")
    logger.info(f"Original Chunk Size: {settings.original_chunk_size}")
    logger.info(f"Advanced Chunk Size: {settings.advanced_chunk_size}")
    logger.info(f"Database URL: {settings.database_url}")
    logger.info(f"Vector Index Path: {settings.vector_index_path}")
    logger.info(f"Max Concurrent Crawls: {settings.max_concurrent_crawls}")
    logger.info("=================================")


def print_usage_instructions():
    """Print usage instructions."""
    logger.info("\n=== Setup Complete! ===")
    logger.info("WebNexus database and services are now ready.")
    logger.info("\nTo start the services:")
    logger.info("1. FastAPI Server: uv run uvicorn src.api.main:app --reload --port 8000")
    logger.info("2. MCP Server: uv run python src/mcp/server.py")
    logger.info("\nTo test the system:")
    logger.info("- Visit http://localhost:8000/docs for API documentation")
    logger.info("- Use the MCP tools in Claude Code or other MCP clients")
    logger.info("- Try crawling a website: POST /api/crawl/single")
    logger.info("- Search documents: POST /api/search/query")
    logger.info("\nDatabase location: data/db/WebNexus.db")
    logger.info("Vector index location: data/vectors/")
    logger.info("========================")


async def main():
    """Main setup function."""
    logger.info("Starting WebNexus database setup...")
    
    try:
        # Print configuration
        print_configuration()
        
        # Create directories
        data_dir, vector_dir, db_dir = create_data_directories()
        
        # Initialize database
        if not initialize_database():
            logger.error("Database initialization failed")
            return False
        
        # Initialize services
        if not await initialize_services():
            logger.error("Service initialization failed")
            return False
        
        # Print success message and instructions
        print_usage_instructions()
        return True
        
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return False


def reset_database():
    """Reset the database (remove all data)."""
    logger.warning("=== RESETTING DATABASE ===")
    logger.warning("This will DELETE all crawled documents and embeddings!")
    
    response = input("Are you sure you want to reset the database? (yes/no): ")
    if response.lower() != "yes":
        logger.info("Database reset cancelled")
        return
    
    try:
        # Remove database file
        db_file = Path(settings.database_url.replace("sqlite:///", ""))
        if db_file.exists():
            db_file.unlink()
            logger.info(f"Removed database file: {db_file}")
        
        # Remove vector index files
        vector_dir = Path(settings.vector_index_path).parent
        if vector_dir.exists():
            import shutil
            shutil.rmtree(vector_dir)
            logger.info(f"Removed vector directory: {vector_dir}")
        
        logger.info("Database reset complete. Run setup again to reinitialize.")
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--reset":
        reset_database()
    else:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)