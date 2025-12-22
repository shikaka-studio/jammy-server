import logging
import sys

from pathlib import Path
from typing import Any

from app.config import get_settings

# ANSI color codes for terminal output
class LogColors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for different log levels"""
    
    COLORS = {
        logging.DEBUG: LogColors.GRAY,
        logging.INFO: LogColors.BLUE,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.MAGENTA,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Add color to level name
        levelname = record.levelname
        if record.levelno in self.COLORS:
            levelname_color = f"{self.COLORS[record.levelno]}{levelname}{LogColors.RESET}"
            record.levelname = levelname_color
        
        # Format the message
        formatted = super().format(record)
        
        # Reset levelname for next use
        record.levelname = levelname
        
        return formatted


def setup_logging() -> None:
    """
    Configure logging for the entire application.
    
    Call this once at application startup (in main.py before creating the FastAPI app).
    """
    settings = get_settings()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler with colors (for development)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(settings.log_level)
    
    if settings.is_development:
        # Detailed format with colors for development
        formatter = ColoredFormatter(
            fmt="%(levelname)s:\t%(asctime)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    else:
        # Structured format for production (easier to parse)
        formatter = logging.Formatter(
            fmt="%(levelname)s:%(asctime)s:%(name)s:%(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Optional: File handler for production (with rotation)
    if settings.is_production:
        from logging.handlers import RotatingFileHandler
        
        # Create logs directory if it doesn't exist
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        
        # Rotating file handler (10MB per file, keep 5 backup files)
        file_handler = RotatingFileHandler(
            filename=log_dir / "jammy-server.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Configure third-party loggers to be less verbose
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("supabase").setLevel(logging.WARNING)
    
    # Set uvicorn loggers to use our configuration
    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.error").handlers.clear()


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.
    
    Usage in any module:
        from app.core.logging import get_logger
        logger = get_logger(__name__)
        logger.info("Something happened")
    
    Args:
        name: Usually __name__ to get the module path as logger name
    
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
