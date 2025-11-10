#!/usr/bin/env python3
"""
Server Startup Script for WebNexus

Convenient script to start both FastAPI and MCP servers with proper configuration.
Supports running servers individually or together in different modes.
"""

import os
import sys
import time
import signal
import subprocess
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# Add src to Python path
script_dir = Path(__file__).parent.absolute()
project_root = script_dir.parent
src_path = project_root / "src"
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global list to track running processes
running_processes: List[subprocess.Popen] = []


def signal_handler(signum, frame):
    """Handle shutdown signals."""
    logger.info(f"Received signal {signum}, shutting down servers...")
    shutdown_servers()
    sys.exit(0)


def shutdown_servers():
    """Gracefully shutdown all running servers."""
    for process in running_processes:
        if process.poll() is None:  # Process is still running
            logger.info(f"Terminating process {process.pid}...")
            try:
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"Force killing process {process.pid}...")
                process.kill()
            except Exception as e:
                logger.error(f"Error stopping process {process.pid}: {e}")
    
    running_processes.clear()
    logger.info("All servers stopped")


def start_fastapi_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = True):
    """Start the FastAPI server."""
    logger.info(f"Starting FastAPI server on {host}:{port}")
    
    cmd = [
        sys.executable, "-m", "uvicorn",
        "src.api.main:app",
        "--host", host,
        "--port", str(port),
    ]
    
    if reload:
        cmd.append("--reload")
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        running_processes.append(process)
        logger.info(f"FastAPI server started with PID {process.pid}")
        return process
        
    except Exception as e:
        logger.error(f"Failed to start FastAPI server: {e}")
        return None


def start_mcp_server(port: int = 8051, transport: str = "stdio"):
    """Start the MCP server."""
    logger.info(f"Starting MCP server on port {port} with {transport} transport")
    
    cmd = [sys.executable, "src/mcp/server.py"]
    
    if transport == "ws":
        cmd.extend(["--port", str(port)])
    elif transport == "stdio":
        cmd.append("--stdio")
    
    try:
        process = subprocess.Popen(
            cmd,
            cwd=project_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        running_processes.append(process)
        logger.info(f"MCP server started with PID {process.pid}")
        return process
        
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        return None


def check_dependencies():
    """Check if required dependencies are available."""
    logger.info("Checking dependencies...")
    
    try:
        # Check if uv is available
        result = subprocess.run(["uv", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            logger.error("UV package manager not found. Please install uv first.")
            return False
        logger.info(f"UV version: {result.stdout.strip()}")
        
        # Check if database exists
        from webnexus.config.settings import settings
        db_file = Path(settings.database_url.replace("sqlite:///", ""))
        if not db_file.exists():
            logger.warning(f"Database file not found at {db_file}")
            logger.warning("Run 'python scripts/setup_db.py' first to initialize the database")
            return False
        
        logger.info("Dependencies check passed")
        return True
        
    except Exception as e:
        logger.error(f"Dependency check failed: {e}")
        return False


def monitor_processes():
    """Monitor running processes and restart if needed."""
    logger.info("Monitoring servers...")
    
    try:
        while running_processes:
            for i, process in enumerate(running_processes):
                if process.poll() is not None:
                    logger.warning(f"Process {process.pid} has stopped")
                    # Could implement restart logic here
            
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Monitoring interrupted")


def print_server_info():
    """Print information about running servers."""
    logger.info("\n=== WebNexus Servers Started ===")
    logger.info("FastAPI Server: http://localhost:8000")
    logger.info("  - API Documentation: http://localhost:8000/docs")
    logger.info("  - Health Check: http://localhost:8000/health")
    logger.info("  - System Stats: http://localhost:8000/api/stats")
    logger.info("")
    logger.info("MCP Server: localhost:8051")
    logger.info("  - Tools: crawl_website, search_documents, get_sources")
    logger.info("")
    logger.info("Press Ctrl+C to stop all servers")
    logger.info("===================================\n")


def main():
    """Main function to handle command line arguments and start servers."""
    parser = argparse.ArgumentParser(description="WebNexus Server Startup Script")
    
    parser.add_argument(
        "--mode", 
        choices=["both", "api", "mcp"],
        default="both",
        help="Which servers to start (default: both)"
    )
    
    parser.add_argument(
        "--api-host",
        default="127.0.0.1", 
        help="FastAPI server host (default: 127.0.0.1)"
    )
    
    parser.add_argument(
        "--api-port",
        type=int,
        default=8000,
        help="FastAPI server port (default: 8000)"
    )
    
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8051,
        help="MCP server port (default: 8051)"
    )
    
    parser.add_argument(
        "--mcp-transport",
        choices=["stdio", "ws"],
        default="stdio",
        help="MCP transport type (default: stdio)"
    )
    
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable FastAPI auto-reload"
    )
    
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check dependencies and configuration"
    )
    
    args = parser.parse_args()
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check dependencies
    if not check_dependencies():
        logger.error("Dependency check failed. Exiting.")
        return 1
    
    if args.check_only:
        logger.info("Dependency check completed successfully")
        return 0
    
    logger.info(f"Starting servers in mode: {args.mode}")
    
    # Start requested servers
    try:
        if args.mode in ["both", "api"]:
            fastapi_process = start_fastapi_server(
                host=args.api_host,
                port=args.api_port,
                reload=not args.no_reload
            )
            if not fastapi_process:
                return 1
        
        if args.mode in ["both", "mcp"]:
            mcp_process = start_mcp_server(
                port=args.mcp_port,
                transport=args.mcp_transport
            )
            if not mcp_process:
                return 1
        
        # Give servers time to start
        time.sleep(2)
        
        # Print server information
        print_server_info()
        
        # Monitor processes
        monitor_processes()
        
        return 0
        
    except Exception as e:
        logger.error(f"Error starting servers: {e}")
        return 1
    finally:
        shutdown_servers()


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Startup interrupted by user")
        shutdown_servers()
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        shutdown_servers()
        sys.exit(1)