````markdown
# E-Commerce Platform with Partner Catalog Ingest & RMA System

A comprehensive e-commerce platform featuring partner integration, flash sales, and a complete Returns Merchandise Authorization (RMA) system. Built with Flask, SQLite, and Docker for easy deployment.

## 🚀 Features

### Core E-Commerce
- Product catalog with inventory management
- Shopping cart and checkout
- User authentication and dashboard
- Order history and receipts
- Payment processing integration

### Partner Integration
- CSV/JSON feed ingestion from partners
- Validation and normalization of partner data
- Durable job queue with async processing
- Admin dashboard for partner management
- API key authentication and audit logging
- Scheduled feed imports

### Flash Sales
- Time-limited promotional events
- Concurrent purchase handling
- Payment gateway resilience (circuit breaker, retry logic)
- Rate limiting and caching
- Real-time inventory tracking

### Returns & RMA System (NEW)
- **Customer Portal**:
  - Request returns with reason selection
  - Upload supporting images
  - Track return status in real-time
  - View return history
  
- **Admin Workflow** (10-stage process):
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

- **Disposition Types**:
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

## 🐳 Docker Deployment (Recommended)

The easiest way to run the entire system is with Docker Compose:

```bash
# One-command startup (automatically seeds database on first run)
docker-compose up
```

The application will be available at **http://localhost:5000**

**Default Login Credentials (automatically created):**
- **Admin**: username: `admin1`, password: `123`
- **Customer**: username: `john`, password: `password123`

The database is automatically seeded with demo data on first startup.

### Docker Architecture

The application runs in two containers:
- **web**: Flask application (port 5000)
  - Handles web requests
  - Admin interface
  - Customer portal
  
- **worker**: Background worker
  - Processes partner feed imports
  - Handles async job queue
  - Retry with exponential backoff

### Quick Docker Commands

```bash
# Start services in background
docker-compose up -d

# View logs
docker-compose logs -f web
docker-compose logs -f worker

# View all logs
docker-compose logs -f

# Run tests in container
docker-compose exec web python -m pytest -v

# Access Python shell in container
docker-compose exec web python

# Run database migrations
docker-compose exec web python scripts/run_migrations.py

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v

# Rebuild after code changes
docker-compose build
docker-compose up
```

### Docker Volumes

Persistent data is stored in Docker volumes:
- `checkpoint3_db_data`: SQLite database
- `checkpoint3_uploads`: RMA image uploads

Data persists between container restarts. To reset:
```bash
docker-compose down -v
docker-compose up
```

### Environment Variables (Docker)

Set in `docker-compose.yml` or create a `.env` file:

```bash
# Application
APP_DB_PATH=/app/data/app.sqlite
APP_SECRET_KEY=your-secret-key-here

# Admin
ADMIN_API_KEY=admin-demo-key

# Partner Integration
HASH_KEYS=false

# Flash Sales
ENABLE_FLASH_SALES=true
```

### Health Checks

Docker health checks automatically monitor service health:
- Web: `http://localhost:5000/health`
- Worker: Checks if worker process is running

View health status:
```bash
docker-compose ps
```

---

## 🛠️ Manual Setup (Local Development)

### Prerequisites
- Python 3.10 or higher
- pip
- virtualenv (recommended)

### Installation Steps

1. **Create virtual environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Initialize database**
```bash
# Create schema and run migrations
python -m src.main

# Seed demo data (includes default admin account)
python -m src.seed
python -m db.seed_flash_sales
```

**Default Credentials (after seeding):**
- **Admin**: username: `admin1`, password: `123`
- **Customer**: username: `john`, password: `password123`
- **Customer**: username: `jane`, password: `password123`
- **Customer**: username: `alice`, password: `password123`

> ⚠️ **Important**: Each person running the app has their own local database. 
> The database file is NOT shared between different laptops/machines.
> Everyone must run `python -m src.seed` to create accounts on their own machine.

4. **Set environment variables**
```bash
export APP_DB_PATH=$(pwd)/app.sqlite
export ADMIN_API_KEY=admin-demo-key
export APP_SECRET_KEY=dev-insecure-secret
```

