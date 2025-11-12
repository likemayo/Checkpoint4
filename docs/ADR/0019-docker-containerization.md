# ADR 0019: Docker Containerization Strategy

**Status**: Accepted  
**Date**: 2025-11-12  
**Decision Makers**: Development Team  
**Related ADRs**: ADR-0001 (Database Choice)

---

## Context

The Checkpoint3 retail system needs a consistent deployment strategy that:
- Works across different development environments (macOS, Linux, Windows)
- Simplifies dependency management
- Provides isolation from host system
- Enables easy scaling and replication
- Supports continuous integration/deployment

### Current Situation
- Python application with multiple dependencies
- SQLite database requiring file system persistence
- Background worker for async tasks
- Need for development/production parity

### Requirements
- Portable deployment across environments
- Easy setup for new developers
- Consistent runtime environment
- Separate web and worker processes
- Persistent data storage
- Simple orchestration

---

## Decision

We will use **Docker containerization** with **Docker Compose** for orchestration.

### Architecture

```yaml
services:
  web:
    - Flask application
    - Port 5000 exposed
    - Mounts data volume
    - Health checks
    
  worker:
    - Background processing
    - Shares database volume
    - No exposed ports
```

### Container Design

**1. Base Image**
```dockerfile
FROM python:3.11-slim
```
- Official Python image
- Slim variant for smaller size
- Stable Python 3.11 runtime

**2. Dependency Installation**
```dockerfile
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
```
- Cached layer for dependencies
- Fast rebuilds when code changes

**3. Application Code**
```dockerfile
COPY src/ /app/src/
WORKDIR /app
```
- Separate layer for code
- Efficient layer caching

**4. Volume Mounts**
```yaml
volumes:
  - ./data:/app/data
```
- Persistent database
- Log files
- User uploads

---

## Rationale

### Why Docker?

1. **Environment Consistency**
   - Same runtime everywhere
   - No "works on my machine" issues
   - Reproducible builds

2. **Dependency Isolation**
   - No conflicts with host system
   - Clean dependency management
   - Easy version control

3. **Simplified Deployment**
   - Single `docker-compose up` command
   - No manual dependency installation
   - Automated container orchestration

4. **Development Efficiency**
   - Quick onboarding for new developers
   - Consistent dev/prod environments
   - Easy testing of different configurations

5. **Scalability Foundation**
   - Easy to add more containers
   - Horizontal scaling possible
   - Load balancer ready

### Why Docker Compose?

1. **Multi-Container Management**
   - Orchestrates web + worker
   - Manages networks automatically
   - Handles service dependencies

2. **Configuration as Code**
   - `docker-compose.yml` version controlled
   - Easy to understand and modify
   - Self-documenting setup

3. **Development Friendly**
   - Simple commands (up, down, restart)
   - Log aggregation
   - Volume management

### Why NOT Kubernetes?

- **Overkill for Current Scale**: Single host sufficient
- **Complexity**: Steep learning curve
- **Resources**: Requires more infrastructure
- **Cost**: Not justified for prototype/small deployment

---

## Implementation Details

### Directory Structure

```
Checkpoint3/
├── Dockerfile              # Container definition
├── docker-compose.yml      # Orchestration config
├── requirements.txt        # Python dependencies
├── src/                    # Application code
└── data/                   # Persistent data
    ├── app.sqlite          # Database
    ├── logs/               # Application logs
    └── uploads/            # User files
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ /app/src/
COPY db/ /app/db/
COPY scripts/ /app/scripts/

# Create necessary directories
RUN mkdir -p /app/data/logs /app/data/uploads/rma

# Environment variables
ENV FLASK_APP=src.app:create_app
ENV PYTHONUNBUFFERED=1
ENV APP_DB_PATH=/app/data/app.sqlite

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import requests; requests.get('http://localhost:5000/health')"

# Run migrations and start app
CMD python scripts/run_migrations.py && \
    flask run --host=0.0.0.0 --port=5000
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    container_name: checkpoint3-web
    ports:
      - "5000:5000"
    volumes:
      - ./data:/app/data
      - ./src:/app/src  # For development hot-reload
    environment:
      - FLASK_ENV=development
      - APP_DB_PATH=/app/data/app.sqlite
      - ADMIN_API_KEY=admin-demo-key
    restart: unless-stopped
    depends_on:
      - worker

  worker:
    build: .
    container_name: checkpoint3-worker
    volumes:
      - ./data:/app/data
    environment:
      - APP_DB_PATH=/app/data/app.sqlite
    command: python scripts/background_worker.py
    restart: unless-stopped
```

### Volume Management

**Data Persistence Strategy**:
- **Bind Mount**: `./data` on host → `/app/data` in container
- **Benefits**:
  - Easy backup (just copy `data/` folder)
  - Direct access to database for debugging
  - Survives container recreation
  - Simple migration

