# ADR 0020: RMA (Returns & Refunds) System Design

**Status**: Accepted  
**Date**: 2025-11-12  
**Decision Makers**: Development Team, Support Team  
**Related ADRs**: ADR-0001 (Database Choice), ADR-0006 (Admin Access Control)

---

## Context

The Checkpoint3 retail system needs a comprehensive Returns Merchandise Authorization (RMA) system to handle customer returns and refunds. This is a critical business process that impacts:
- Customer satisfaction and retention
- Inventory management
- Financial operations
- Operational efficiency
- Compliance and audit requirements

### Business Requirements

1. **Customer Needs**
   - Easy return request submission
   - Track return status in real-time
   - Multiple return reasons supported
   - Photo upload for evidence
   - Clear communication throughout process

2. **Operational Needs**
   - Multi-stage workflow with clear responsibilities
   - Validation and approval process
   - Warehouse inspection and disposition
   - Multiple disposition types (refund, replacement, repair, reject, store credit)
   - Audit trail for compliance

3. **System Requirements**
   - Integration with existing order system
   - Inventory synchronization
   - Financial transaction recording
   - User notifications
   - Admin dashboards and reporting

### Challenges

- Complex multi-stakeholder process (customer, support, warehouse, finance)
- Need for clear status tracking
- Flexible disposition handling
- Data consistency across operations
- Auditability for compliance
- User experience considerations

---

## Decision

We will implement a **10-stage workflow-based RMA system** with **5 disposition types** and **role-based admin queues**.

### Architecture Overview

```
┌────────────────────────────────────────────────────────────┐
│                    RMA System Architecture                  │
└────────────────────────────────────────────────────────────┘

┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Customer   │      │    Admin     │      │   Database   │
│   Interface  │◄────►│   Queues     │◄────►│   (SQLite)   │
└──────────────┘      └──────────────┘      └──────────────┘
       │                      │                      │
       └──────────────────────┼──────────────────────┘
                              ▼
                   ┌──────────────────┐
                   │   RMA Manager    │
                   │  (Workflow Engine)│
                   └──────────────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │  Validation  │  │ Disposition  │  │  Inventory   │
    │   Service    │  │   Handlers   │  │   Manager    │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## 10-Stage Workflow

### Stage Flow

```
1. SUBMITTED     → Customer initiates return request
       ↓
2. VALIDATING    → System validates request rules
       ↓
3. APPROVED      → Support team reviews and approves
       ↓
4. SHIPPING      → Customer receives label and ships item
       ↓
5. RECEIVED      → Warehouse receives returned item
       ↓
6. INSPECTING    → Warehouse inspects condition
       ↓
7. INSPECTED     → Inspection complete, results recorded
       ↓
8. DISPOSITION   → Decision made (refund/replace/repair/reject/credit)
       ↓
9. PROCESSING    → Executing disposition action
       ↓
