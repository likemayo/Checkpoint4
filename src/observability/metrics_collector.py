"""
Metrics collection module for system observability.
Tracks key business and technical metrics for monitoring and alerting.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict, deque
from threading import Lock
import json


class MetricsCollector:
    """
    Collects and aggregates system metrics in-memory.
    Provides counters, gauges, and histograms for various metrics.
    """
    
    def __init__(self):
        self.lock = Lock()
        
        # Counters (cumulative)
        self.counters = defaultdict(int)
        
        # Gauges (point-in-time values)
        self.gauges = defaultdict(float)
        
        # Histograms (time-series data with retention)
        self.histograms = defaultdict(lambda: deque(maxlen=1000))
        
        # Time-windowed metrics (for rate calculations)
        self.time_windowed = defaultdict(lambda: deque(maxlen=10000))
        
        # Start time for uptime calculation
        self.start_time = time.time()
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict] = None):
        """Increment a counter metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict] = None):
        """Set a gauge metric to a specific value."""
        with self.lock:
            key = self._make_key(name, labels)
            self.gauges[key] = value
    
    def observe(self, name: str, value: float, labels: Optional[Dict] = None):
        """Record an observation for a histogram metric."""
        with self.lock:
            key = self._make_key(name, labels)
            self.histograms[key].append({
                'value': value,
                'timestamp': time.time()
            })
    
    def record_event(self, name: str, labels: Optional[Dict] = None):
        """Record a timestamped event for rate calculations."""
        with self.lock:
            key = self._make_key(name, labels)
            self.time_windowed[key].append(time.time())
    
    def _make_key(self, name: str, labels: Optional[Dict] = None) -> str:
        """Create a unique key from metric name and labels."""
        if labels:
            label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
            return f"{name}{{{label_str}}}"
        return name
    
    def get_counter(self, name: str, labels: Optional[Dict] = None) -> int:
        """Get current counter value."""
        key = self._make_key(name, labels)
        return self.counters.get(key, 0)
    
    def get_gauge(self, name: str, labels: Optional[Dict] = None) -> float:
        """Get current gauge value."""
        key = self._make_key(name, labels)
        return self.gauges.get(key, 0.0)
    
    def get_histogram_stats(self, name: str, labels: Optional[Dict] = None) -> Dict:
        """Get statistics for a histogram metric."""
        key = self._make_key(name, labels)
        observations = self.histograms.get(key, deque())
        
        if not observations:
            return {
                'count': 0,
                'sum': 0,
                'min': 0,
                'max': 0,
                'avg': 0,
                'p50': 0,
                'p95': 0,
                'p99': 0
            }
        
        values = sorted([obs['value'] for obs in observations])
        count = len(values)
        
        return {
            'count': count,
            'sum': sum(values),
            'min': values[0],
            'max': values[-1],
            'avg': sum(values) / count,
            'p50': values[int(count * 0.50)] if count > 0 else 0,
            'p95': values[int(count * 0.95)] if count > 0 else 0,
            'p99': values[int(count * 0.99)] if count > 0 else 0
        }
    
    def get_rate(self, name: str, window_seconds: int = 60, labels: Optional[Dict] = None) -> float:
        """Calculate rate of events per second over a time window."""
        key = self._make_key(name, labels)
        events = self.time_windowed.get(key, deque())
        
        if not events:
            return 0.0
        
        now = time.time()
        cutoff = now - window_seconds
        
        # Count events within the window
        recent_events = sum(1 for timestamp in events if timestamp >= cutoff)
        
        return recent_events / window_seconds if window_seconds > 0 else 0.0
    
    def get_all_metrics(self) -> Dict:
        """Get all metrics in a structured format."""
        with self.lock:
            return {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'uptime_seconds': time.time() - self.start_time,
                'counters': dict(self.counters),
                'gauges': dict(self.gauges),
                'histograms': {
                    name: self.get_histogram_stats(name)
                    for name in self.histograms.keys()
                }
            }
    
    def get_business_metrics(self) -> Dict:
        """Get business-specific metrics for dashboard."""
        return {
            'orders': {
                'total': self.get_counter('orders_total'),
                'successful': self.get_counter('orders_total', {'status': 'success'}),
                'failed': self.get_counter('orders_total', {'status': 'failed'}),
                'rate_per_minute': self.get_rate('orders_total', window_seconds=60) * 60
            },
            'refunds': {
                'total': self.get_counter('refunds_total'),
                'approved': self.get_counter('refunds_total', {'status': 'approved'}),
                'rejected': self.get_counter('refunds_total', {'status': 'rejected'}),
                'pending': self.get_counter('refunds_total', {'status': 'pending'}),
                'rate_per_day': self.get_rate('refunds_total', window_seconds=86400) * 86400
            },
            'errors': {
                'total': self.get_counter('errors_total'),
                'rate_per_minute': self.get_rate('errors_total', window_seconds=60) * 60,
                'by_type': {
                    '4xx': self.get_counter('http_errors', {'type': '4xx'}),
                    '5xx': self.get_counter('http_errors', {'type': '5xx'})
                }
            },
            'performance': {
                'avg_response_time_ms': self.get_histogram_stats('http_request_duration_seconds').get('avg', 0) * 1000,
                'p95_response_time_ms': self.get_histogram_stats('http_request_duration_seconds').get('p95', 0) * 1000,
                'p99_response_time_ms': self.get_histogram_stats('http_request_duration_seconds').get('p99', 0) * 1000
            }
        }


# Global metrics collector instance
metrics_collector = MetricsCollector()


def track_request_duration(endpoint: str):
    """Decorator to track request duration."""
    def decorator(f):
        from functools import wraps
        
        @wraps(f)
        def wrapped(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = f(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                metrics_collector.increment_counter('errors_total')
                raise
            finally:
                duration = time.time() - start_time
                metrics_collector.observe(
                    'http_request_duration_seconds',
                    duration,
                    labels={'endpoint': endpoint, 'status': status}
                )
        
        return wrapped
    return decorator