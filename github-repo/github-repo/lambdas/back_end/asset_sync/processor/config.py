# config.py
import os
from dataclasses import dataclass


@dataclass
class RetryConfig:
    max_attempts: int = int(os.getenv("MAX_RETRY_ATTEMPTS", "10"))
    base_backoff_time: float = float(os.getenv("BASE_BACKOFF_TIME", "0.2"))
    max_backoff_time: float = float(os.getenv("MAX_BACKOFF_TIME", "30.0"))


@dataclass
class ProcessingConfig:
    batch_size: int = int(os.getenv("PROCESSING_BATCH_SIZE", "100"))
    max_concurrent_tasks: int = int(os.getenv("MAX_CONCURRENT_TASKS", "10"))
