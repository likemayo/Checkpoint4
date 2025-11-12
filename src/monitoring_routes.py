"""
Monitoring dashboard and metrics API endpoints.
Provides real-time visibility into system health and performance.
"""

from flask import Blueprint, render_template, jsonify, request
from src.observability.metrics_collector import metrics_collector
from src.observability.structured_logger import app_logger
import time

monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/monitoring')


@monitoring_bp.route('/dashboard')
def dashboard():
    """Render the monitoring dashboard UI."""
    return render_template('monitoring/dashboard.html')


@monitoring_bp.route('/api/metrics')
def get_metrics():
    """
    API endpoint to fetch current metrics.
    Returns JSON with all collected metrics.
    """
    try:
        metrics = metrics_collector.get_business_metrics()
        app_logger.info("Metrics fetched successfully")
        return jsonify({
            'status': 'success',
            'data': metrics,
            'timestamp': time.time()
        })
    except Exception as e:
        app_logger.error(f"Error fetching metrics: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


@monitoring_bp.route('/api/metrics/orders')
def get_order_metrics():
    """Get detailed order metrics."""
    return jsonify({
        'total_orders': metrics_collector.get_counter('orders_total'),
        'successful_orders': metrics_collector.get_counter('orders_total', {'status': 'success'}),
        'failed_orders': metrics_collector.get_counter('orders_total', {'status': 'failed'}),
        'orders_per_minute': metrics_collector.get_rate('orders_total', window_seconds=60) * 60,
        'orders_per_hour': metrics_collector.get_rate('orders_total', window_seconds=3600) * 3600
    })


@monitoring_bp.route('/api/metrics/refunds')
def get_refund_metrics():
    """Get detailed refund/returns metrics."""
    return jsonify({
        'total_refunds': metrics_collector.get_counter('refunds_total'),
        'approved_refunds': metrics_collector.get_counter('refunds_total', {'status': 'approved'}),
        'rejected_refunds': metrics_collector.get_counter('refunds_total', {'status': 'rejected'}),
        'pending_refunds': metrics_collector.get_counter('refunds_total', {'status': 'pending'}),
        'refunds_per_day': metrics_collector.get_rate('refunds_total', window_seconds=86400) * 86400,
        'avg_refund_amount_cents': metrics_collector.get_gauge('avg_refund_amount_cents')
    })


@monitoring_bp.route('/api/metrics/errors')
def get_error_metrics():
    """Get detailed error metrics."""
    return jsonify({
        'total_errors': metrics_collector.get_counter('errors_total'),
        'errors_per_minute': metrics_collector.get_rate('errors_total', window_seconds=60) * 60,
        'client_errors_4xx': metrics_collector.get_counter('http_errors', {'type': '4xx'}),
        'server_errors_5xx': metrics_collector.get_counter('http_errors', {'type': '5xx'}),
        'rate_limit_errors': metrics_collector.get_counter('errors_total', {'type': 'rate_limit'}),
        'payment_errors': metrics_collector.get_counter('errors_total', {'type': 'payment'})
    })


@monitoring_bp.route('/api/metrics/performance')
def get_performance_metrics():
    """Get detailed performance metrics."""
    duration_stats = metrics_collector.get_histogram_stats('http_request_duration_seconds')
    
    return jsonify({
        'avg_response_time_ms': duration_stats.get('avg', 0) * 1000,
        'p50_response_time_ms': duration_stats.get('p50', 0) * 1000,
        'p95_response_time_ms': duration_stats.get('p95', 0) * 1000,
        'p99_response_time_ms': duration_stats.get('p99', 0) * 1000,
        'min_response_time_ms': duration_stats.get('min', 0) * 1000,
        'max_response_time_ms': duration_stats.get('max', 0) * 1000,
        'total_requests': duration_stats.get('count', 0)
    })


@monitoring_bp.route('/api/health')
def health_check():
    """
    Health check endpoint for container orchestration.
    Returns service health status.
    """
    uptime = time.time() - metrics_collector.start_time
    
    # Check if error rate is too high
    error_rate = metrics_collector.get_rate('errors_total', window_seconds=60)
    is_healthy = error_rate < 1.0  # Less than 1 error per second
    
    return jsonify({
        'status': 'healthy' if is_healthy else 'degraded',
        'uptime_seconds': uptime,
        'error_rate_per_second': error_rate,
        'timestamp': time.time()
    }), 200 if is_healthy else 503


@monitoring_bp.route('/api/logs/recent')
def get_recent_logs():
    """
    Get recent log entries (last 100 lines from log file).
    """
    try:
        with open('logs/app.log', 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-100:]  # Last 100 lines
            
            logs = []
            for line in recent_lines:
                try:
                    import json
                    log_entry = json.loads(line.strip())
                    logs.append(log_entry)
                except:
                    # Skip malformed lines
                    pass
            
            return jsonify({
                'status': 'success',
                'logs': logs,
                'count': len(logs)
            })
    except FileNotFoundError:
        return jsonify({
            'status': 'success',
            'logs': [],
            'count': 0,
            'message': 'No logs available yet'
        })
    except Exception as e:
        app_logger.error(f"Error reading logs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500