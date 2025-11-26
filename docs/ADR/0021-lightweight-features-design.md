# ADR 0021: Lightweight Features Design (Order Filtering, Low Stock Alerts, RMA Notifications)

**Status**: Accepted  
**Date**: 2025-11-27  
**Decision Makers**: Development Team  
**Related ADRs**: ADR-0020 (RMA System Design), ADR-0019 (Observability Implementation)

---

## Context

Checkpoint 4 requires three lightweight enhancements to improve user experience and operational efficiency:

1. **Order History Filtering & Search** - Help customers find specific orders quickly
2. **Low Stock Alerts** - Notify admins when inventory falls below threshold
3. **RMA Notifications** - Alert customers about return status changes

### Business Requirements

**Order Filtering & Search:**
- Filter by order status (Completed, Pending, Returned, Refunded)
- Date range filtering for temporal searches
- Keyword search by product name or order ID
- Fast, responsive UI without pagination complexity

**Low Stock Alerts:**
- Configurable threshold (default: 5 units)
- Display on admin dashboard
- Real-time accuracy
- No external notification services needed

**RMA Notifications:**
- Alert customers on RMA status changes
- Display RMA disposition outcomes (Repair, Refund, etc.)
- Lightweight UI (no email/SMS required)
- Auto-refresh for real-time updates

### Constraints

- Minimal complexity (lightweight features)
- No external dependencies (no email/SMS services)
- Fast implementation (<1 day per feature)
- SQLite database constraints (single-file, no complex queries)
- Existing tech stack only (Flask, SQLite, Jinja2, vanilla JS)

---

## Decision

### 1. Order History Filtering & Search

**Architecture:** Server-side dynamic SQL query building with GET parameters

**Implementation:**
- **Backend**: Modify `/dashboard` route to accept filter parameters (`status`, `start_date`, `end_date`, `search`)
- **SQL Strategy**: Build dynamic WHERE clauses based on provided filters
- **Frontend**: HTML form with dropdowns and date inputs submitting via GET
- **No Pagination**: Display all filtered results (sufficient for typical user order volumes)

**Key Design Choices:**

```python
# Dynamic SQL building (secure with parameterized queries)
query = "SELECT ... FROM sale WHERE user_id = ?"
params = [user_id]

if status_filter:
    query += " AND s.status = ?"
    params.append(status_filter)

if start_date:
    query += " AND DATE(s.sale_time) >= ?"
    params.append(start_date)
```

**Rationale:**
- ✅ Simple GET-based filtering (bookmarkable URLs)
- ✅ No JavaScript framework needed
- ✅ Works with existing template system
- ✅ Parameterized queries prevent SQL injection
- ✅ Fast for small-medium datasets (< 10k orders per user)

**Trade-offs:**
- ❌ No client-side filtering (full page reload)
- ❌ No advanced search (exact matches only)
- ✅ Acceptable for lightweight requirement

---

### 2. Low Stock Alerts

**Architecture:** Environment variable configuration + database query + admin dashboard display

**Implementation:**
- **Configuration**: `LOW_STOCK_THRESHOLD` environment variable (default: 5)
  ```yaml
  # docker-compose.yml
  environment:
    - LOW_STOCK_THRESHOLD=${LOW_STOCK_THRESHOLD:-5}
  ```
- **Backend**: New method `AProductRepo.get_low_stock_products(threshold)`
  ```sql
  SELECT id, name, stock 
  FROM product 
  WHERE active=1 AND stock <= ? 
  ORDER BY stock ASC
  ```
- **Frontend**: Display in admin dashboard with red styling
- **API Endpoint**: `/api/low-stock` for programmatic access (optional)

**Key Design Choices:**

1. **Configuration Method**: Environment variable with constant fallback
   - Rationale: Matches 12-factor app principles, easy to change per environment
   - Alternative considered: Database table (rejected: overkill for single value)

2. **Display Location**: Admin dashboard only
   - Rationale: Inventory management is admin concern, not customer-facing

3. **No Notifications**: Display-only (no email/SMS)
   - Rationale: Lightweight requirement, admin checks dashboard regularly

4. **Query Override**: URL parameter `?low_stock_threshold=N` for ad-hoc testing
   - Rationale: Debugging convenience without changing environment

**Trade-offs:**
- ✅ Zero external dependencies
- ✅ Real-time accuracy (queries live data)
- ✅ Simple to configure
- ❌ No proactive alerts (admin must check dashboard)
- ✅ Acceptable for lightweight requirement

---

### 3. RMA Notifications

**Architecture:** Database-backed notification system with polling-based UI updates

**Implementation:**

**Database Schema:**
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    rma_id INTEGER,
    rma_number TEXT,
    is_read INTEGER DEFAULT 0,
    read_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

