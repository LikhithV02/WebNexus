#!/bin/bash
# WebNexus MCP Server Launcher
# This script runs the MCP server for Claude Desktop

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Change to project root
cd "$PROJECT_ROOT"

# Use full path to uv (Claude Desktop doesn't have user PATH)
exec /Users/likhithv/.local/bin/uv run python -m src.mcp.server --stdio