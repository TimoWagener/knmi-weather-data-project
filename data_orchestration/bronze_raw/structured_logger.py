"""
Structured JSON Logging for Bronze Raw Ingestion

Provides both human-readable console logs and structured JSON logs for analysis.
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from .config import LOGS_DIR


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if provided
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class StructuredLogger:
    """
    Logger that outputs both human-readable and structured JSON logs.
    """

    def __init__(self, name: str):
        """
        Initialize structured logger.

        Args:
            name: Logger name
        """
        self.logger = logging.getLogger(name)
        self.json_log_file = None

    def setup_json_logging(self, log_file: Path):
        """
        Setup JSON logging to a separate file.

        Args:
            log_file: Path to JSON log file
        """
        self.json_log_file = log_file

        # Create JSON file handler
        json_handler = logging.FileHandler(log_file)
        json_handler.setLevel(logging.DEBUG)
        json_handler.setFormatter(JSONFormatter())

        self.logger.addHandler(json_handler)

    def log_event(self, level: str, message: str, **extra_data):
        """
        Log an event with structured data.

        Args:
            level: Log level (INFO, WARNING, ERROR, etc.)
            message: Human-readable message
            **extra_data: Additional structured data to log
        """
        # Create log record with extra data
        log_method = getattr(self.logger, level.lower())

        # Attach extra data to the record
        extra = {'extra_data': extra_data} if extra_data else {}

        log_method(message, extra=extra)

    def log_year_loaded(self, station_key: str, station_name: str, year: int,
                       file_path: str, size_mb: float, duration_sec: float):
        """
        Log a successfully loaded year with structured data.

        Args:
            station_key: Station identifier
            station_name: Station display name
            year: Year loaded
            file_path: Path to data file
            size_mb: File size in MB
            duration_sec: Time taken to load
        """
        self.log_event(
            'INFO',
            f"{station_name} {year} loaded successfully",
            event_type="year_loaded",
            station_key=station_key,
            station_name=station_name,
            year=year,
            file_path=file_path,
            file_size_mb=round(size_mb, 2),
            duration_seconds=round(duration_sec, 2)
        )

    def log_station_complete(self, station_key: str, station_name: str,
                            total_years: int, completed_years: int,
                            skipped_years: int, failed_years: int,
                            duration_sec: float):
        """
        Log station completion with structured data.

        Args:
            station_key: Station identifier
            station_name: Station display name
            total_years: Total years attempted
            completed_years: Years successfully loaded
            skipped_years: Years skipped (already existed)
            failed_years: Years that failed
            duration_sec: Total time taken
        """
        self.log_event(
            'INFO',
            f"{station_name} complete: {completed_years} loaded, {skipped_years} skipped",
            event_type="station_complete",
            station_key=station_key,
            station_name=station_name,
            total_years=total_years,
            completed_years=completed_years,
            skipped_years=skipped_years,
            failed_years=failed_years,
            duration_seconds=round(duration_sec, 2),
            success=failed_years == 0
        )

    def log_pipeline_complete(self, total_stations: int, successful_stations: int,
                             failed_stations: int, total_years_loaded: int,
                             total_years_skipped: int, duration_sec: float):
        """
        Log overall pipeline completion with structured data.

        Args:
            total_stations: Total stations processed
            successful_stations: Stations completed successfully
            failed_stations: Stations that failed
            total_years_loaded: Total years loaded across all stations
            total_years_skipped: Total years skipped across all stations
            duration_sec: Total pipeline duration
        """
        self.log_event(
            'INFO',
            f"Pipeline complete: {successful_stations}/{total_stations} stations succeeded",
            event_type="pipeline_complete",
            total_stations=total_stations,
            successful_stations=successful_stations,
            failed_stations=failed_stations,
            total_years_loaded=total_years_loaded,
            total_years_skipped=total_years_skipped,
            duration_seconds=round(duration_sec, 2),
            success=failed_stations == 0
        )