5. **Start Flask application**
```bash
python -m src.app
# Application runs on http://127.0.0.1:5000
```

6. **Start background worker (in separate terminal)**
```bash
source .venv/bin/activate
export APP_DB_PATH=$(pwd)/app.sqlite
python -c "from src.partners.ingest_queue import start_worker; from pathlib import Path; start_worker(str(Path('.').resolve()/ 'app.sqlite'))"
```

---

## 📋 Usage Guide

### Customer Workflow

1. **Browse and Purchase**
   - Visit http://localhost:5000
   - Register/login
   - Browse products
   - Add to cart and checkout

2. **Request Return**
   - Go to Dashboard
   - Find order with "Request Return" button
   - Fill return form with reason
   - Upload images (optional)
   - Submit request

3. **Track Return**
   - Click "My Returns" in navigation
   - View status of all returns
   - Track progress through workflow stages

### Admin Workflow

1. **Access Admin Portal**
   - Go to http://localhost:5000/rma/admin/login
   - Login with admin credentials
   - Navigate admin dashboard

2. **Process Returns**
   - **Validation Queue**: Review and approve/reject new requests
   - **Shipping Queue**: Monitor items being shipped
   - **Receiving Queue**: Mark items as received
   - **Inspection Queue**: Perform quality inspection
   - **Disposition Queue**: Decide refund/replacement/repair/reject
   - **Processing Queue**: Complete refunds or replacements

3. **View Analytics**
   - Metrics dashboard shows RMA statistics
   - Activity logs for audit trail
   - Completed RMA history

### Partner Integration

1. **Onboard Partner**
```bash
curl -X POST http://localhost:5000/partner/onboard \
  -H "X-Admin-Key: admin-demo-key" \
  -H "Content-Type: application/json" \
  -d '{"name":"DemoPartner","description":"Test Partner","format":"json"}'
```

2. **Upload Product Feed**
```bash
curl -X POST 'http://localhost:5000/partner/ingest?async=1' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <partner-key>' \
  --data '[{"sku":"sku-1","name":"Demo Product","price":9.99,"stock":10}]'
```

3. **Monitor Jobs**
```bash
curl -H "X-Admin-Key: admin-demo-key" http://localhost:5000/partner/jobs
```

---

## 🧪 Testing

### Run All Tests
```bash
# Local
pytest -v

# Docker
docker-compose exec web python -m pytest -v
```

### Test Categories
```bash
# Unit tests
pytest tests/unit_test.py -v

# Integration tests
pytest tests/test_integration_partner_ingest.py -v

# RMA tests
pytest tests/test_admin_auth.py -v
pytest tests/test_audit_entries.py -v

# Rate limiting
pytest tests/test_rate_limiting.py -v

# Concurrent operations
pytest tests/test_concurrent_checkout.py -v
```

---

## 📁 Project Structure

```
.
├── src/
│   ├── app.py                 # Main Flask application
│   ├── dao.py                 # Database access layer
│   ├── product_repo.py        # Product repository
│   ├── payment.py             # Payment processing
│   ├── observability.py       # Metrics and logging
│   │
│   ├── adapters/              # Partner feed adapters
│   │   ├── csv_adapter.py
│   │   ├── json_adapter.py
│   │   └── registry.py
│   │
│   ├── flash_sales/           # Flash sale features
│   │   ├── flash_sale_manager.py
│   │   ├── cache.py
│   │   ├── circuit_breaker.py
│   │   ├── rate_limiter.py
│   │   └── routes.py
│   │
│   ├── partners/              # Partner integration
│   │   ├── routes.py
│   │   ├── ingest_queue.py
│   │   ├── partner_ingest_service.py
│   │   ├── security.py
│   │   └── metrics.py
│   │
│   ├── rma/                   # Returns system (NEW)
│   │   ├── routes.py          # RMA endpoints
│   │   ├── manager.py         # Business logic
│   │   └── templates/         # RMA templates
│   │
│   └── templates/             # HTML templates
│
├── db/
│   ├── init.sql              # Database schema
│   ├── flash_sales.sql       # Flash sales tables
│   ├── partners.sql          # Partner tables
│   └── migrations/           # Database migrations
│
├── tests/                    # Test suite
├── docs/                     # Documentation
├── docker-compose.yml        # Docker configuration
├── Dockerfile               # Container image
├── requirements.txt         # Python dependencies
└── README.md               # This file
```

