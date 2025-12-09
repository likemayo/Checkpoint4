# How to Demonstrate Observability on the Monitoring Dashboard

## Quick Start

### Access the Monitoring Dashboard

1. **Login as Admin** (if not already)
   - Navigate to `http://localhost:5000/login`
   - Use admin credentials (or select "Admin" role)

2. **From Admin Dashboard**
   - Click "Admin Dashboard" in the top navigation
   - Scroll down to **System Monitoring** section
   - Click **"📊 Monitoring Dashboard"** card

OR directly visit: `http://localhost:5000/monitoring/dashboard`

---

## What the Dashboard Shows

### 1. **Orders Metrics** 📦
- **Total Orders**: Cumulative count of all checkout transactions
- **Successful Orders**: Orders with COMPLETED or REFUNDED status
- **Failed Orders**: Orders that failed during checkout
- **Orders/min**: Real-time throughput rate

**How to generate data:**
1. Login as a customer
2. Browse `/products`
3. Add items to cart
4. Complete checkout
5. Watch the metrics update on the dashboard (refresh every 5 seconds)

---

### 2. **Refunds/Returns Metrics** 💰
- **Total Refunds**: Total RMA (Return Merchandise Authorization) requests
- **Approved Refunds**: RMAs with REFUND/REPLACEMENT/REPAIR/CREDIT disposition
- **Rejected Refunds**: RMAs with REJECT disposition
- **Pending Refunds**: RMAs currently being processed
- **Refunds/day**: Rate metric showing refunds per day

**How to generate data:**
1. Login as customer
2. Go to **Dashboard** → **My Orders**
3. Click on an order → **Request Return**
4. Fill in RMA details and submit
5. Login as admin
6. Go to **RMA Admin Dashboard**
7. Process the RMA through the workflow (Warehouse → Inspection → Disposition → Processing)
8. Watch the refund metrics update

---

### 3. **Error Metrics** ⚠️
- **Total Errors**: All HTTP errors and system failures
- **4xx Client Errors**: Bad requests, auth failures (400, 404, 401, etc.)
- **5xx Server Errors**: Internal server errors, database issues
- **Errors/min**: Error rate per minute

**How to generate errors:**
1. Try accessing an invalid URL like `/invalid-page` (generates 404)
2. Try accessing `/admin` without logging in as admin (generates 401)
3. Attempt to exceed rate limits on partner API endpoints
4. Watch errors appear on dashboard

---

### 4. **Performance Metrics** ⚡
- **Avg Response Time**: Average HTTP request latency in milliseconds
- **P95 Response Time**: 95th percentile (95% of requests are faster than this)
- **P99 Response Time**: 99th percentile (slowest 1% of requests)

**How to generate performance data:**
1. Load-test by visiting pages repeatedly
2. Checkout multiple times
3. Check performance percentiles showing how fast the system responds

---

### 5. **System Status** 🟢
- **Status Badge**: Shows "Healthy" or "Degraded"
- **Uptime**: How long the application has been running

---

## Structured Logging Example

Every request is logged with structured JSON containing:
- **Request ID** - Unique identifier for tracing
- **Timestamp** - ISO format timestamp
- **Level** - INFO, WARNING, ERROR
- **Message** - Human-readable description
- **Context** - Additional structured data (user_id, status_code, etc.)

### View Logs in Two Ways:

#### 1. **Dashboard (Real-time)**
- Scroll to **"📋 Recent Logs"** section
- Shows last 20 logs with color-coded levels
- Auto-updates every 5 seconds

#### 2. **Terminal/Docker Logs**
```bash
# View web service logs
docker-compose logs -f web

# Filter for errors only
docker-compose logs web | grep ERROR

# View specific request
docker-compose logs web | grep "REQUEST_ID_HERE"
```

Example log output:
```json
{"timestamp": "2025-12-09T14:35:42.123456Z", "level": "INFO", "message": "User logged in", "request_id": "abc123", "context": {"user_id": 1, "username": "john"}}
{"timestamp": "2025-12-09T14:36:15.456789Z", "level": "INFO", "message": "Checkout completed", "request_id": "def456", "context": {"user_id": 1, "order_id": 42, "total_cents": 5999}}
```

---

## Complete Demonstration Workflow

### Step 1: Generate Orders
```
1. Open browser tab 1: http://localhost:5000/products
2. Login as customer "john"
3. Add 3 products to cart
4. Checkout
5. Repeat 2-3 more times with different products
```

### Step 2: Generate Refunds/Returns
```
1. Go to Dashboard → My Orders
2. Click "Request Return" on an order
3. Fill RMA form and submit
4. Open browser tab 2: Login as admin
5. Go to RMA Admin Dashboard
6. Process RMA through workflow:
   - Move from Warehouse queue to Inspection
   - Review item condition
   - Mark disposition (Refund/Repair/etc.)
   - Mark as processed
7. Refund metrics update on monitoring dashboard
```

### Step 3: Monitor in Real-time
```
1. Open browser tab 3: http://localhost:5000/monitoring/dashboard
2. Watch metrics update every 5 seconds as you:
   - Checkout (Orders metrics increase)
   - Process RMAs (Refund metrics update)
   - View logs (Recent Logs section)
3. Check performance percentiles
4. Verify system status shows "Healthy"
```

### Step 4: Generate Errors (Optional)
```
1. Try visiting http://localhost:5000/invalid-url (404 error)
2. Try /admin without admin login (401 error)
3. Watch error counters increase on dashboard
4. See error logs in Recent Logs section with level="ERROR"
```

---

## Key Metrics to Highlight

| Metric | What It Means | Why It Matters |
|--------|---------------|----------------|
| **Orders/min** | How many customers are checking out | Customer engagement |
| **Success Rate** | % of orders completed successfully | System reliability |
| **Approved Refunds** | RMAs approved for refund/replacement | Customer satisfaction |
| **Avg Response Time** | How fast pages load | User experience |
| **P95 Latency** | Performance for typical users | SLA compliance |
| **Error Rate** | How many requests fail | System health |
| **Uptime** | How long without restart | Reliability |

---

## Advanced: View Raw Metrics API

All metrics are available via JSON API endpoints:

```bash
# Get all metrics
curl http://localhost:5000/monitoring/api/metrics

# Get order metrics
curl http://localhost:5000/monitoring/api/metrics/orders

# Get refund metrics
curl http://localhost:5000/monitoring/api/metrics/refunds

# Get error metrics
curl http://localhost:5000/monitoring/api/metrics/errors

# Get performance metrics
curl http://localhost:5000/monitoring/api/metrics/performance

# Get system health
curl http://localhost:5000/monitoring/api/health

# Get recent logs
curl http://localhost:5000/monitoring/api/logs/recent
```

---

## Addressing Requirements

This implementation demonstrates all three observability requirements:

### ✅ **Structured Logging**
- Every request logged with unique request ID
- Timestamp, level (INFO/WARNING/ERROR), and structured context
- Searchable by request ID or timestamp
- Visible in dashboard Recent Logs section

### ✅ **Basic Metrics**
- Orders/day tracking
- Error rate monitoring
- Refund/return tracking
- Performance percentiles (P95, P99)
- Real-time throughput rates

### ✅ **Dashboard for System Admin**
- Clean, real-time monitoring interface
- Auto-refreshes every 5 seconds
- Shows business metrics (orders, refunds)
- Shows technical metrics (errors, latency)
- Accessible from Admin Dashboard
- Color-coded status indicators
- Recent logs with level indicators
