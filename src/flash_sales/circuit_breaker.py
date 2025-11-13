from functools import wraps
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any
from threading import Lock

# Import observability with fallback
try:
    from src.observability.metrics_collector import metrics_collector
    from src.observability.structured_logger import app_logger
    OBSERVABILITY_ENABLED = True
except ImportError:
    OBSERVABILITY_ENABLED = False


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern for protecting against cascading failures"""
    
    def __init__(
        self,
        failure_threshold: int = 3,  # Changed to 3 for demo (was 5)
        timeout_seconds: int = 30,    # Changed to 30 for demo (was 60)
        success_threshold: int = 2,
        name: str = "default"         # NEW: Name for logging/metrics
    ):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.success_threshold = success_threshold
        self.name = name  # NEW
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function through circuit breaker"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    
                    # NEW: Log state transition
                    if OBSERVABILITY_ENABLED:
                        try:
                            app_logger.info(
                                f"Circuit breaker '{self.name}' moved to HALF_OPEN",
                                circuit_name=self.name,
                                state="HALF_OPEN",
                                timeout_seconds=self.timeout_seconds
                            )
                            metrics_collector.increment_counter(
                                'circuit_breaker_state_changes',
                                labels={'circuit': self.name, 'new_state': 'HALF_OPEN'}
                            )
                        except Exception:
                            # Observability failed, continue anyway
                            pass
                else:
                    # NEW: Track fast-fail rejections
                    if OBSERVABILITY_ENABLED:
                        try:
                            metrics_collector.increment_counter(
                                'circuit_breaker_rejections',
                                labels={'circuit': self.name}
                            )
                            app_logger.warning(
                                f"Circuit breaker '{self.name}' is OPEN - request rejected",
                                circuit_name=self.name,
                                state="OPEN",
                                failure_count=self.failure_count
                            )
                        except Exception:
                            # Observability failed, continue anyway
                            pass
                    
                    raise CircuitBreakerOpenError("Circuit breaker is OPEN")
        
        # Execute function outside the lock
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            raise
    
    def _on_success(self):
        """Handle successful call"""
        with self.lock:
            previous_state = self.state
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    
                    # NEW: Log recovery
                    if OBSERVABILITY_ENABLED:
                        try:
                            app_logger.info(
                                f"Circuit breaker '{self.name}' CLOSED - recovered",
                                circuit_name=self.name,
                                state="CLOSED",
                                success_count=self.success_threshold
                            )
                            metrics_collector.increment_counter(
                                'circuit_breaker_state_changes',
                                labels={'circuit': self.name, 'new_state': 'CLOSED'}
                            )
                            metrics_collector.increment_counter(
                                'circuit_breaker_recoveries',
                                labels={'circuit': self.name}
                            )
                        except Exception:
                            # Observability failed, continue anyway
                            pass
    
    def _on_failure(self, exception: Exception = None):
        """Handle failed call"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            # NEW: Track each failure
            if OBSERVABILITY_ENABLED:
                try:
                    metrics_collector.increment_counter(
                        'circuit_breaker_failures',
                        labels={'circuit': self.name}
                    )
                    app_logger.warning(
                        f"Circuit breaker '{self.name}' failure",
                        circuit_name=self.name,
                        failure_count=self.failure_count,
                        threshold=self.failure_threshold,
                        error=str(exception) if exception else None
                    )
                except Exception:
                    # Observability failed, continue anyway
                    pass
            
            if self.failure_count >= self.failure_threshold:
                previous_state = self.state
                self.state = CircuitState.OPEN
                
                # NEW: Log circuit opening
                if OBSERVABILITY_ENABLED:
                    try:
                        app_logger.error(
                            f"Circuit breaker '{self.name}' OPENED",
                            circuit_name=self.name,
                            state="OPEN",
                            failure_count=self.failure_count,
                            threshold=self.failure_threshold,
                            timeout_seconds=self.timeout_seconds
                        )
                        metrics_collector.increment_counter(
                            'circuit_breaker_state_changes',
                            labels={'circuit': self.name, 'new_state': 'OPEN'}
                        )
                        metrics_collector.increment_counter(
                            'circuit_breaker_opens',
                            labels={'circuit': self.name}
                        )
                    except Exception:
                        # Observability failed, continue anyway
                        pass
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open"""
        if self.last_failure_time is None:
            return True
        
        elapsed = datetime.now() - self.last_failure_time
        return elapsed > timedelta(seconds=self.timeout_seconds)
    
    def reset(self):
        """Manually reset circuit breaker"""
        with self.lock:
            previous_state = self.state
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            
            # NEW: Log manual reset
            if OBSERVABILITY_ENABLED:
                try:
                    app_logger.info(
                        f"Circuit breaker '{self.name}' manually reset",
                        circuit_name=self.name,
                        previous_state=previous_state.value,
                        new_state="CLOSED"
                    )
                    metrics_collector.increment_counter(
                        'circuit_breaker_resets',
                        labels={'circuit': self.name}
                    )
                except Exception:
                    # Observability failed, continue anyway
                    pass
    
    def get_state(self) -> CircuitState:
        """Get current circuit state"""
        return self.state
    
    def get_metrics(self) -> dict:
        """NEW: Get circuit breaker metrics for monitoring"""
        return {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'failure_threshold': self.failure_threshold,
            'timeout_seconds': self.timeout_seconds,
            'last_failure_time': self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


def circuit_breaker(failure_threshold=3, timeout_seconds=30, name="default"):
    """Decorator to apply circuit breaker to functions"""
    breaker = CircuitBreaker(failure_threshold, timeout_seconds, name=name)
    
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            return breaker.call(f, *args, **kwargs)
        wrapped.circuit_breaker = breaker  # Expose breaker for testing
        return wrapped
    return decorator