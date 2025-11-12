"""
Structured logging module for observability.
Provides consistent log formatting with request IDs, timestamps, and severity levels.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
from flask import request, g


class StructuredLogger:
    """
    Provides structured logging with consistent formatting.
    Logs are output in JSON format for easy parsing and analysis.
    """
    
    def __init__(self, name: str, log_level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Create console handler with JSON formatting
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        self.logger.addHandler(handler)
        
        # Also add file handler (create directory if it doesn't exist)
        import os
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.FileHandler('logs/app.log')
        file_handler.setFormatter(JsonFormatter())
        self.logger.addHandler(file_handler)
    
    def _get_request_id(self) -> str:
        """Get or create request ID for current request context."""
        if hasattr(g, 'request_id'):
            return g.request_id
        return str(uuid.uuid4())
    
    def _build_log_entry(self, level: str, message: str, **kwargs) -> Dict[str, Any]:
        """Build structured log entry."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "message": message,
            "request_id": self._get_request_id(),
        }
        
        # Add any additional context
        if kwargs:
            log_entry["context"] = kwargs
        
        # Add request details if available
        if request:
            try:
                log_entry["request"] = {
                    "method": request.method,
                    "path": request.path,
                    "remote_addr": request.remote_addr
                }
            except RuntimeError:
                # Outside request context
                pass
        
        return log_entry
    
    def info(self, message: str, **kwargs):
        """Log info level message."""
        self.logger.info(json.dumps(self._build_log_entry("INFO", message, **kwargs)))
    
    def warning(self, message: str, **kwargs):
        """Log warning level message."""
        self.logger.warning(json.dumps(self._build_log_entry("WARNING", message, **kwargs)))
    
    def error(self, message: str, **kwargs):
        """Log error level message."""
        self.logger.error(json.dumps(self._build_log_entry("ERROR", message, **kwargs)))
    
    def debug(self, message: str, **kwargs):
        """Log debug level message."""
        self.logger.debug(json.dumps(self._build_log_entry("DEBUG", message, **kwargs)))
    
    def critical(self, message: str, **kwargs):
        """Log critical level message."""
        self.logger.critical(json.dumps(self._build_log_entry("CRITICAL", message, **kwargs)))


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs JSON."""
    
    def format(self, record):
        return record.getMessage()


def log_request(logger: StructuredLogger):
    """
    Decorator to automatically log API requests and responses.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            # Generate request ID
            g.request_id = str(uuid.uuid4())
            
            # Log incoming request
            logger.info(
                f"Incoming request to {request.endpoint}",
                method=request.method,
                path=request.path,
                remote_addr=request.remote_addr
            )
            
            try:
                # Execute the route function
                response = f(*args, **kwargs)
                
                # Log successful response
                logger.info(
                    f"Request completed successfully",
                    endpoint=request.endpoint,
                    status_code=getattr(response, 'status_code', 200)
                )
                
                return response
            
            except Exception as e:
                # Log error
                logger.error(
                    f"Request failed with exception",
                    endpoint=request.endpoint,
                    exception=str(e),
                    exception_type=type(e).__name__
                )
                raise
        
        return wrapped
    return decorator


# Create global logger instance
app_logger = StructuredLogger("retail_app", log_level="INFO")