**Backend Components:**
1. **NotificationService** (new module `src/notifications.py`)
   - `create_rma_status_notification()`: Creates notification with disposition-aware messaging
   - `get_user_notifications()`: Retrieves user's notifications
   - `get_unread_count()`: Count for badge display
   - `mark_as_read()`: Mark notification as read

2. **Integration Point**: `RMAManager._log_activity()`
   - Automatically creates notification on status change
   - Passes disposition info for context-aware messages
   - Notify statuses: SUBMITTED, APPROVED, REJECTED, RECEIVED, INSPECTING, INSPECTED, DISPOSITION, PROCESSING, COMPLETED, CANCELLED

**Frontend Components:**
1. **Notification Badge** (in nav bar)
   ```javascript
   // Auto-poll every 30 seconds
   async function updateNotificationBadge() {
       const response = await fetch('/api/notifications/count');
       const data = await response.json();
       badge.textContent = data.count || '';
   }
   setInterval(updateNotificationBadge, 30000);
   ```

2. **Notification Center** (`/notifications` page)
   - List view with mark-as-read buttons
   - Links to RMA details
   - Timestamp display

**Key Design Choices:**

1. **Storage**: Database table (not in-memory cache)
   - Rationale: Persistence across restarts, full audit trail
   - Alternative: Redis (rejected: adds external dependency)

2. **Delivery**: Pull-based polling (not push WebSockets)
   - Rationale: Simple, no WebSocket infrastructure, 30s latency acceptable
   - Alternative: WebSockets (rejected: overkill for low-frequency updates)

3. **Disposition-Aware Messages**: Different messages per disposition type
   ```python
   if disposition == 'REPAIR':
       title = "Repair Approved"
       message = "Your item will be repaired..."
   elif disposition == 'REFUND':
       title = "Refund Approved"
       message = "Your refund is being processed..."
   ```
   - Rationale: Better UX, clear communication of outcome

4. **Integration**: Automatic via `_log_activity()` (not manual calls)
   - Rationale: Single source of truth, can't forget to notify
   - Ensures every status change triggers notification

**Trade-offs:**
- ✅ No external services (email/SMS)
- ✅ Full persistence and audit trail
- ✅ Works offline (no external API dependencies)
- ❌ 30-second polling delay (not real-time)
- ✅ Acceptable for lightweight requirement
- ❌ Polling adds minor server load (mitigated by efficient query)

---

## Consequences

### Positive

**Order Filtering:**
- ✅ Improved customer self-service (find orders faster)
- ✅ Reduced support burden (fewer "where's my order?" tickets)
- ✅ Simple implementation (1-file change: `app.py` + template)
- ✅ SEO-friendly URLs (GET parameters)

**Low Stock Alerts:**
- ✅ Proactive inventory management
- ✅ Prevents stockouts
- ✅ Environment-specific configuration (dev/staging/prod)
- ✅ Zero runtime overhead (query on-demand)

**RMA Notifications:**
- ✅ Better customer experience (proactive status updates)
- ✅ Reduced "what's the status?" support tickets
- ✅ Complete audit trail of customer communications
- ✅ Disposition-aware messaging improves clarity
- ✅ Real-time badge updates enhance engagement

### Negative

**Order Filtering:**
- ❌ Full page reload on filter change (acceptable for simplicity)
- ❌ No advanced search operators (e.g., fuzzy matching)

**Low Stock Alerts:**
- ❌ Admin must check dashboard (no proactive alerts)
- ❌ Single global threshold (not per-product)

**RMA Notifications:**
- ❌ 30-second polling delay (not instant)
- ❌ Polling adds minor server load (~0.5 req/min per active user)
- ❌ No mobile push notifications

### Mitigation Strategies

1. **Polling Load**: Efficient query with indexes on `user_id` and `is_read`
2. **Threshold Flexibility**: URL override parameter for testing different values
3. **Future Enhancement**: Easy to add email/SMS later (NotificationService abstraction)

---

## Alternatives Considered

### Order Filtering

**Alternative 1: Client-side filtering with JavaScript**
- Pros: No page reload, instant results
- Cons: Requires loading all data upfront, memory intensive
- Rejected: Breaks with large datasets, complexity not justified

**Alternative 2: ElasticSearch integration**
- Pros: Advanced search, faceting, fuzzy matching
- Cons: External dependency, operational complexity
- Rejected: Overkill for lightweight requirement

### Low Stock Alerts

**Alternative 1: Email notifications via SendGrid/SES**
- Pros: Proactive alerts, no need to check dashboard
- Cons: External service dependency, configuration overhead
- Rejected: Violates lightweight constraint

**Alternative 2: Per-product thresholds in database**
- Pros: Fine-grained control
- Cons: Added UI complexity, migration overhead
- Rejected: Not needed for initial implementation

### RMA Notifications

