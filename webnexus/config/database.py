"""Database configuration for WebNexus"""

import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .settings import settings


class DatabaseConfig:
    """Database configuration and setup"""
    
    def __init__(self):
        self.database_url = settings.database_url
        self.engine = None
        self.SessionLocal = None
        self.Base = declarative_base()
        self.metadata = MetaData()
    
    def initialize(self):
        """Initialize database connection and create tables if needed"""
        # Ensure data directory exists
        if self.database_url.startswith("sqlite:///"):
            db_path = self.database_url.replace("sqlite:///", "")
            db_dir = Path(db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
        
        # Create engine and session
        self.engine = create_engine(
            self.database_url,
            echo=settings.debug,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {}
        )
        
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Create tables
        self.create_tables()
    
    def create_tables(self):
        """Create database tables"""
        if self.engine:
            # Import Base from models to ensure all models are loaded
            from ..models.database import Base
            Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session"""
        if not self.SessionLocal:
            self.initialize()
        return self.SessionLocal()
    
    def close(self):
        """Close database connections"""
        if self.engine:
            self.engine.dispose()


# Global database instance
db_config = DatabaseConfig()