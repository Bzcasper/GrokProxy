"""
Colored console logging with structured JSON output.

Provides colorized console output for development while maintaining JSON logging for production.
"""

import logging
import sys
from typing import Optional
from datetime import datetime

# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Log levels
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[31m'      # Red
    CRITICAL = '\033[35m'   # Magenta
    
    # Components
    TIMESTAMP = '\033[90m'  # Gray
    LOGGER = '\033[94m'     # Blue
    MESSAGE = '\033[97m'    # White
    
    # Special
    SUCCESS = '\033[92m'    # Bright Green
    METRIC = '\033[96m'     # Bright Cyan
    REQUEST = '\033[95m'    # Bright Magenta


class ColoredFormatter(logging.Formatter):
    """
    Colored console formatter for development.
    
    Adds colors to log levels and components while keeping structure readable.
    """
    
    LEVEL_COLORS = {
        logging.DEBUG: Colors.DEBUG,
        logging.INFO: Colors.INFO,
        logging.WARNING: Colors.WARNING,
        logging.ERROR: Colors.ERROR,
        logging.CRITICAL: Colors.CRITICAL,
    }
    
    LEVEL_ICONS = {
        logging.DEBUG: '🔍',
        logging.INFO: '✓',
        logging.WARNING: '⚠️',
        logging.ERROR: '✗',
        logging.CRITICAL: '🔥',
    }
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors."""
        # Get color for level
        level_color = self.LEVEL_COLORS.get(record.levelno, Colors.RESET)
        icon = self.LEVEL_ICONS.get(record.levelno, '•')
        
        # Format timestamp
        timestamp = datetime.utcnow().strftime('%H:%M:%S.%f')[:-3]
        timestamp_str = f"{Colors.TIMESTAMP}{timestamp}{Colors.RESET}"
        
        # Format level
        level_str = f"{level_color}{icon} {record.levelname:8s}{Colors.RESET}"
        
        # Format logger name
        logger_str = f"{Colors.LOGGER}[{record.name}]{Colors.RESET}"
        
        # Format message
        message = record.getMessage()
        
        # Check for special message types
        if 'request_id=' in message or 'generation_id=' in message:
            message_color = Colors.REQUEST
        elif '✓' in message or 'success' in message.lower():
            message_color = Colors.SUCCESS
        elif 'metric' in message.lower() or 'latency' in message.lower():
            message_color = Colors.METRIC
        else:
            message_color = Colors.MESSAGE
        
        message_str = f"{message_color}{message}{Colors.RESET}"
        
        # Combine
        formatted = f"{timestamp_str} {level_str} {logger_str} {message_str}"
        
        # Add exception info if present
        if record.exc_info:
            formatted += f"\n{Colors.ERROR}{self.formatException(record.exc_info)}{Colors.RESET}"
        
        return formatted


def setup_colored_logging(
    level: str = "INFO",
    enable_colors: bool = True,
    json_output: bool = False
) -> None:
    """
    Setup colored logging for the application.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_colors: Whether to enable colored output
        json_output: If True, use JSON formatter instead of colored
    """
    # Determine if we should use colors
    use_colors = enable_colors and sys.stdout.isatty() and not json_output
    
    # Create formatter
    if json_output:
        from observability.logging import JSONFormatter
        formatter = JSONFormatter()
    elif use_colors:
        formatter = ColoredFormatter()
    else:
        # Plain text formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Add console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Log startup message
    logger = logging.getLogger(__name__)
    if use_colors:
        logger.info(f"{Colors.SUCCESS}Colored logging enabled{Colors.RESET}")
    else:
        logger.info("Logging configured")


def get_colored_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with colored output.
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Convenience functions for special log types
def log_request(logger: logging.Logger, request_id: str, method: str, endpoint: str, **kwargs):
    """Log an incoming request with special formatting."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"→ {method} {endpoint} request_id={request_id} {extra_info}")


def log_response(logger: logging.Logger, request_id: str, status: int, latency_ms: int, **kwargs):
    """Log a response with special formatting."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"← Response {status} request_id={request_id} latency={latency_ms}ms {extra_info}")


def log_metric(logger: logging.Logger, metric_name: str, value: float, unit: str = "", **labels):
    """Log a metric with special formatting."""
    label_str = " ".join(f"{k}={v}" for k, v in labels.items())
    logger.info(f"📊 {metric_name}={value}{unit} {label_str}")


def log_success(logger: logging.Logger, message: str, **kwargs):
    """Log a success message with special formatting."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info(f"✓ {message} {extra_info}")


def log_error(logger: logging.Logger, message: str, error: Optional[Exception] = None, **kwargs):
    """Log an error with special formatting."""
    extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
    if error:
        logger.error(f"✗ {message} error={str(error)} {extra_info}", exc_info=error)
    else:
        logger.error(f"✗ {message} {extra_info}")


# Example usage
if __name__ == "__main__":
    setup_colored_logging(level="DEBUG", enable_colors=True)
    
    logger = get_colored_logger(__name__)
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")
    logger.critical("This is a critical message")
    
    log_request(logger, "req-123", "POST", "/v1/chat/completions", model="grok-3")
    log_response(logger, "req-123", 200, 1234, tokens=150)
    log_metric(logger, "request_latency", 1.234, "s", endpoint="/chat", status="200")
    log_success(logger, "Session created", session_id="sess-456")
    log_error(logger, "Failed to connect", error=ConnectionError("Timeout"))
