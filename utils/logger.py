import logging
import sys
from typing import Optional
from datetime import datetime

def setup_logger(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with colored output and detailed formatting.
    
    Args:
        name: Logger name (optional)
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    # Color codes for different log levels
    COLORS = {
        logging.DEBUG: '\033[0;36m',    # Cyan
        logging.INFO: '\033[0;32m',     # Green
        logging.WARNING: '\033[0;33m',  # Yellow
        logging.ERROR: '\033[0;31m',    # Red
        logging.CRITICAL: '\033[1;31m'  # Bold Red
    }
    RESET = '\033[0m'
    
    class ColoredFormatter(logging.Formatter):
        def format(self, record):
            # Add color to the level name
            levelname = record.levelname
            if record.levelno in COLORS:
                record.levelname = f"{COLORS[record.levelno]}{levelname}{RESET}"
            
            # Add timestamp with milliseconds
            record.created_fmt = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            
            # Format the message
            msg = super().format(record)
            record.levelname = levelname  # Restore original levelname
            return msg
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Remove existing handlers
    logger.handlers = []
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        fmt='%(created_fmt)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s'
    )
    
    # Add formatter to handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger 