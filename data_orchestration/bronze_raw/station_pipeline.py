"""
Station Pipeline - Independent Station Ingestion

Each station is loaded independently using 1-year chunks.
This allows parallel processing of multiple stations.
"""
import logging
import time
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from .api_client import fetch_station_year
from .storage import atomic_write_json, get_output_path, file_exists
from .config import get_station_id, get_station_name
from .metadata_tracker import StationMetadata
from .structured_logger import StructuredLogger

logger = logging.getLogger(__name__)
structured_logger = StructuredLogger(__name__)


class StationPipeline:
    """
    Independent pipeline for loading historical data for a single station.

    Handles:
    - Calculating yearly chunks from start_year to end_year
    - Fetching each year from EDR API
    - Writing data atomically to bronze raw layer
    - Tracking progress and errors
    - Resume capability (skips already-loaded years)
    """

    def __init__(self, station_key: str, skip_existing: bool = True):
        """
        Initialize pipeline for a station.

        Args:
            station_key: Station identifier (e.g., "hupsel", "deelen")
            skip_existing: If True, skip years that already exist (default: True)
        """
        self.station_key = station_key
        self.station_id = get_station_id(station_key)
        self.station_name = get_station_name(station_key)
        self.skip_existing = skip_existing

        # Load metadata tracker
        self.metadata = StationMetadata(station_key)

        self.total_years = 0
        self.completed_years = 0
        self.skipped_years = 0
        self.failed_years = []

        logger.info(f"Initialized pipeline for {self.station_name} ({self.station_id})")

    def load_historical(self, start_year: int, end_year: int) -> Dict[str, Any]:
        """
        Load historical data for the station from start_year to end_year.

        Each year is fetched as a separate API call and stored in:
        data/bronze/raw/edr_api/station_id={id}/year={year}/data.json

        Args:
            start_year: First year to load (e.g., 2000)
            end_year: Last year to load (e.g., 2025)

        Returns:
            Summary dictionary with:
                - total_years: Number of years attempted
                - completed_years: Number successfully loaded
                - skipped_years: Number skipped (already existed)
                - failed_years: List of years that failed
                - success: True if all years succeeded
        """
        years = list(range(start_year, end_year + 1))
        self.total_years = len(years)

        logger.info(f"Loading {self.station_name}: {start_year}-{end_year} "
                   f"({self.total_years} years)")

        start_time = datetime.now()

        for year in years:
            try:
                self._load_year(year)
            except Exception as e:
                logger.error(f"Failed to load {self.station_name} year {year}: {e}")
                self.failed_years.append(year)

        elapsed = (datetime.now() - start_time).total_seconds()

        # Build summary
        summary = {
            'station_key': self.station_key,
            'station_name': self.station_name,
            'start_year': start_year,
            'end_year': end_year,
            'total_years': self.total_years,
            'completed_years': self.completed_years,
            'skipped_years': self.skipped_years,
            'failed_years': self.failed_years,
            'success': len(self.failed_years) == 0,
            'elapsed_seconds': round(elapsed, 2)
        }

        # Log summary
        if summary['success']:
            logger.info(f"[OK] {self.station_name} complete: "
                       f"{self.completed_years} loaded, "
                       f"{self.skipped_years} skipped, "
                       f"{elapsed:.1f}s")
        else:
            logger.warning(f"[WARN] {self.station_name} completed with errors: "
                          f"{self.completed_years} loaded, "
                          f"{self.skipped_years} skipped, "
                          f"{len(self.failed_years)} failed")

        # Structured logging
        structured_logger.log_station_complete(
            station_key=self.station_key,
            station_name=self.station_name,
            total_years=self.total_years,
            completed_years=self.completed_years,
            skipped_years=self.skipped_years,
            failed_years=len(self.failed_years),
            duration_sec=elapsed
        )

        return summary

    def _load_year(self, year: int) -> None:
        """
        Load a single year of data.

        Steps:
        1. Check metadata if already loaded (skip if skip_existing=True)
        2. Fetch from API
        3. Write atomically to storage
        4. Update metadata
        5. Update counters

        Args:
            year: Year to load

        Raises:
            Exception: If fetch or write fails
        """
        # Check metadata if already loaded
        if self.skip_existing and self.metadata.is_year_loaded(year):
            logger.debug(f"  Skipping {self.station_name} {year} (already in metadata)")
            self.skipped_years += 1
            return

        # Fetch from API
        logger.info(f"  Fetching {self.station_name} {year}...")
        year_start_time = time.time()

        data = fetch_station_year(self.station_id, year)

        # Write atomically
        output_path = get_output_path(self.station_id, year)
        atomic_write_json(data, output_path)

        # Get file size for metadata
        file_size_bytes = output_path.stat().st_size
        file_size_mb = file_size_bytes / (1024 * 1024)

        # Calculate duration
        year_duration = time.time() - year_start_time

        # Mark as loaded in metadata with file details
        self.metadata.mark_year_loaded(year, file_path=str(output_path), size_mb=file_size_mb)

        # Log with structured data
        logger.info(f"  [OK] {self.station_name} {year} -> {output_path} ({file_size_mb:.2f} MB, {year_duration:.1f}s)")

        structured_logger.log_year_loaded(
            station_key=self.station_key,
            station_name=self.station_name,
            year=year,
            file_path=str(output_path),
            size_mb=file_size_mb,
            duration_sec=year_duration
        )

        self.completed_years += 1

    def get_summary(self) -> Dict[str, Any]:
        """
        Get current pipeline status summary.

        Returns:
            Dictionary with current counts and status
        """
        return {
            'station_key': self.station_key,
            'station_name': self.station_name,
            'total_years': self.total_years,
            'completed_years': self.completed_years,
            'skipped_years': self.skipped_years,
            'failed_years': self.failed_years,
            'success': len(self.failed_years) == 0
        }
