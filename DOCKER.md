# 🐳 Docker Deployment Guide for WebNexus

Complete guide for running WebNexus in Docker containers.

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Build and start the services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (⚠️ deletes all data)
docker-compose down -v
```

### Using Docker CLI

```bash
# Build the image
docker build -t webnexus:latest .

# Run FastAPI server
docker run -d \
  --name webnexus-api \
  -p 8000:8000 \
  -v webnexus-data:/app/data \
  webnexus:latest

# Run MCP server
docker run -d \
  --name webnexus-mcp \
  -p 8051:8051 \
  -v webnexus-data:/app/data \
  webnexus:latest \
  python -m webnexus.mcp.server --stdio
```

## Configuration

### Environment Variables

You can customize WebNexus behavior using environment variables:

```bash
# Database
DATABASE_URL=sqlite:////app/data/db/webnexus.db

# Server settings
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO

# Embedding settings
EMBEDDING_MODEL=dunzhang/stella_en_400M_v5
EMBEDDING_DEVICE=cpu  # or cuda for GPU

# Crawling settings
MAX_CONCURRENT_CRAWLS=10
MAX_CRAWL_DEPTH=3
CRAWL_TIMEOUT=30

# Search settings
DEFAULT_SEARCH_LIMIT=5
USE_HYBRID_SEARCH=true
USE_RERANKING=true
```

### Using Environment File

Create a `.env` file:

```env
DATABASE_URL=sqlite:////app/data/db/webnexus.db
LOG_LEVEL=INFO
MAX_CONCURRENT_CRAWLS=5
```

Then run with docker-compose:

```yaml
# docker-compose.yml
services:
  webnexus-api:
    # ...
    env_file:
      - .env
```

## Volume Management

### Data Persistence

WebNexus stores three types of data:

1. **Database** (`/app/data/db/`) - SQLite database with documents, chunks, embeddings
2. **Models** (`/app/data/models/`) - Downloaded ML models (~800MB for Stella)
3. **Vectors** (`/app/data/vectors/`) - FAISS vector indexes

**Named Volume (Recommended):**
```bash
# Create named volume
docker volume create webnexus-data

# Use in docker run
docker run -v webnexus-data:/app/data webnexus:latest

# Inspect volume
docker volume inspect webnexus-data

# Backup volume
docker run --rm -v webnexus-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/webnexus-backup.tar.gz -C /data .

# Restore volume
docker run --rm -v webnexus-data:/data -v $(pwd):/backup \
  alpine tar xzf /backup/webnexus-backup.tar.gz -C /data
```

**Bind Mount (Development):**
```bash
# Mount local directory
docker run -v $(pwd)/data:/app/data webnexus:latest
```

## First Run Setup

### Initialize Database

The database will be automatically initialized on first run. To manually initialize:

```bash
# Enter container
docker exec -it webnexus-api /bin/bash

# Run database setup
python scripts/setup_db.py
```

### Download Models

ML models are downloaded on first use (~800MB). To pre-download:

```bash
# Inside container
python -c "from webnexus.services.embedding_service import embedding_service; embedding_service._load_model()"
```

## Building for Production

### Optimize Image Size

```bash
# Build with BuildKit for better caching
DOCKER_BUILDKIT=1 docker build -t webnexus:latest .

# Multi-platform build
docker buildx build --platform linux/amd64,linux/arm64 -t webnexus:latest .
```

### Use GPU Support

For CUDA GPU support:

```dockerfile
# Use CUDA base image
FROM nvidia/cuda:12.1.0-base-ubuntu22.04 as builder

# Install Python
RUN apt-get update && apt-get install -y python3.12
```

Then run with GPU:

```bash
docker run --gpus all -p 8000:8000 webnexus:latest
```

## Common Commands

### Monitoring

```bash
# View logs
docker logs -f webnexus-api

# Check resource usage
docker stats webnexus-api

# Inspect container
docker inspect webnexus-api

# Health check
curl http://localhost:8000/health
```

### Maintenance

```bash
# Restart container
docker restart webnexus-api

# Update to latest image
docker-compose pull
docker-compose up -d

# Clean up old images
docker image prune -a

# View container processes
docker top webnexus-api
```

### Development

```bash
# Run with code mounted (live reload)
docker run -p 8000:8000 \
  -v $(pwd)/webnexus:/app/webnexus \
  -v webnexus-data:/app/data \
  webnexus:latest \
  uvicorn webnexus.api.main:app --host 0.0.0.0 --reload

# Run tests in container
docker exec webnexus-api python scripts/test_mcp.py

# Open shell in container
docker exec -it webnexus-api /bin/bash
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs webnexus-api

# Verify volumes
docker volume ls
docker volume inspect webnexus-data

# Check permissions
docker exec webnexus-api ls -la /app/data
```

### Out of Memory

```bash
# Increase memory limit
docker run -m 4g webnexus:latest

# In docker-compose.yml:
services:
  webnexus-api:
    mem_limit: 4g
```

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Use different port
docker run -p 8001:8000 webnexus:latest
```

### Database Locked

```bash
# Check if multiple containers accessing same volume
docker ps -a | grep webnexus

# Stop all containers
docker-compose down

# Restart
docker-compose up -d
```

## Security Best Practices

1. **Non-root user**: Container runs as user `webnexus` (UID 1000)
2. **Read-only filesystem**: Mount `/tmp` as writable only
3. **No secrets in image**: Use environment variables or secrets management
4. **Regular updates**: Keep base images updated
5. **Network isolation**: Use Docker networks for service communication

```yaml
# Enhanced security in docker-compose.yml
services:
  webnexus-api:
    security_opt:
      - no-new-privileges:true
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
```

## Performance Optimization

### Multi-stage Build Benefits

- **Smaller image**: Final image ~500MB vs ~2GB without multi-stage
- **Faster deployments**: Less data to transfer
- **Better security**: No build tools in production image

### Resource Limits

```yaml
# docker-compose.yml
services:
  webnexus-api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 2G
```

### Caching Strategy

The Dockerfile is optimized for layer caching:
1. Dependencies installed first (changes rarely)
2. Code copied last (changes frequently)
3. Multi-stage build separates build and runtime

## Production Checklist

- [ ] Set proper environment variables
- [ ] Configure persistent volumes
- [ ] Set up health checks
- [ ] Configure resource limits
- [ ] Enable logging to external system
- [ ] Set up backup strategy
- [ ] Configure reverse proxy (nginx/traefik)
- [ ] Enable HTTPS
- [ ] Set up monitoring (Prometheus/Grafana)
- [ ] Configure restart policy

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Best Practices for Writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [WebNexus Documentation](./README.md)
