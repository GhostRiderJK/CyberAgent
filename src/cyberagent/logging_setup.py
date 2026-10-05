"""
Logging setup for CyberAgent.
Configures logging for the entire application.
"""
import logging
import sys
from typing import Optional
from .config import config

def setup_logging(name: str = "cyberagent", level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        name: Logger name
        level: Logging level (e.g., 'INFO', 'DEBUG'). If None, uses config.
        
    Returns:
        Configured logger instance
    """
    if level is None:
        level = config.get("logging.level", "INFO")
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
    
    # Create formatter
    formatter = logging.Formatter(config.get("logging.format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# Default logger
logger = setup_logging()
