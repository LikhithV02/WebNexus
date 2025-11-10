# WebNexus Dockerfile
# Multi-stage build for efficient image size

# Stage 1: Builder - Install dependencies
FROM python:3.12-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv (fast Python package installer)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock* ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Stage 2: Runtime - Create final image
FROM python:3.12-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 webnexus && \
    mkdir -p /app /app/data /app/data/models /app/data/vectors /app/data/db && \
    chown -R webnexus:webnexus /app

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy application code
COPY --chown=webnexus:webnexus webnexus/ ./webnexus/
COPY --chown=webnexus:webnexus scripts/ ./scripts/
COPY --chown=webnexus:webnexus pyproject.toml ./

# Set environment variables
ENV PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # WebNexus specific
    DATABASE_URL="sqlite:////app/data/db/webnexus.db" \
    # Disable unnecessary warnings
    TRANSFORMERS_VERBOSITY=error \
    TRANSFORMERS_NO_ADVISORY_WARNINGS=1 \
    HF_HUB_DISABLE_PROGRESS_BARS=1 \
    TOKENIZERS_PARALLELISM=false

# Create data directories with proper permissions
RUN chown -R webnexus:webnexus /app/data

# Switch to non-root user
USER webnexus

# Expose ports
# 8000 for FastAPI server
# 8051 for MCP server
EXPOSE 8000 8051

# Health check for FastAPI server
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Default command: Run FastAPI server
# Can be overridden with docker run command
CMD ["uvicorn", "webnexus.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
