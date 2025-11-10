"""Settings configuration for WebNexus"""

import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

# Get project root (3 levels up from this file: src/config/settings.py)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Database settings - use absolute path
    database_url: str = f"sqlite:///{PROJECT_ROOT}/data/WebNexus.db"
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    api_port: int = 8000
    mcp_port: int = 8051
    
    # Embedding settings
    embedding_model: str = "dunzhang/stella_en_400M_v5"
    embedding_dimensions: int = 1024
    embedding_batch_size: int = 100
    embedding_device: str = "auto"  # auto, cpu, cuda
    
    # Crawling settings
    max_concurrent_crawls: int = 10
    max_crawl_depth: int = 3
    crawl_timeout: int = 30
    
    # Search settings
    default_search_limit: int = 5
    use_hybrid_search: bool = True
    use_reranking: bool = True
    
    # Vector storage settings
    vector_index_path: str = "./data/vectors/faiss_index.bin"
    
    # Chunking strategy settings
    chunking_strategy: str = "original"  # "original", "advanced", "specialized"
    original_chunk_size: int = 5000 
    advanced_chunk_size: int = 1000  # For advanced chunker
    chunk_overlap: int = 100  # Only for advanced chunker
    
    # API settings
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000"]
    
    # Development settings
    debug: bool = False
    log_level: str = "INFO"
    
    # Optional API keys
    openai_api_key: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()