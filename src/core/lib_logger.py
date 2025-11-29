"""Structured logging configuration for Bablib."""

import json
import logging
import logging.config
import sys
from datetime import datetime
from typing import Any

from rich.console import Console
from rich.logging import RichHandler

from .config import BablibConfig


class StructuredFormatter(logging.Formatter):
    """Custom formatter that outputs structured JSON logs."""

    def __init__(self, include_fields: list | None = None):
        """Initialize with optional field filtering."""
        super().__init__()
        self.include_fields = include_fields or [
            "timestamp", "level", "logger", "message", "module", "function"
        ]

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_entry = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields from the log record
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "levelname", "levelno", "pathname",
                          "filename", "module", "lineno", "funcName", "created",
                          "msecs", "relativeCreated", "thread", "threadName",
                          "processName", "process", "getMessage", "exc_info",
                          "exc_text", "stack_info"]:
                log_entry[key] = value

        # Filter fields if specified
        if self.include_fields:
            filtered_entry = {k: v for k, v in log_entry.items()
                            if k in self.include_fields or k.startswith("extra_")}
            log_entry = filtered_entry

        return json.dumps(log_entry, default=str)


class BablibLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds Bablib-specific context."""

    def __init__(self, logger: logging.Logger, extra: dict[str, Any]):
        """Initialize with logger and extra context."""
        super().__init__(logger, extra)

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple:
        """Process log message and add extra context."""
        extra = kwargs.get("extra", {})
        extra.update(self.extra)
        kwargs["extra"] = extra
        return msg, kwargs

    def with_context(self, **context) -> "BablibLoggerAdapter":
        """Create new adapter with additional context."""
        new_extra = self.extra.copy()
        new_extra.update(context)
        return BablibLoggerAdapter(self.logger, new_extra)


class LoggingManager:
    """Manage logging configuration for Bablib."""

    def __init__(self, config: BablibConfig):
        """Initialize logging manager with configuration."""
        self.config = config
        self.console = Console(stderr=True)
        self._configured = False

    def setup_logging(self) -> None:
        """Set up logging configuration based on settings."""
        if self._configured:
            return

        # Create logs directory
        self.config.logs_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.config.log_level.upper())

        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Set up console handler with Rich formatting
        console_handler = RichHandler(
            console=self.console,
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=self.config.debug
        )
        console_handler.setLevel(self.config.log_level.upper())

        # Use simple format for console in debug mode, structured otherwise
        if self.config.debug:
            console_format = "%(asctime)s [%(levelname)8s] %(name)s: %(message)s"
            console_handler.setFormatter(logging.Formatter(console_format))
        else:
            # Rich handler has its own formatting
            pass

        root_logger.addHandler(console_handler)

        # Set up file handler with structured logging
        if self.config.log_file or self.config.logs_dir:
            log_file = self.config.log_file or (self.config.logs_dir / "bablib.log")
            file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)  # Always log everything to file

            # Use structured formatter for file logs
            structured_formatter = StructuredFormatter()
            file_handler.setFormatter(structured_formatter)
            root_logger.addHandler(file_handler)

        # Set up separate error log file
        error_log_file = self.config.logs_dir / "bablib-errors.log"
        error_handler = logging.FileHandler(error_log_file, mode="a", encoding="utf-8")
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(StructuredFormatter())
        root_logger.addHandler(error_handler)

        # Configure third-party library logging
        self._configure_third_party_logging()

        self._configured = True

    def _configure_third_party_logging(self) -> None:
        """Configure logging for third-party libraries."""
        # Reduce noise from third-party libraries
        library_loggers = {
            "httpx": logging.WARNING,
            "httpcore": logging.WARNING,
            "qdrant_client": logging.INFO,
            "scrapy": logging.INFO,
            "twisted": logging.WARNING,
            "urllib3": logging.WARNING,
            "docker": logging.WARNING,
            "langchain": logging.INFO,
            "langchain_community": logging.WARNING,
        }

        for logger_name, level in library_loggers.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

    def get_logger(self, name: str, **context) -> BablibLoggerAdapter:
        """Get a logger with Bablib-specific context."""
        if not self._configured:
            self.setup_logging()

        logger = logging.getLogger(name)
        return BablibLoggerAdapter(logger, context)

    def get_component_logger(self, component: str, **context) -> BablibLoggerAdapter:
        """Get a logger for a specific Bablib component."""
        logger_name = f"bablib.{component}"
        context["component"] = component
        return self.get_logger(logger_name, **context)

    def log_system_info(self) -> None:
        """Log system information at startup."""
        import platform

        logger = self.get_logger("bablib.system")

        system_info = {
            "python_version": sys.version,
            "platform": platform.platform(),
            "architecture": platform.architecture(),
            "processor": platform.processor(),
            "bablib_config": {
                "data_dir": str(self.config.data_dir),
                "debug": self.config.debug,
                "log_level": self.config.log_level,
                "deployment_strategy": self.config.get_effective_deployment_strategy(),
            }
        }

        logger.info("Bablib starting up", extra={"system_info": system_info})

    def log_service_status(self, service_status: dict[str, bool]) -> None:
        """Log service connectivity status."""
        logger = self.get_logger("bablib.services")

        for service, is_healthy in service_status.items():
            if is_healthy:
                logger.info(f"{service} service is healthy", extra={"service": service, "status": "healthy"})
            else:
                logger.warning(f"{service} service is unhealthy", extra={"service": service, "status": "unhealthy"})

    def setup_crawl_logging(self, project_name: str, crawl_id: str) -> BablibLoggerAdapter:
        """Set up logging for a crawl session."""
        crawl_log_file = self.config.logs_dir / f"crawl-{project_name}-{crawl_id}.log"

        # Create a specific logger for this crawl
        crawl_logger = logging.getLogger(f"bablib.crawl.{project_name}")

        # Add file handler for crawl-specific logs
        crawl_handler = logging.FileHandler(crawl_log_file, mode="w", encoding="utf-8")
        crawl_handler.setLevel(logging.DEBUG)
        crawl_handler.setFormatter(StructuredFormatter())
        crawl_logger.addHandler(crawl_handler)

        return BablibLoggerAdapter(crawl_logger, {
            "project": project_name,
            "crawl_id": crawl_id
        })

    def cleanup_old_logs(self, days: int = 30) -> None:
        """Clean up log files older than specified days."""
        import time

        logger = self.get_logger("bablib.cleanup")
        cutoff_time = time.time() - (days * 24 * 60 * 60)
        cleaned_count = 0

        for log_file in self.config.logs_dir.glob("*.log"):
            try:
                if log_file.stat().st_mtime < cutoff_time:
                    log_file.unlink()
                    cleaned_count += 1
                    logger.debug(f"Deleted old log file: {log_file}")
            except OSError as e:
                logger.warning(f"Failed to delete log file {log_file}: {e}")

        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} old log files")


# Global logging manager instance
_logging_manager: LoggingManager | None = None


def setup_logging(config: BablibConfig) -> LoggingManager:
    """Set up global logging configuration."""
    global _logging_manager
    _logging_manager = LoggingManager(config)
    _logging_manager.setup_logging()
    return _logging_manager


def get_logger(name: str, **context) -> BablibLoggerAdapter:
    """Get a logger instance."""
    if _logging_manager is None:
        # Fallback if logging not configured
        from .config import get_config
        setup_logging(get_config())

    return _logging_manager.get_logger(name, **context)


def get_component_logger(component: str, **context) -> BablibLoggerAdapter:
    """Get a component-specific logger."""
    if _logging_manager is None:
        from .config import get_config
        setup_logging(get_config())

    return _logging_manager.get_component_logger(component, **context)
