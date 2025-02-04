import logging
from typing import Optional

def get_logger(name: Optional[str] = None) -> logging.Logger:
    logger = logging.getLogger(name or "MediaLake")
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s", "level":"%(levelname)s", "service":"%(name)s", "message":"%(message)s"}'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        # Set default level, can be overridden by environment variables
        logger.setLevel(logging.INFO)
    
    return logger
