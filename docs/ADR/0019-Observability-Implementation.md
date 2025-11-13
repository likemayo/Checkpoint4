```markdown
# ADR-0019: Observability Implementation

**Status:** Accepted

**Date:** 2025-11-13

**Decision Makers:** Development Team

**Related ADRs:** ADR-0019 Docker Containerization, ADR-009 Circuit Breaker Pattern

---

## Context

The Checkpoint3 retail system needs an operational observability strategy so engineers and operators can:

- Understand system health and performance (latency, errors, throughput)
- Detect and resolve incidents quickly (alerts, runbooks)
- Measure business/operational metrics (RMA rate, refund amounts, queue depth)
- Correlate traces across components for debugging (web, worker, payment integrations)

Current state of the codebase:

- Flask web app exposing `/health` and other endpoints
- `src/observability/metrics_collector.py` used by RMA routes
- RMA metrics stored and surfaced in `src/rma/manager.py` and templates
- Docker and docker-compose used for deployment (see ADR-0019: Docker Containerization)

Requirements:

- Low-friction local/CI integration for developers
- Lightweight runtime overhead for production
- Docker-friendly (works with our compose-based deployment)
- Support for metrics, logs, traces, and alerting
- Practical, incremental rollout — start with metrics + logs, add tracing later

## Decision

We will adopt a pragmatic, tiered observability stack:

1. Metrics: instrument application code and export metrics via Prometheus-compatible endpoints. Use a lightweight in-process collector and expose /metrics for scraping.
2. Logging: structured JSON logs (stdout) for all services so logs can be captured by container runtime and aggregated by the platform (or file during local development).
3. Tracing: add optional OpenTelemetry tracing instrumentation for critical flows (payment calls, RMA workflow) with a no-op/collector fallback in dev.
4. Alerting and Dashboards: define basic Prometheus alerts and Grafana dashboards for uptime, error rates, latency, and RMA business metrics.

This keeps the stack simple while giving immediate value for debugging and SRE workflows.

## Rationale

- Prometheus + Grafana are well-supported, lightweight, and work with Docker Compose.
- Structured logs (JSON) are standard and enable filtering and correlation with traces/metrics.
- OpenTelemetry provides vendor-neutral tracing and can be toggled off in low-cost environments.
- Starting with metrics + logs gives high ROI quickly; traces can be added for low-frequency, high-value flows.

## Implementation Details

Instrumentation and code locations

- Metrics collector: continue using `src/observability/metrics_collector.py`. Ensure it exposes a Prometheus scrape endpoint (e.g., `/metrics`).
- RMA metrics: `src/rma/manager.py` already updates `rma_metrics`; add exporter hooks to surface these as Prometheus gauges/counters.
- Route-level metrics: instrument key endpoints (e.g., `POST /rma/submit`, `GET /rma/my-returns`, payment endpoints) with counters and request duration histograms.
- Health check: keep `/health` returning 200 when app and critical dependencies are healthy; return 503 when degraded.

Prometheus

- Expose `/metrics` on the web service (Flask) for Prometheus scraping.
- Sample metrics to export:
	- `http_requests_total{method,endpoint,status}` counter
	- `http_request_duration_seconds_bucket{method,endpoint}` histogram
	- `rma_requests_total{status}` counter
	- `rma_queue_depth` gauge (per admin queue)
	- `payment_gateway_failures_total` counter
	- `circuit_breaker_state{service}` gauge (0=closed,1=open,2=half-open)

- Configure Prometheus scrape in docker-compose (for local dev) or platform-specific Prometheus config in production.

Logging

- Log to stdout in structured JSON.
- Include these fields where applicable: timestamp, level, logger, message, request_id, trace_id, user_id, path, status_code, duration_ms.
- Ensure exceptions include stack traces in the log entry.

Tracing (OpenTelemetry)

- Instrument high-value flows with OpenTelemetry SDK (Python). Provide configuration via env vars to enable/disable and to set exporter (OTLP/collector endpoint).
- Propagate trace and span IDs in logs (trace_id) for correlation.

Alerting and dashboards

- Define Prometheus alert rules (examples):
	- High error rate: rates(http_requests_total{status=~"5.."}[5m]) > 0.05
	- High latency: histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint)) > 1.0
	- RMA backlog growth: increase(rma_requests_total{status="SUBMITTED"}[15m]) > threshold
	- Health check failing: `up{job="checkpoint3-web"} == 0`

- Create Grafana dashboards:
	- System overview: uptime, request rate, errors, 95p latency
	- RMA operations: daily RMA rate, approval rate, disposition counts, queue depths
	- Payments: failure rate, circuit-breaker state

Deployment and Docker

- Ensure `docker-compose.yml` includes Prometheus (and Grafana) services for local development OR document how to add them.
- Expose `/metrics` port for scraping; do not expose Prometheus or Grafana to the public internet in production without auth.

Operational runbook (short)

- When alert fires for high error rate:
	1. Check `docker-compose logs` for service logs.
 2. Correlate with traces (if enabled) for recent requests.
 3. Check health endpoint and Prometheus targets.
 4. Rollback if a recent deploy caused the spike; if not, escalate to on-call.

Privacy and cost considerations

- Avoid shipping PII in logs. Mask or omit sensitive fields (payment identifiers, full card numbers, user passwords).
- Tracing can be noisy — sample traces in production (e.g., 1% or adaptive sampling) and capture 100% for high-error requests.

Open points / next steps

1. Add an instrumented `/metrics` endpoint and exporter in `src/observability/metrics_collector.py` if not already present.
2. Wire RMA metrics into Prometheus metrics.
3. Add basic Prometheus + Grafana docker-compose services for local development (optional package under `tools/` or documented in `DOCKER.md`).
4. Implement structured JSON logging across Flask app and workers.
5. Optional: add OpenTelemetry tracing with OTLP exporter behind a feature flag.

## Alternatives Considered

- SaaS monitoring (Datadog/New Relic): easier setup but increases cost and vendor lock-in.
- Full OpenTelemetry rollout immediately: higher initial complexity; deferred to phased approach.

## Consequences

- Positive: Faster incident response, measurable business metrics, better visibility into failures.
- Negative: Slight increase in runtime overhead and operational complexity. Mitigations are sampling and phased rollout.

## References

- Prometheus: https://prometheus.io/
- Grafana: https://grafana.com/
- OpenTelemetry Python: https://opentelemetry.io/
- `src/observability/metrics_collector.py` in repository
- `src/rma/manager.py` for RMA metrics update points

## Approval

**Decision:** Approved

**Implementation status:** Partial — metrics collector exists; ADR documents scope to complete rollout.

---

*This ADR documents the observability approach for Checkpoint3 and provides concrete next steps to implement metrics, logs, tracing, and alerting.*

```