10. COMPLETED    → RMA closed, outcome delivered
```

### Stage Details

| Stage | Status | Actor | Actions | Next Stage |
|-------|--------|-------|---------|------------|
| 1 | SUBMITTED | Customer | Submit form, upload photos | VALIDATING |
| 2 | VALIDATING | System | Check timing, items, quantities | APPROVED/REJECTED |
| 3 | APPROVED | Support Team | Review and approve | SHIPPING |
| 4 | SHIPPING | Customer | Print label, ship item | RECEIVED |
| 5 | RECEIVED | Warehouse | Scan tracking, confirm receipt | INSPECTING |
| 6 | INSPECTING | Warehouse | Physical inspection | INSPECTED |
| 7 | INSPECTED | Warehouse | Record inspection results | DISPOSITION |
| 8 | DISPOSITION | Warranty Team | Decide outcome | PROCESSING |
| 9 | PROCESSING | Finance/Fulfillment | Execute disposition | COMPLETED |
| 10 | COMPLETED | System | Close RMA, notify customer | END |

---

## 5 Disposition Types

### 1. REFUND
**Description**: Full or partial refund to customer

**Process**:
- Finance team processes refund
- Inventory restored to available stock
- Refund record created with payment details
- Customer notified

**Inventory Impact**: +quantity (item returned to stock)

**Example Use Cases**:
- Defective product
- Wrong item shipped
- Customer changed mind (within policy)

### 2. REPLACEMENT
**Description**: Send new item to customer

**Process**:
- Fulfillment team creates replacement order
- New item shipped to customer
- Original item may be repaired or scrapped
- Inventory adjusted accordingly

**Inventory Impact**: -quantity (new item), +quantity (returned item if repairable)

**Example Use Cases**:
- Defective item under warranty
- Damaged during shipping
- Manufacturing defect

### 3. REPAIR
**Description**: Fix and return original item

**Process**:
- Repair team initiates repair
- Inventory marked as "in repair" (unavailable)
- Repair completed
- Item returned to customer
- Inventory status updated

**Inventory Impact**: Temporary unavailable, then restored

**Example Use Cases**:
- Repairable defect
- Warranty coverage for repair
- High-value item worth fixing

### 4. REJECT
**Description**: Deny return request

**Process**:
- Rejection decision made
- Customer notified with reason
- No refund issued
- Customer keeps item
- RMA closed

**Inventory Impact**: None (customer keeps item)

**Example Use Cases**:
- Outside return window
- Customer misuse/damage
- Item doesn't match policy
- Inspection fails criteria

### 5. STORE_CREDIT
**Description**: Issue store credit instead of refund

**Process**:
- Finance team calculates credit amount
- Credit added to customer account
- Inventory restored
- Customer can use credit for future purchases

**Inventory Impact**: +quantity (item returned to stock)

**Example Use Cases**:
- Customer prefers credit
- Promotional return policy
- Incentive for retention

---

## Database Schema

### Core Tables

```sql
-- Main RMA requests table
CREATE TABLE rma_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rma_number TEXT UNIQUE NOT NULL,
    sale_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN (
        'SUBMITTED', 'VALIDATING', 'APPROVED', 'REJECTED', 
        'SHIPPING', 'RECEIVED', 'INSPECTING', 'INSPECTED', 
        'DISPOSITION', 'PROCESSING', 'COMPLETED', 'CANCELLED'
    )),
    reason TEXT,
    description TEXT,
    photo_path TEXT,
    
    -- Workflow timestamps
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    approved_by TEXT,
    rejected_at TIMESTAMP,
    rejection_reason TEXT,
    
    -- Shipping
    shipping_label_url TEXT,
    shipped_at TIMESTAMP,
    tracking_number TEXT,
    received_at TIMESTAMP,
    received_by TEXT,
    
    -- Inspection
    inspection_started_at TIMESTAMP,
    inspected_at TIMESTAMP,
    inspected_by TEXT,
    inspection_result TEXT,
    inspection_notes TEXT,
    
    -- Disposition
    disposition TEXT CHECK(disposition IN (
        'REFUND', 'REPLACEMENT', 'REPAIR', 'REJECT', 'STORE_CREDIT'
    )),
    disposition_reason TEXT,
    disposition_at TIMESTAMP,
    disposition_by TEXT,
    refund_amount_cents INTEGER,
    
    -- Closure
    closed_at TIMESTAMP,
    
    FOREIGN KEY (sale_id) REFERENCES sale(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);

-- RMA line items
CREATE TABLE rma_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rma_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    reason TEXT,
    FOREIGN KEY (rma_id) REFERENCES rma_requests(id),
    FOREIGN KEY (product_id) REFERENCES product(id)
);

-- Refund records
CREATE TABLE refunds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rma_id INTEGER NOT NULL,
    amount_cents INTEGER NOT NULL,
    method TEXT NOT NULL,
    status TEXT NOT NULL,
    reference TEXT,
    processed_at TIMESTAMP,
    processed_by TEXT,
    FOREIGN KEY (rma_id) REFERENCES rma_requests(id)
);

-- Activity log for audit trail
CREATE TABLE rma_activities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rma_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    from_status TEXT,
    to_status TEXT,
    actor TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (rma_id) REFERENCES rma_requests(id)
);

-- Notifications
CREATE TABLE rma_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rma_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP,
    FOREIGN KEY (rma_id) REFERENCES rma_requests(id),
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

---

## Component Design

### RMA Manager (Workflow Engine)

**Location**: `src/rma/manager.py`

**Responsibilities**:
- Enforce workflow state transitions
- Validate business rules
- Execute disposition logic
- Manage inventory updates
- Log all activities
- Send notifications

**Key Methods**:
```python
class RMAManager:
    def create_rma(self, sale_id, user_id, items, reason, description, photo_path)
    def validate_rma(self, rma_id)
    def approve_rma(self, rma_id, actor)
    def generate_shipping_label(self, rma_id)
    def mark_received(self, rma_id, actor)
    def start_inspection(self, rma_id, actor)
    def complete_inspection(self, rma_id, result, notes, actor)
    def make_disposition(self, rma_id, disposition, reason, decided_by)
    def process_refund(self, rma_id, actor)
    def process_replacement(self, rma_id, actor)
    def process_repair(self, rma_id, actor)
    def process_rejection(self, rma_id, actor, notes)
    def process_store_credit(self, rma_id, amount_cents, actor)
    def complete_repair(self, rma_id, actor, notes)
```

