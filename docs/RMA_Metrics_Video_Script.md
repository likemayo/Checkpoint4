# RMA Metrics Dashboard - Video Script

**Duration**: ~5-6 minutes  
**Target Audience**: Operations managers, finance team, customer service leads, product managers  
**Dashboard URL**: `/rma/admin/metrics-dashboard`

---

## Introduction (15 seconds)

"Hi everyone! Today I'm going to walk you through our comprehensive RMA Metrics Dashboard. This dashboard provides deep insights into our Returns and Refunds operations - from business metrics like refund rates and approval rates, to operational metrics like cycle times and queue backlogs. This helps us optimize our return process, identify product quality issues, and ensure we're meeting our customer service SLAs."

---

## Dashboard Overview (10 seconds)

"You can access this dashboard from the Admin Home page under the Returns & Refunds section, or directly at `/rma/admin/metrics-dashboard`. Let's dive into each metric category."

---

## Section 1: Business Health Metrics (60 seconds)

**[Point to top section with RMA Rate, Refund Amount, Refund Rate]**

"First, let's look at our **Business Health Metrics** - these tell us how returns are impacting our bottom line.

### RMA Rate
- This shows what percentage of our orders result in return requests
- Formula: Total RMAs ÷ Total Orders × 100
- Currently showing [X]%
- Industry benchmark is 10-15% for e-commerce
- **If too low** (under 5%): Might indicate overly strict return policies hurting customer satisfaction
- **If too high** (over 20%): Could signal product quality issues or misleading product descriptions

### Total Refund Amount (Current Month)
- The dollar amount we've refunded this month
- Currently at $[X]
- This helps Finance forecast cash flow and plan reserves
- Broken down by disposition type: full refunds, partial credits, replacements

### Refund Rate
- What percentage of our revenue is being refunded
- Formula: Total Refund Amount ÷ Total Revenue × 100
- Currently at [X]%
- This is a key profitability metric
- Target: Keep under 10% to maintain healthy margins"

---

## Section 2: Operational Efficiency (45 seconds)

**[Point to Refunds per Day and Approval Rate]**

"Now let's look at **Operational Efficiency** - how well we're processing returns.

### Refunds per Day (Last 30 days)
- Average number of refunds processed daily
- Currently [X] refunds/day
- This helps us plan staffing levels
- If this number spikes, we know we need to bring in extra support or warehouse staff

### Approval Rate
- What percentage of submitted RMAs get approved by our support team
- Currently at [X]%
- **High approval rate** (80%+): Good - means most customer returns are legitimate
- **Low approval rate** (under 50%): Might indicate fraud attempts or customers not understanding our policy
- This includes all RMAs that moved past the SUBMITTED stage"

---

## Section 3: Disposition Breakdown (40 seconds)

**[Point to pie chart or disposition table]**

"The **Disposition Breakdown** shows how we're resolving approved returns.

We have 5 disposition types:
- **REFUND**: Customer gets their money back - currently [X]%
- **REPLACEMENT**: We send them a new product - [X]%
- **REPAIR**: We fix the item and return it - [X]%
- **STORE_CREDIT**: Customer gets credit for future purchases - [X]%
- **REJECT**: Return denied after inspection - [X]%

**Why this matters**: 
- High refund percentage means we're paying out cash
- High replacement percentage might indicate product quality issues
- Store credit is best for us (keeps the sale) and often satisfies customers
- Repair disposition shows our commitment to sustainability"

---

## Section 4: Queue Backlogs (35 seconds)

**[Point to queue backlog numbers]**

"**Queue Backlogs** show where RMAs are piling up in our workflow.

- **Warehouse Queue**: RMAs marked as SHIPPING - items customer is sending back. Currently [X] pending.
- **Inspection Queue**: Items we've received that need to be inspected. Currently [X] items.
- **Disposition Queue**: Items inspected and awaiting finance decision. Currently [X] pending.
- **Processing Queue**: Approved dispositions being executed (issuing refunds, shipping replacements). Currently [X] in progress.

**Watch for**: If any queue is growing rapidly, that team needs help. For example, if Inspection Queue hits 50+ items, our warehouse is bottlenecked."