**File Permissions**:
- Container runs as root
- Writes to mounted volume
- Host can read/write files

---

## Consequences

### Positive

✅ **Easy Setup**
- New developers: `docker-compose up`
- No manual dependency installation
- Consistent environment

✅ **Environment Isolation**
- No conflicts with host Python
- Clean dependency management
- Multiple projects can coexist

✅ **Production Ready**
- Same container in dev and prod
- Reduces deployment issues
- Easy rollbacks

✅ **Scalability**
- Can add more web containers
- Load balancer integration ready
- Horizontal scaling possible

✅ **Portability**
- Runs on any Docker-capable host
- Cloud deployment ready (AWS, GCP, Azure)
- Easy CI/CD integration

### Negative

⚠️ **Resource Overhead**
- Docker daemon uses memory
- Container overhead (~100MB)
- Disk space for images

⚠️ **Learning Curve**
- Team needs Docker knowledge
- Debugging inside containers
- Understanding networking

⚠️ **Development Workflow**
- May need volume mounts for live reload
- Container rebuilds for dependency changes
- Log access via docker commands

⚠️ **SQLite Limitations**
- File-based database in container
- Concurrent access limitations
- Need careful volume mounting

### Mitigation Strategies

**For Development**:
- Volume mount source code for hot reload
- Use development mode in Flask
- Expose logs via `docker-compose logs`

**For Production**:
- Use production WSGI server (gunicorn)
- Implement proper health checks
- Set restart policies
- Monitor container metrics

**For Database**:
- Regular backups of `data/` directory
- Consider migration to PostgreSQL if concurrency issues arise
- Use WAL mode for better concurrent access

---

## Alternatives Considered

### 1. Virtual Environment (venv)

**Pros**:
- Native Python tool
- Lower overhead
- Simpler debugging

**Cons**:
- System-dependent issues
- Manual dependency management
- No process isolation
- Deployment complexity

**Why Not**: Less consistent across environments, harder to deploy

### 2. Kubernetes

**Pros**:
- Production-grade orchestration
- Auto-scaling
- Service discovery
- High availability

**Cons**:
- Complex setup
- Overkill for current scale
- Steep learning curve
- Infrastructure overhead

**Why Not**: Too complex for current needs and team size

### 3. Serverless (AWS Lambda)

**Pros**:
- No infrastructure management
- Auto-scaling
- Pay-per-use

**Cons**:
- Cold start latency
- Vendor lock-in
- SQLite not suitable
- Request timeout limits

**Why Not**: Architecture not suitable for long-running processes and database requirements

### 4. Platform as a Service (Heroku)

**Pros**:
- Easy deployment
- Managed infrastructure
- Add-ons ecosystem

**Cons**:
- Cost
- Less control
- Vendor lock-in
- Ephemeral file system (bad for SQLite)

**Why Not**: Database persistence issues and cost considerations

---

## Validation

### Success Criteria

- [x] Single command startup: `docker-compose up`
- [x] Consistent environment across team
- [x] Data persists across container restarts
- [x] Web and worker processes run independently
- [x] Health checks functional
- [x] Logs accessible via docker commands
- [x] Port 5000 accessible on host

### Testing

```bash
# Build and start
docker-compose up --build

# Check running containers
docker-compose ps

# View logs
docker-compose logs -f web

# Health check
curl http://localhost:5000/health

# Stop all
docker-compose down

# Verify data persists
ls -la ./data/app.sqlite
```

---

## Migration Path

### From Development to Production

1. **Build Image**
   ```bash
   docker build -t checkpoint3:latest .
   ```

2. **Push to Registry**
   ```bash
   docker tag checkpoint3:latest registry.example.com/checkpoint3:latest
   docker push registry.example.com/checkpoint3:latest
   ```

3. **Deploy**
   ```bash
   docker pull registry.example.com/checkpoint3:latest
   docker-compose -f docker-compose.prod.yml up -d
   ```

### Future Enhancements

1. **Multi-stage Builds**
   - Separate build and runtime images
   - Smaller final image size

2. **CI/CD Integration**
   - Automated builds on commit
   - Testing in containers
   - Automated deployment

3. **Container Orchestration**
   - Docker Swarm for simple clustering
   - Kubernetes if scale demands

4. **Database Migration**
   - PostgreSQL in separate container
   - Managed database service

---

## References

- Docker Documentation: https://docs.docker.com/
- Docker Compose: https://docs.docker.com/compose/
- Flask in Docker: https://flask.palletsprojects.com/en/3.0.x/deploying/
- SQLite in Docker: Best practices for file-based databases

---

## Approval

**Decision**: Approved  
**Implementation Status**: Complete  
**Review Date**: 2025-11-12

---

*This ADR documents our containerization strategy and provides guidance for deployment and scaling.*