### Admin Queues

**Purpose**: Organize RMAs by stage for different teams

**Queues**:

1. **Validation Queue** (`/rma/admin/validation-queue`)
   - Shows: SUBMITTED RMAs
   - For: Support Team
   - Actions: Approve/Reject

2. **Warehouse Queue** (`/rma/admin/warehouse-queue`)
   - Shows: RECEIVED RMAs
   - For: Warehouse Team
   - Actions: Start Inspection

3. **Inspection Queue** (`/rma/admin/inspection-queue`)
   - Shows: INSPECTING RMAs
   - For: Warehouse Team
   - Actions: Complete Inspection

4. **Disposition Queue** (`/rma/admin/disposition-queue`)
   - Shows: INSPECTED RMAs
   - For: Warranty Team
   - Actions: Make Disposition Decision

5. **Processing Queue** (`/rma/admin/processing-queue`)
   - Shows: DISPOSITION/PROCESSING RMAs
   - For: Finance/Fulfillment Teams
   - Actions: Process Refund, Replacement, Repair, Rejection, Store Credit

6. **Completed Queue** (`/rma/admin/completed`)
   - Shows: COMPLETED RMAs
   - For: All Teams (reporting)
   - Actions: View details, download reports

---

## Business Rules

### Return Eligibility

```python
# Timing rules
MAX_DAYS_AFTER_DELIVERY = 30

# Item conditions
VALID_REASONS = [
    "Defective", "Wrong item", "Not as described",
    "Changed mind", "Damaged in shipping"
]

# Quantity rules
- Cannot return more than purchased
- Cannot return already refunded items
- Cannot return gift cards or digital items
```

### Disposition Logic

```python
def determine_suggested_disposition(inspection_result, reason):
    if inspection_result == "DEFECTIVE":
        if high_value_item:
            return "REPAIR"
        return "REPLACEMENT" or "REFUND"
    
    if inspection_result == "CUSTOMER_DAMAGE":
        return "REJECT"
    
    if inspection_result == "ACCEPTABLE":
        if reason == "Changed mind":
            return "REFUND" or "STORE_CREDIT"
        return "REFUND"
    
    return "REJECT"
```

### Inventory Management

```python
def adjust_inventory(disposition, items):
    if disposition in ["REFUND", "STORE_CREDIT"]:
        # Restore to available stock
        for item in items:
            product.stock += item.quantity
    
    elif disposition == "REPAIR":
        # Mark as unavailable during repair
        for item in items:
            product.stock -= item.quantity  # Temporarily
        # Restore after repair complete
    
    elif disposition == "REPLACEMENT":
        # Deduct new item, restore returned if repairable
        # Complex logic based on item condition
    
    elif disposition == "REJECT":
        # No change (customer keeps item)
        pass
```

---

## User Interface

### Customer Views

1. **My Returns** (`/rma/my-returns`)
   - List all customer's RMAs
   - Status badges with colors
   - Click to view details

2. **Submit Return** (`/rma/submit`)
   - Select order from history
   - Choose items and quantities
   - Upload photos (optional)
   - Describe issue
   - Submit request

3. **RMA Details** (`/rma/view/<id>`)
   - Full RMA information
   - Current status
   - Timeline of activities
   - Documents (shipping label, receipts)
   - Refund/credit information

### Admin Views

1. **RMA Dashboard** (`/rma/admin/dashboard`)
   - Summary statistics
   - Quick access to all queues
   - Metrics and charts

2. **Queue Views** (Multiple routes)
   - Tabular list of RMAs
   - Filters and search
   - Action buttons

3. **Processing Forms**
   - Inspection form
   - Disposition decision form
   - Refund processing form
   - Replacement form
   - Repair tracking form
   - Rejection form
   - Store credit form

---

## Quality Attributes

### Auditability

**Implementation**:
- All state changes logged in `rma_activities`
- Includes: actor, timestamp, before/after status, notes
- Immutable log (insert-only)
- Activity timeline displayed to admins

**Benefits**:
- Compliance with regulations
- Dispute resolution
- Process analysis
- Performance tracking

### Reliability

**Implementation**:
- Multi-stage validation
- Status checks before transitions
- Database constraints
- Transaction management
- Error handling and rollback