---

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_DB_PATH` | SQLite database path | `app.sqlite` |
| `APP_SECRET_KEY` | Flask session secret | `dev-insecure-secret` |
| `ADMIN_API_KEY` | Admin API key | `admin-demo-key` |
| `HASH_KEYS` | Hash API keys before storing | `false` |
| `ENABLE_FLASH_SALES` | Enable flash sale features | `true` |

### Database Schema

The application uses SQLite with the following main tables:
- `user` - User accounts
- `product` - Product catalog
- `sale` / `sale_item` - Orders
- `rma_requests` - Return requests
- `rma_items` - Items in returns
- `rma_activity_log` - Activity tracking
- `refunds` - Refund records
- `partner` / `partner_api_keys` - Partner management
- `partner_ingest_jobs` - Job queue

---

## 📎 Appendix: Partner (VAR) Catalog Ingest — Developer Guide

This appendix preserves the original developer-facing guidance for the partner ingest system.

### Key endpoints and UX notes
- GET /partner/contract — machine-readable contract (JSON)
- GET /partner/contract/example — example payload a partner can copy (JSON)
- GET /partner/help — quickstart and copyable curl examples (JSON)
- POST /partner/ingest — ingest endpoint (requires X-API-Key for partner auth)
- GET /partner/admin — admin UI; buttons disabled until session is confirmed
- POST /partner/admin/login — login (JSON or form); sets admin session cookie
- POST /partner/onboard_form — admin UI helper to onboard partner and return API key
- GET /partner/jobs — admin-only JSON jobs listing
- GET /partner/metrics — admin-only metrics dashboard (reads Prometheus registry)
- GET /partner/audit — admin-only audit viewer

Error responses are normalized to JSON:
```json
{ "error": "<Name>", "details": "<message>" }
```

### Demo commands (copy/paste)

1) Contract & example (pretty-print with jq)
```bash
curl -sS http://127.0.0.1:5000/partner/contract | jq .
curl -sS http://127.0.0.1:5000/partner/contract/example | jq .
```

2) Quickstart/help
```bash
curl -sS http://127.0.0.1:5000/partner/help | jq .
```

3) Show JSON error for missing API key
```bash
curl -i -sS -X POST http://127.0.0.1:5000/partner/ingest -H 'Content-Type: application/json' -d '[]'
```

4) Admin login + onboard (session-based)
```bash
# login and save cookie
curl -i -c cookies.txt -H "Content-Type: application/json" \
   -d '{"admin_key":"admin-demo-key"}' -X POST http://127.0.0.1:5000/partner/admin/login

# create partner using session cookie (returns the API key)
curl -i -b cookies.txt -H "Content-Type: application/json" \
   -d '{"name":"DemoPartner","description":"Demo","format":"json"}' \
   -X POST http://127.0.0.1:5000/partner/onboard_form
```

### Schema notes

This repository contains schema helpers under `db/`:
- `db/init.sql` — full application schema (products, partners, durable ingest jobs, schedules)
- `db/partners.sql` — lightweight subset documenting core partner tables (`partner`, `partner_api_keys`)

Initialize database with the full schema (equivalent to the app init):
```bash
sqlite3 app.sqlite < db/init.sql
# or run the app initialization helper
python -m src.main
```


## 🎯 Key Features in Detail

### RMA System Features

1. **Smart Order Detection**
   - Automatically hides "Request Return" for:
     - Orders with existing RMA requests
     - Replacement orders from previous returns
   - Shows "REPLACEMENT" badge for replacement orders

2. **Automated Workflows**
   - Auto-validation checks
   - Status transitions based on disposition type
   - Inventory adjustments
   - Activity logging

3. **Admin Tools**
   - Multiple queue views for different stages
   - Bulk operations
   - Search and filter
   - Metrics dashboard

Quick start (dev)

1) Setup a virtualenv and install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Initialize the database (idempotent)

```bash
# create schema
python -m src.main