---

## Section 5: Cycle Time Metrics (50 seconds)

**[Point to average cycle time and stage breakdown]**

"**Cycle Time** measures how fast we process returns - critical for customer satisfaction.

### Average Cycle Time (Overall)
- Time from RMA submission to completion
- Currently averaging [X] days
- Our SLA target is 7 days or less

### Cycle Time by Stage
This breaks down where time is spent in our 10-stage workflow:

1. **Submission → Approval**: [X] days - how long support takes to validate
2. **Approval → Received**: [X] days - shipping time (customer's side)
3. **Received → Inspected**: [X] days - warehouse inspection time
4. **Inspected → Disposition**: [X] days - finance decision time
5. **Disposition → Completed**: [X] days - executing the refund/replacement

**Identifying bottlenecks**: The longest bar tells us where we're slowest. If 'Received → Inspected' is 5 days, our warehouse team needs more resources or better processes."

---

## Section 6: SLA Compliance & Trends (40 seconds)

**[Point to SLA metric and trend indicators]**

"### SLA Compliance
- Target: Complete RMAs within 7 days
- Currently at [X]% compliance
- Green = good (80%+), Yellow = warning (70-80%), Red = critical (under 70%)

### Volume Trend (Last 30 days vs Previous 30 days)
- RMA volume: [up/down] [X]%
- **Increasing**: Could indicate seasonal returns, product issues, or marketing campaigns
- **Decreasing**: Good sign - fewer unhappy customers

### Cycle Time Trend
- Average cycle time: [up/down] [X]%
- **Increasing**: We're getting slower - need process improvements
- **Decreasing**: Great! We're getting more efficient"

---

## Section 7: Top Returned Products (35 seconds)

**[Point to products table]**

"The **Top Returned Products** table is critical for product management.

This shows:
- Product name
- Number of returns
- Return rate (returns ÷ total sales of that product)

**How to use this**:
- High return rate on specific products → quality issues or misleading descriptions
- If a product has 30% return rate → investigate with product team immediately
- Could be manufacturing defect, wrong sizing chart, misleading photos
- This data drives product improvement decisions"

---

## Section 8: How Different Teams Use This (50 seconds)

"Let me show you how different teams use this dashboard:

**Operations Team**:
- Monitors queue backlogs to allocate staff
- Watches refunds/day to predict workload
- Uses cycle time to identify process bottlenecks

**Finance Team**:
- Tracks total refund amount for cash flow planning
- Monitors refund rate to assess impact on profitability
- Uses disposition breakdown to forecast reserves

**Customer Service**:
- Watches approval rate - are we being too strict or too lenient?
- Monitors SLA compliance - are we meeting our 7-day promise?
- Uses cycle time trends to improve customer communications

**Product Management**:
- Top returned products → which items need attention
- Return rate by product → quality issues or description problems
- Disposition breakdown → are repairs viable or should we discontinue certain products?

**Executive Team**:
- RMA rate as key business health indicator
- Refund rate impact on margins
- Trend data for strategic planning"

---

## Section 9: Real Example Scenario (30 seconds)

"Let me walk through a real scenario:

Say you see:
- RMA rate jumped from 12% to 18% in last 30 days
- Top returned product: 'Wireless Headphones Pro' with 35% return rate
- Disposition: 80% are REJECT (item works fine)

**Diagnosis**: Product works correctly but doesn't meet customer expectations.

**Action**: Check product page → photos make them look bigger than they are. Update description, add size comparison photo, maybe offer free returns to rebuild trust.

This dashboard gave us the data to find and fix the root cause!"

---

## Closing (15 seconds)

"And that's our comprehensive RMA Metrics Dashboard! This single view gives operations, finance, customer service, and product teams everything they need to optimize our returns process, maintain profitability, and ensure customer satisfaction.

Questions? Reach out to the admin team. Thanks!"

---

## Technical Notes for Demo

### Before Recording:
1. Ensure realistic data in database:
   ```bash
   # Should have:
   - At least 50-100 orders
   - 10-20 RMAs in various states
   - Mix of all 5 disposition types
   - Some completed RMAs with timestamps
   - A few products with multiple returns
   ```

2. Check dashboard loads properly:
   - Login as admin
   - Navigate to Admin Home → RMA Admin Dashboard → Metrics Dashboard
   - Verify all charts/numbers display

3. Optional: Create some "problem" scenarios:
   - One product with high return rate (15%+)
   - Some RMAs stuck in one queue (show backlog)
   - Mix of fast and slow cycle times

### During Recording:
- **Zoom in on numbers** when discussing specific metrics
- **Highlight trends** with mouse or annotation tool
- **Pause on the disposition breakdown** - visually interesting
- **Show the queue backlog** numbers clearly
- **Point to the bottleneck** in cycle time breakdown

### Screen Flow:
1. Start at Admin Home page
2. Click "RMA Admin Dashboard" card
3. Click "Metrics Dashboard" (or navigate directly to `/rma/admin/metrics-dashboard`)
4. Walk through each section top to bottom
5. Maybe refresh page to show it's live data
6. End with a summary of key metrics

### Key Talking Points to Emphasize:

**Business Context**:
- "This isn't just data - it's actionable intelligence"
- "Each metric connects to a business decision"
- "We can catch problems before they impact revenue"

**Cross-Functional Value**:
- "Every team uses this differently - that's the power"
- "Finance sees cash flow, Operations sees workload, Product sees quality issues"

**Data Integrity**:
- "All calculations come from the database - 100% accurate"
- "Updated in real-time as RMAs move through the workflow"

### Common Questions & Answers:

**Q: What's a good RMA rate?**  
A: For general e-commerce: 10-15%. Fashion/apparel: 20-30% (size issues). Electronics: 5-10%. Below 5% might mean restrictive policies; above 25% indicates serious product or description issues.

**Q: Why track disposition breakdown?**  
A: Financial impact varies wildly. REFUND = cash out. REPLACEMENT = cost of goods + shipping. STORE_CREDIT = revenue retained. REPAIR = minimal cost. REJECT = no cost. Knowing the mix helps forecast expenses.

**Q: What causes queue backlogs?**  
A: Usually staffing. Warehouse backlog = need more inspectors. Disposition backlog = finance team overwhelmed. Could also be process issues - if inspection takes 30 minutes per item but should take 5, we need better procedures.

**Q: How do you improve SLA compliance?**  
A: Identify the longest cycle time stage and optimize it. If "Approval → Received" is slow, maybe offer prepaid return labels. If "Disposition → Completed" is slow, automate refund processing.

**Q: What's the most important metric?**  
A: Depends on role. CEO cares about RMA rate and refund rate (revenue impact). COO cares about cycle time and queue backlogs (operational efficiency). CFO cares about total refund amount (cash flow).

---

## Alternative: Shorter 3-Minute Version

### Quick Script (3 minutes)

"Hi! Let's look at our RMA Metrics Dashboard at `/rma/admin/metrics-dashboard`.

**Business Health**: RMA rate shows [X]% of orders result in returns - industry standard is 10-15%. We've refunded $[X] this month, which is [X]% of revenue.

**Disposition Breakdown**: [X]% refunds, [X]% replacements, [X]% repairs, [X]% store credit, [X]% rejected. Store credit is best for us - keeps the revenue.

**Queue Backlogs**: [X] items in warehouse, [X] awaiting inspection, [X] pending disposition decision. These numbers tell us where to allocate staff.

**Cycle Time**: Averaging [X] days from submission to completion. Our SLA is 7 days, currently at [X]% compliance. The breakdown shows which stage is the bottleneck.

**Top Returned Products**: This table shows which products have quality issues. If a product has 30%+ return rate, we investigate immediately - usually misleading description or manufacturing defect.

**Trends**: RMA volume is [up/down] [X]%, cycle time is [up/down] [X]%. These help us forecast and plan.

Different teams use this differently - Operations watches queues, Finance tracks refund amounts, Product investigates high-return items, Customer Service monitors SLA compliance.

This dashboard turns raw RMA data into actionable business intelligence. Thanks!"

---

