import logging
import os
from typing import Dict, Optional

# Define log levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class CDKLogger:
    """CDK logging utility with consistent configuration."""

    _loggers: Dict[str, logging.Logger] = {}
    _initialized = False
    _global_level = logging.INFO

    @classmethod
    def _initialize_from_config(cls):
        """Initialize logger from configuration."""
        if cls._initialized:
            return

        try:
            # Try to import config without creating circular imports
            import importlib

            config_module = importlib.import_module("config")

            if hasattr(config_module, "config") and hasattr(
                config_module.config, "logging"
            ):
                log_level = getattr(config_module.config.logging, "level", "INFO")
                cls._global_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
        except (ImportError, AttributeError):
            # Fall back to environment variable if config import fails
            log_level = os.environ.get("MEDIALAKE_LOG_LEVEL", "INFO")
            cls._global_level = LOG_LEVELS.get(log_level.upper(), logging.INFO)

        cls._initialized = True

    @classmethod
    def get_logger(cls, name: Optional[str] = None) -> logging.Logger:
        """Get or create a logger with the given name."""
        # Initialize from config the first time
        if not cls._initialized:
            cls._initialize_from_config()

        logger_name = name or "MediaLake"

        # Return existing logger if already created
        if logger_name in cls._loggers:
            return cls._loggers[logger_name]

        # Create new logger
        logger = logging.getLogger(logger_name)

        if not logger.handlers:
            # Create and configure handler
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '{"timestamp":"%(asctime)s", "level":"%(levelname)s", "service":"%(name)s", "message":"%(message)s"}'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # Set the global log level
            logger.setLevel(cls._global_level)

        # Store logger in cache
        cls._loggers[logger_name] = logger
        return logger

    @classmethod
    def set_level(cls, level: str) -> None:
        """Set log level for all loggers."""
        log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
        cls._global_level = log_level

        # Update all existing loggers
        for logger in cls._loggers.values():
            logger.setLevel(log_level)


# For backward compatibility
def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get a logger with the specified name."""
    return CDKLogger.get_logger(name)
