"""
Standardized logging configuration for the speaker database pipeline.

Provides structured logging with consistent format across all modules.
Railway can parse these logs for monitoring and alerting.

Log Levels:
- INFO: Normal operations, progress updates, successful completions
- WARNING: Recoverable issues, skipped items, retries, degraded performance
- ERROR: Failures, exceptions, data integrity issues
"""

import logging
import sys
from datetime import datetime
from typing import Optional, Dict, Any


class StructuredFormatter(logging.Formatter):
    """
    Formats log messages with structured fields for easy parsing.

    Format: [LEVEL] timestamp | component | message | key=value key=value
    Example: [INFO] 2026-02-24T10:30:45Z | pipeline.extraction | Event processed | event_id=123 speakers=5
    """

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        # Extract component from logger name (e.g., "pipeline.extraction" from "pipeline_cron.extraction")
        component = record.name.replace('_', '.')

        # Build base message
        base = f"[{record.levelname}] {timestamp} | {component} | {record.getMessage()}"

        # Add extra fields if provided
        if hasattr(record, 'extra_fields') and record.extra_fields:
            fields = ' | '.join([f"{k}={v}" for k, v in record.extra_fields.items()])
            return f"{base} | {fields}"

        return base


def setup_logging(component: str, level: int = logging.INFO) -> logging.Logger:
    """
    Setup standardized logging for a component.

    Args:
        component: Component name (e.g., "pipeline.extraction", "web.search")
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(component)
    logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with structured format
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(StructuredFormatter())

    logger.addHandler(handler)
    logger.propagate = False  # Don't propagate to root logger

    return logger


def log_with_context(logger: logging.Logger, level: int, message: str, **context):
    """
    Log a message with structured context fields.

    Args:
        logger: Logger instance
        level: Log level (logging.INFO, logging.WARNING, logging.ERROR)
        message: Log message
        **context: Key-value pairs for structured context

    Example:
        log_with_context(logger, logging.INFO, "Event processed",
                        event_id=123, speakers=5, duration_ms=234)
    """
    # Create a log record with extra fields
    if context:
        logger.log(level, message, extra={'extra_fields': context})
    else:
        logger.log(level, message)


# Convenience functions for common log patterns
def log_phase_start(logger: logging.Logger, phase: str, **context):
    """Log the start of a pipeline phase"""
    log_with_context(logger, logging.INFO, f"Starting {phase} phase", phase=phase, **context)


def log_phase_complete(logger: logging.Logger, phase: str, **context):
    """Log successful completion of a pipeline phase"""
    log_with_context(logger, logging.INFO, f"✓ {phase} phase complete", phase=phase, **context)


def log_phase_failed(logger: logging.Logger, phase: str, error: str, **context):
    """Log failure of a pipeline phase"""
    log_with_context(logger, logging.ERROR, f"✗ {phase} phase failed",
                     phase=phase, error=error, **context)


def log_item_processed(logger: logging.Logger, item_type: str, item_name: str, **context):
    """Log successful processing of an item"""
    log_with_context(logger, logging.INFO, f"✓ Processed {item_type}: {item_name}",
                     item_type=item_type, item_name=item_name, **context)


def log_item_skipped(logger: logging.Logger, item_type: str, item_name: str, reason: str, **context):
    """Log when an item is skipped (WARNING level)"""
    log_with_context(logger, logging.WARNING, f"⚠ Skipped {item_type}: {item_name} - {reason}",
                     item_type=item_type, item_name=item_name, reason=reason, **context)


def log_item_failed(logger: logging.Logger, item_type: str, item_name: str, error: str, **context):
    """Log when an item fails to process (ERROR level)"""
    log_with_context(logger, logging.ERROR, f"✗ Failed {item_type}: {item_name} - {error}",
                     item_type=item_type, item_name=item_name, error=error, **context)


def log_retry(logger: logging.Logger, operation: str, attempt: int, max_attempts: int, **context):
    """Log retry attempts (WARNING level)"""
    log_with_context(logger, logging.WARNING,
                     f"⚠ Retrying {operation} (attempt {attempt}/{max_attempts})",
                     operation=operation, attempt=attempt, max_attempts=max_attempts, **context)


def log_api_call(logger: logging.Logger, service: str, operation: str, success: bool,
                 duration_ms: Optional[int] = None, **context):
    """Log API calls with timing and success status"""
    level = logging.INFO if success else logging.ERROR
    status = "✓" if success else "✗"
    msg = f"{status} API call: {service}.{operation}"

    extra = {'service': service, 'operation': operation, 'success': success, **context}
    if duration_ms is not None:
        extra['duration_ms'] = duration_ms

    log_with_context(logger, level, msg, **extra)


def log_stats(logger: logging.Logger, title: str, stats: Dict[str, Any]):
    """Log statistics/metrics"""
    msg = f"📊 {title}"
    log_with_context(logger, logging.INFO, msg, **stats)


# Pre-configured loggers for common components
pipeline_logger = setup_logging("pipeline")
extraction_logger = setup_logging("pipeline.extraction")
enrichment_logger = setup_logging("pipeline.enrichment")
embedding_logger = setup_logging("pipeline.embedding")
scraping_logger = setup_logging("pipeline.scraping")
web_logger = setup_logging("web")
db_logger = setup_logging("database")