# optional: seed demo data (users + products)
python -m src.seed
#seed for flash sale products
python -m db.seed_flash_sales
```

3) Start the Flask app (single-process dev)

```bash
# default: 127.0.0.1:5000
python -m src.app

# or with overridden env vars
APP_DB_PATH=$(pwd)/app.sqlite ADMIN_API_KEY=admin-demo-key APP_SECRET_KEY=dev-insecure-secret python -m src.app
```

4) Start the background worker in a second terminal

```bash
APP_DB_PATH=$(pwd)/app.sqlite python -c "import sys, pathlib; sys.path.insert(0, str(pathlib.Path('.').resolve())); from src.partners.ingest_queue import start_worker; from pathlib import Path; start_worker(str(Path('.').resolve()/ 'app.sqlite'))"
```

Important environment variables
- `APP_DB_PATH` — path to SQLite DB file (default: `app.sqlite` in repo)
- `ADMIN_API_KEY` — demo admin key (default: `admin-demo-key`)
- `APP_SECRET_KEY` — Flask session secret (set to a strong value in non-dev)
- `HASH_KEYS` — set to `true` to hash API keys before storing (default: `false`)

Key endpoints and UX notes
- `GET /partner/contract` — machine-readable contract (JSON)
- `GET /partner/contract/example` — example payload a partner can copy (JSON)
- `GET /partner/help` — quickstart and copyable curl examples (JSON)
- `POST /partner/ingest` — ingest endpoint (requires `X-API-Key` for partner auth)
- `GET /partner/admin` — admin UI; buttons disabled until session is confirmed
- `POST /partner/admin/login` — login (JSON or form); sets admin session cookie
- `POST /partner/onboard_form` — admin UI helper to onboard partner and return API key
- `GET /partner/jobs` — admin-only JSON jobs listing
- `GET /partner/metrics` — admin-only metrics dashboard (reads Prometheus registry)
- `GET /partner/audit` — admin-only audit viewer

Error responses
- API errors are normalized to JSON: `{ "error": "<Name>", "details": "<message>" }`.
   This makes it simple for partner automation to parse and react to failures.

Demo commands (copy/paste)

1) Contract & example (pretty-print with `jq`)

```bash
curl -sS http://127.0.0.1:5000/partner/contract | jq .
curl -sS http://127.0.0.1:5000/partner/contract/example | jq .
```

2) Quickstart/help

```bash
curl -sS http://127.0.0.1:5000/partner/help | jq .
```

3) Show JSON error for missing API key

```bash
curl -i -sS -X POST http://127.0.0.1:5000/partner/ingest -H 'Content-Type: application/json' -d '[]'
```

4) Admin login + onboard (session-based)

```bash
# login and save cookie
curl -i -c cookies.txt -H "Content-Type: application/json" \
   -d '{"admin_key":"admin-demo-key"}' -X POST http://127.0.0.1:5000/partner/admin/login

# create partner using session cookie (returns the API key)
curl -i -b cookies.txt -H "Content-Type: application/json" \
   -d '{"name":"DemoPartner","description":"Demo","format":"json"}' \
   -X POST http://127.0.0.1:5000/partner/onboard_form
```

Running tests

```bash
pytest -q
```

Notes and security guidance
- The demo `ADMIN_API_KEY` is `admin-demo-key` unless you override it. Do not commit real secrets.
- In production:
   - Use a secure `APP_SECRET_KEY` and rotate admin keys.
   - Replace SQLite + in-process worker with a durable queue (Redis, RabbitMQ, Cloud Tasks).
   - Harden cookies (SameSite, Secure) and add CSRF protections for forms.

Further reading
- ADR: `docs/ADR/0013-usability.md` — describes contract, example, quickstart and normalized errors.

Maintainers
- Pragya Chapagain
- Yanlin Wu

```