**Benefits**:
- Data consistency
- No lost returns
- Clear error messages
- Recoverable from failures

### Usability

**Implementation**:
- Clear step-by-step process
- Visual status indicators
- Color-coded badges
- Contextual help text
- Responsive design

**Benefits**:
- Easy for customers to use
- Reduced support burden
- Faster admin processing
- Lower error rates

### Performance

**Implementation**:
- Indexed database queries
- Efficient SQL joins
- Cached product data
- Pagination for lists
- Async photo uploads

**Benefits**:
- Fast page loads
- Handles many concurrent RMAs
- Scales with order volume

---

## Integration Points

### Order System
- Fetches order details
- Validates items purchased
- Links RMA to original sale

### Inventory System
- Updates stock levels
- Reserves/releases inventory
- Tracks inventory status

### Payment System
- Processes refunds
- Records transactions
- Handles store credit

### Notification System
- Email/SMS to customers
- Status updates
- Admin alerts

---

## Security Considerations

### Access Control

- Customers: Only their own RMAs
- Support: Validation queue only
- Warehouse: Inspection/receiving queues
- Finance: Processing queue (refunds/credits)
- Admins: Full access

### Data Protection

- Photo uploads validated (type, size)
- Sanitized user input
- SQL injection prevention
- CSRF protection on forms

### Audit Trail

- All actions logged with actor
- Cannot delete or modify RMAs (only status transitions)
- Admin actions auditable

---

## Consequences

### Positive

✅ **Clear Process**
- Everyone knows their role
- No confusion about status
- Predictable workflow

✅ **Flexibility**
- 5 disposition types cover all scenarios
- Easy to add new disposition types
- Customizable per business need

✅ **Auditability**
- Complete activity log
- Compliance ready
- Dispute resolution

✅ **Scalability**
- Queue-based architecture
- Can add more admin users
- Handles high volume

✅ **User Experience**
- Easy for customers
- Efficient for admins
- Clear communication

### Negative

⚠️ **Complexity**
- 10 stages can seem daunting
- Training required for admins
- More database tables

⚠️ **Maintenance**
- Complex state machine
- Many edge cases
- Requires testing

⚠️ **Performance**
- Many database queries
- Large activity logs over time
- Photo storage management

### Mitigation

- **Training**: Comprehensive admin documentation
- **Testing**: End-to-end tests for all paths
- **Monitoring**: Track stage durations, bottlenecks
- **Optimization**: Database indexes, query optimization
- **Archiving**: Archive old completed RMAs

---

## Alternatives Considered

### 1. Simple Approve/Reject Only

**Pros**: Simple, easy to implement

**Cons**: No flexibility, no repair/replacement options, poor UX

**Why Not**: Doesn't meet business needs for complex scenarios

### 2. External RMA Service

**Pros**: No development needed, proven solution

**Cons**: Cost, vendor lock-in, integration complexity, less control

**Why Not**: Want full control and customization

### 3. 5-Stage Workflow

**Pros**: Simpler than 10 stages

**Cons**: Less granularity, harder to track progress, unclear responsibilities

**Why Not**: Need more visibility and role separation

---

## Success Metrics

### Operational Metrics

- Average time per stage
- Queue wait times
- Disposition distribution
- Rejection rate
- Customer satisfaction score

### System Metrics

- RMA creation success rate
- Page load times
- Database query performance
- Photo upload success rate

### Business Metrics

- Total refund amount
- Store credit issued
- Replacement rate
- Customer retention after return

---

## Future Enhancements

1. **Automated Validation**
   - ML-based fraud detection
   - Automated approval for simple cases

2. **Advanced Reporting**
   - BI dashboard integration
   - Trend analysis
   - Predictive analytics

3. **Integration**
   - Shipping carrier API
   - Payment gateway direct integration
   - CRM system sync

4. **Self-Service**
   - Customer portal for status updates
   - Chat support within RMA flow
   - FAQ and help articles

5. **Mobile App**
   - Mobile-optimized views
   - Photo upload via mobile
   - Push notifications

---

## References

- RMA Best Practices: Industry standards
- E-commerce Return Policies: Legal requirements
- Workflow Patterns: Business process modeling
- State Machine Design: Software engineering patterns

---

## Approval

**Decision**: Approved  
**Implementation Status**: Complete  
**Review Date**: 2025-11-12  
**Next Review**: 2026-05-12

---

*This ADR documents the comprehensive RMA system design and provides guidance for operations and future enhancements.*