**Alternative 1: WebSocket real-time push**
- Pros: Instant updates (<1s latency)
- Cons: WebSocket infrastructure, connection management, scalability concerns
- Rejected: Complexity not justified for low-frequency events

**Alternative 2: Email/SMS notifications**
- Pros: Customer receives alerts outside app
- Cons: External service (SendGrid/Twilio), cost, deliverability issues
- Rejected: Violates "no external services" requirement

**Alternative 3: Server-Sent Events (SSE)**
- Pros: Simpler than WebSockets, unidirectional
- Cons: Still requires persistent connections, browser compatibility
- Rejected: Polling is simpler and sufficient

---

## Implementation Summary

### Files Created/Modified

**New Files:**
- `src/notifications.py` - NotificationService class
- `src/templates/notifications.html` - Notification center UI
- `migrations/0004_add_notifications.sql` - Database schema
- `tests/test_low_stock_alerts.py` - Low stock test coverage

**Modified Files:**
- `src/app.py` - Added filtering logic, notification routes, low stock display
- `src/rma/manager.py` - Integrated NotificationService
- `src/product_repo.py` - Added `get_low_stock_products()`
- `src/templates/dashboard.html` - Filter UI, notification badge with polling
- `src/templates/admin_home.html` - Low stock alerts display
- `docker-compose.yml` - Added `LOW_STOCK_THRESHOLD` environment variable

### Database Changes

**New Table:**
```sql
notifications (id, user_id, type, title, message, rma_id, rma_number, is_read, read_at, created_at)
```

**Indexes:**
```sql
idx_notifications_user_id
idx_notifications_is_read
idx_notifications_created_at
idx_notifications_user_unread (composite)
```

### API Endpoints

**New:**
- `GET /dashboard?status=X&start_date=Y&end_date=Z&search=Q` - Filtered orders
- `GET /admin?low_stock_threshold=N` - Admin dashboard with low stock alerts
- `GET /api/low-stock` - JSON endpoint for low stock products
- `GET /notifications` - Notification center page
- `POST /notifications/mark-read/<id>` - Mark single notification as read
- `POST /notifications/mark-all-read` - Mark all as read
- `GET /api/notifications/count` - Unread count for badge

---

## Testing Strategy

### Order Filtering
- Unit tests: SQL query building with different filter combinations
- Integration tests: End-to-end filter application
- Manual testing: Various filter combinations, empty results

### Low Stock Alerts
- Unit tests: `get_low_stock_products()` with various thresholds
- Environment tests: Verify `LOW_STOCK_THRESHOLD` override works
- Edge cases: Zero stock, exactly at threshold, inactive products

### RMA Notifications
- Unit tests: Notification creation with different dispositions
- Integration tests: RMA workflow triggers notifications
- UI tests: Badge update polling, mark-as-read functionality
- Disposition tests: Verify correct messages for each disposition type

---

## Monitoring & Observability

**Metrics to Track:**
- Order filter usage (which filters most popular?)
- Low stock alert frequency (how often products fall below threshold?)
- Notification open rates (how many users view notifications?)
- Notification response time (polling endpoint performance)

**Logs:**
- Low stock query performance
- Notification creation events (RMA status changes)
- Filter query execution times

---

## Future Enhancements

### Order Filtering (Priority: Low)
- Client-side filtering for instant results
- Advanced search operators (fuzzy match, regex)
- Saved filter presets
- Export filtered results to CSV

### Low Stock Alerts (Priority: Medium)
- Per-product threshold overrides
- Email notifications for critical stock levels
- Stock trend predictions (ML-based)
- Reorder suggestions

### RMA Notifications (Priority: High)
- Email/SMS integration (opt-in)
- Browser push notifications (Progressive Web App)
- Reduce polling interval (15s or WebSocket upgrade)
- Notification preferences (which statuses to notify)
- Mobile app integration

---

## Conclusion

These three lightweight features significantly enhance user experience and operational efficiency with minimal complexity. The design prioritizes:

1. **Simplicity**: No external dependencies, standard Flask patterns
2. **Maintainability**: Clear separation of concerns, well-documented code
3. **Performance**: Efficient queries with proper indexing
4. **Extensibility**: Easy to enhance later (e.g., add email notifications)

The trade-off of "good enough" implementations (polling vs. WebSocket, single threshold vs. per-product) is justified by the lightweight requirement and rapid implementation timeline.

**Total Implementation Time**: ~6 hours (2 hours per feature)  
**Lines of Code Added**: ~800 lines (including tests)  
**External Dependencies Added**: 0  
**Database Tables Added**: 1 (notifications)

---

## References

- ADR-0020: RMA System Design
- ADR-0019: Observability Implementation
- [12-Factor App: Config](https://12factor.net/config)
- [Flask Request Context](https://flask.palletsprojects.com/en/3.0.x/reqcontext/)
- [SQLite Query Optimization](https://www.sqlite.org/queryplanner.html)
