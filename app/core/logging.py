import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict
from contextvars import ContextVar

# Context variable to store request_id across async calls
request_id_ctx: ContextVar[str] = ContextVar('request_id', default='system')

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs logs in consistent JSON format with request_id tracking.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "request_id": request_id_ctx.get(),
            "logger": record.name,
            "file": record.pathname,
            "line": record.lineno,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
            
        return json.dumps(log_data)


def setup_logger(name: str = "OneTwenty") -> logging.Logger:
    """
    Set up and return a logger with JSON formatting.
    
    Args:
        name: Logger name (typically module name)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Console handler with JSON formatter
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    
    return logger


def set_request_id(req_id: str):
    """Set the request ID for the current context."""
    request_id_ctx.set(req_id)


def get_request_id() -> str:
    """Get the current request ID."""
    return request_id_ctx.get()


# Create a default logger instance
logger = setup_logger()
