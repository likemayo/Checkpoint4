# Checkpoint 4 — E-Commerce Platform
## Partner Integration · Flash Sales · RMA System · Observability · Order Management

A production-ready e-commerce platform featuring partner catalog integration, flash sales with resilience patterns, a complete Returns Merchandise Authorization (RMA) system, comprehensive observability, and enhanced order management. Built with Flask, SQLite, and Docker for easy deployment.

---

## 🚀 Quick Start (Docker — Recommended)

```bash
# One-command startup (automatically seeds database on first run)
docker-compose up
```

**Application URL**: http://localhost:5000

**Default Login Credentials** (automatically created):
- **Admin**: `admin1` / `123`
- **Customer**: `john` / `password123`

The database is automatically seeded with demo data on first startup.

---

## 📋 Features

### Core E-Commerce
- Product catalog with inventory management
- Shopping cart and checkout
- User authentication and dashboard
- **Order history with filtering** (NEW — Checkpoint 4)
  - Filter by status (pending, processing, completed, cancelled)
  - Filter by date range
  - Keyword search across order ID, product names, and customer info
- Payment processing integration
- Receipt generation

### Partner Integration
- CSV/JSON feed ingestion from partners
- Validation and normalization of partner data
- Durable job queue with async processing
- Admin dashboard for partner management
- API key authentication with audit logging
- Scheduled feed imports
- Machine-readable contract endpoint
- Quickstart help endpoint with curl examples

### Flash Sales
- Time-limited promotional events
- Concurrent purchase handling
- Payment gateway resilience (circuit breaker, retry logic)
- Rate limiting and caching
- Real-time inventory tracking

### Returns & RMA System
- **Customer Portal**:
  - Request returns with reason selection
  - Upload supporting images
  - Track return status in real-time
  - View return history
  
- **Admin Workflow** (10-stage lifecycle):
  1. **Submitted** → Customer submits return request
  2. **Validating** → Automated validation checks
  3. **Approved** → Admin approves return
  4. **Shipping** → Customer ships item back
  5. **Received** → Warehouse receives package
  6. **Inspecting** → Quality inspection
  7. **Inspected** → Inspection complete
  8. **Disposition** → Decision made (Refund/Replacement/Repair/Store Credit/Reject)
  9. **Processing** → Financial/fulfillment processing
  10. **Completed** → RMA closed

- **Disposition Options**:
  - **Refund**: Full or partial refund processing
  - **Replacement**: Create new order and ship replacement
  - **Repair**: Send item for repair
  - **Store Credit**: Issue store credit
  - **Reject**: Deny return request

- **Admin Features**:
  - Multiple queue views (validation, shipping, inspection, disposition, processing)
  - Activity log tracking
  - Inventory adjustment automation
  - Metrics and analytics dashboard
  - Image review for customer submissions
  
- **RMA Notifications** (NEW — Checkpoint 4):
  - Real-time notification badge with unread count
  - Auto-polling every 30 seconds
  - Disposition-aware messages (different notifications for refund vs replacement)
  - Notification center page with mark-as-read functionality
  - Database-backed for persistence across sessions

### Low Stock Alerts (NEW — Checkpoint 4)
- Configurable low-stock threshold (default: 5 units)
- Admin dashboard display of products below threshold
- Environment variable configuration: `LOW_STOCK_THRESHOLD`
- Query parameter override for testing: `?low_stock_threshold=N`
- REST API endpoint: `/api/low-stock`
- Sorted by stock level (lowest first) for prioritization

### Observability & Monitoring (Checkpoint 3)
- **Structured Logging**:
  - JSON-formatted logs with severity levels (DEBUG, INFO, WARNING, ERROR)
  - Request/response logging with timing
  - Business event tracking (orders, RMAs, partner ingests)
  - Correlation IDs for request tracing
  - Log files: `logs/app.log`, `logs/errors.log`

- **Prometheus Metrics**:
  - HTTP request counters and histograms (latency tracking)
  - Business metrics:
    - `partner_ingest_jobs_total` — Total ingest jobs by status
    - `partner_ingest_duration_seconds` — Job processing time
    - `rma_requests_total` — RMA requests by status
    - `flash_sale_purchases_total` — Flash sale transactions
    - `low_stock_products` — Products below threshold (NEW)
  - Custom metrics endpoint: `/metrics` (Prometheus format)

- **Health Checks**:
  - `/health` — Application health status
  - `/health/detailed` — Component-level health (database, worker, cache)
  - Docker health checks for automatic restart

- **Debugging Support**:
  - Logs capture full request lifecycle (authentication, validation, business logic, errors)
  - Metrics enable performance analysis and capacity planning
  - Activity logs in RMA system provide audit trail
  - Partner ingest jobs track retry attempts and failure reasons
  - Flash sale circuit breaker logs gateway failures
  - Example: To debug slow checkout, check `http_request_duration_seconds_bucket{endpoint="/checkout"}`
  - Example: To debug failed RMA, check `logs/app.log` for correlation ID and trace full workflow

---

## 🐳 Docker Deployment

### Docker Architecture

The application runs in two containers:
- **web**: Flask application (http://localhost:5000)
  - Handles web requests
  - Admin interface
  - Customer portal
  - Metrics endpoint
  
- **worker**: Background worker
  - Processes partner feed imports
  - Handles async job queue
  - Retry with exponential backoff
  - Health monitoring

### Quick Docker Commands

\`\`\`bash
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Rebuild after code changes
docker-compose build && docker-compose up

# View logs
docker-compose logs -f web
docker-compose logs -f worker

# Check service health
docker-compose ps
curl http://localhost:5000/health

# Run tests
docker-compose exec web python -m pytest -v

# Run specific tests
docker-compose exec web python -m pytest tests/test_low_stock_alerts.py -v

# View metrics
curl http://localhost:5000/metrics

# Check logs for debugging
docker-compose exec web cat logs/app.log

# Stop services
docker-compose down

# Reset everything (deletes all data)
docker-compose down -v
\`\`\`

### Environment Variables

Configure in `docker-compose.yml` or create a `.env` file:

\`\`\`bash
# Application
APP_DB_PATH=/app/data/app.sqlite
APP_SECRET_KEY=your-secret-key-here

# Low Stock Alerts (NEW — Checkpoint 4)
LOW_STOCK_THRESHOLD=5

# Admin
ADMIN_API_KEY=admin-demo-key

# Observability
LOG_LEVEL=INFO
ENABLE_METRICS=true

# Partner Integration
HASH_KEYS=false

# Flash Sales
ENABLE_FLASH_SALES=true
CACHE_TTL=300
\`\`\`

**Using Environment Variables**:
\`\`\`bash
# Option 1: Set in shell
export LOW_STOCK_THRESHOLD=10
docker-compose up

# Option 2: Inline
LOW_STOCK_THRESHOLD=10 docker-compose up

# Option 3: Create .env file
echo "LOW_STOCK_THRESHOLD=10" > .env
docker-compose up
\`\`\`

---

## 🎯 Checkpoint 4 Features Summary

### 1. Order History Filtering (Feature 2.1)
Enhanced order history with flexible filtering capabilities:
- Filter by status, date range, and keyword search
- Server-side filtering with parameterized SQL
- Bookmarkable URLs via GET parameters

**Files**: `src/app.py`, `src/templates/dashboard.html`

### 2. Low Stock Alerts (Feature 2.2)
Configurable alerts for products below stock threshold:
- Environment variable: `LOW_STOCK_THRESHOLD` (default: 5)
- Admin dashboard display sorted by stock level
- REST API: `GET /api/low-stock`

**Files**: `src/app.py`, `src/product_repo.py`, `src/templates/admin_home.html`, `tests/test_low_stock_alerts.py`

### 3. RMA Notifications (Feature 2.3)
Real-time notifications for RMA status changes:
- Notification badge with unread count
- Auto-polling every 30 seconds
- Disposition-aware messages
- Database-backed persistence

**Files**: `src/notifications.py` (NEW), `src/rma/manager.py`, `migrations/0004_add_notifications.sql` (NEW)

---

## 🔍 Observability & Debugging (Checkpoint 3)

### Structured Logging

**Log Files**:
- `logs/app.log` — All application logs (INFO+)
- `logs/errors.log` — Error logs only

**What Gets Logged**:
- HTTP requests/responses with timing
- Authentication attempts
- Business events (orders, RMA status changes, partner ingests)
- Database operations
- External service calls with retry attempts
- Background job processing

**Debugging Examples**:
\`\`\`bash
# Find RMA-specific logs
docker-compose exec web grep "RMA-2025-001" logs/app.log

# Find recent errors
docker-compose exec web tail -n 1000 logs/errors.log

# Track request by correlation ID
docker-compose exec web grep "req-abc123" logs/app.log
\`\`\`

### Prometheus Metrics

**Available Metrics**:
- `http_requests_total` — HTTP request counters by endpoint
- `http_request_duration_seconds` — Request latency histograms
- `partner_ingest_jobs_total` — Ingest jobs by status
- `rma_requests_total` — RMA requests by status
- `flash_sale_purchases_total` — Flash sale transactions
- `low_stock_products` — Products below threshold (NEW)

**Access Metrics**:
\`\`\`bash
curl http://localhost:5000/metrics
curl -H "X-Admin-Key: admin-demo-key" http://localhost:5000/partner/metrics
\`\`\`

**Debugging with Metrics**:
- Slow checkout → Check `http_request_duration_seconds_bucket{endpoint="/checkout"}`
- Failed ingests → Check `partner_ingest_jobs_total{status="failed"}`
- RMA bottlenecks → Check `rma_requests_total` by status
- Low stock impact → Check `low_stock_products` gauge

### Debugging Scenarios

**Scenario: Order not appearing in dashboard**
1. Check logs: `grep "user_id=<id>" logs/app.log | grep "sale"`
2. Check database: Query `sale` table for user_id
3. Check metrics: `curl http://localhost:5000/metrics | grep dashboard`

**Scenario: Partner ingest job stuck**
1. Check job status: `curl -H "X-Admin-Key: admin-demo-key" http://localhost:5000/partner/jobs`
2. Check worker logs: `docker-compose logs worker | grep job_id=<id>`
3. Check metrics: `curl http://localhost:5000/metrics | grep partner_ingest`

**Scenario: RMA notification not received**
1. Check notification created: Query `notifications` table
2. Check RMA activity log: Query `rma_activity_log` for status changes
3. Check logs: `grep "RMA-<number>" logs/app.log | grep notification`
4. Check polling: Browser console → Network tab → verify `/api/notifications/count`

**Scenario: Low stock alerts not showing**
1. Check threshold: `echo $LOW_STOCK_THRESHOLD`
2. Query database: Check products with `stock <= threshold AND active=1`
3. Check logs: `grep "low_stock" logs/app.log`
4. Override: Visit `http://localhost:5000/admin?low_stock_threshold=10`

---

## 🧪 Testing

\`\`\`bash
# Run all tests
pytest -v

# Docker tests
docker-compose exec web python -m pytest -v

# Specific test categories
pytest tests/test_low_stock_alerts.py -v          # Low stock (NEW)
pytest tests/test_integration_partner_ingest.py -v # Partner integration
pytest tests/test_concurrent_checkout.py -v        # Concurrency
pytest tests/test_admin_auth.py -v                # RMA auth
pytest tests/test_rate_limiting.py -v              # Rate limiting
\`\`\`

---

## 📁 Project Structure

\`\`\`
src/
├── app.py                    # Main Flask app (order filtering, low stock)
├── dao.py                    # Database access layer
├── product_repo.py           # Product repository (low stock queries)
├── notifications.py          # Notification service (NEW — Checkpoint 4)
├── observability.py          # Metrics and logging
├── monitoring_routes.py      # Health checks
├── adapters/                 # Partner feed adapters
├── flash_sales/              # Flash sale features
├── partners/                 # Partner integration
├── rma/                      # RMA system
└── templates/                # HTML templates

db/
├── init.sql                  # Database schema
├── migrations/
│   └── 0004_add_notifications.sql  # Notifications table (NEW)

tests/
├── test_low_stock_alerts.py  # Low stock tests (NEW)
└── ...

docs/
├── ADR/
│   ├── 0021-lightweight-features-design.md      # Checkpoint 4 (NEW)
│   └── 0022-documentation-organization.md        # Doc structure (NEW)
└── UML/
    └── uml_views.md          # 4+1 views (updated for Checkpoint 4)
\`\`\`

---

## 📚 Documentation

- **[ADR 0021: Checkpoint 4 Features](docs/ADR/0021-lightweight-features-design.md)** — Design decisions
- **[ADR 0022: Documentation Organization](docs/ADR/0022-documentation-organization.md)** — Doc structure
- **[UML Diagrams](docs/UML/uml_views.md)** — 4+1 architectural views
- **[Checkpoint 3 Summary](docs/Checkpoint3.md)** — Previous features

---

## 🔧 Configuration

| Variable | Description | Default | Checkpoint |
|----------|-------------|---------|------------|
| `APP_DB_PATH` | Database path | `app.sqlite` | 1 |
| `APP_SECRET_KEY` | Session secret | `dev-insecure-secret` | 1 |
| `ADMIN_API_KEY` | Admin key | `admin-demo-key` | 2 |
| `LOW_STOCK_THRESHOLD` | Low stock threshold | `5` | **4 (NEW)** |
| `LOG_LEVEL` | Logging level | `INFO` | 3 |
| `ENABLE_METRICS` | Prometheus metrics | `true` | 3 |

---

## 🔐 Security Notes

- **Default credentials for development only** — Change in production
- **Admin API key** should be rotated regularly
- **Flask secret key** must be cryptographically secure
- **HTTPS required** for production deployments

---

## 👥 Contributors

- Pragya Chapagain
- Yanlin Wu

---

## 📝 License

Educational project for software engineering course.
