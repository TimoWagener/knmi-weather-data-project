"""
Bronze Raw Orchestrator

Parallel ingestion of multiple stations using independent station pipelines.
Each station runs in its own thread for maximum efficiency.
"""
import sys
import argparse
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from .config import (
    CORE_10_STATIONS,
    MAX_CONCURRENT_STATIONS,
    LOGS_DIR,
    LOG_FORMAT,
    LOG_DATE_FORMAT
)
from .station_pipeline import StationPipeline
from .api_client import test_api_connection
from .structured_logger import StructuredLogger


def setup_logging(verbose: bool = False):
    """
    Configure logging for the orchestrator.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO

    Returns:
        Tuple of (human log file path, JSON log file path)
    """
    level = logging.DEBUG if verbose else logging.INFO

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Also log to file (human-readable)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOGS_DIR / f"bronze_raw_orchestrator_{timestamp}.log"
    json_log_file = LOGS_DIR / f"bronze_raw_orchestrator_{timestamp}.json"

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    logging.getLogger().addHandler(file_handler)

    # Setup structured JSON logging
    structured_logger = StructuredLogger('orchestrator')
    structured_logger.setup_json_logging(json_log_file)

    # Import station pipeline logger and setup its JSON logging too
    from .station_pipeline import structured_logger as pipeline_logger
    pipeline_logger.setup_json_logging(json_log_file)

    logging.info(f"Logging to: {log_file}")
    logging.info(f"JSON logs: {json_log_file}")

    return log_file, json_log_file


def load_station(station_key: str, start_year: int, end_year: int, skip_existing: bool) -> Dict[str, Any]:
    """
    Load historical data for a single station.

    This function is designed to run in a thread pool.

    Args:
        station_key: Station identifier
        start_year: First year to load
        end_year: Last year to load
        skip_existing: Whether to skip already-loaded years

    Returns:
        Summary dictionary from StationPipeline
    """
    pipeline = StationPipeline(station_key, skip_existing=skip_existing)
    return pipeline.load_historical(start_year, end_year)


def orchestrate_bronze_raw(
    stations: List[str],
    start_year: int,
    end_year: int,
    skip_existing: bool = True,
    max_workers: int = MAX_CONCURRENT_STATIONS
) -> Dict[str, Any]:
    """
    Orchestrate parallel ingestion for multiple stations.

    Each station runs in an independent thread, loading its data
    from start_year to end_year using 1-year chunks.

    Args:
        stations: List of station keys to load
        start_year: First year to load
        end_year: Last year to load
        skip_existing: Skip years that already exist
        max_workers: Maximum concurrent station threads

    Returns:
        Summary dictionary with results for all stations
    """
    logger = logging.getLogger(__name__)

    start_time = datetime.now()

    logger.info("="*80)
    logger.info("BRONZE RAW INGESTION - PARALLEL STATION LOADING")
    logger.info("="*80)
    logger.info(f"Stations: {len(stations)} ({', '.join(stations)})")
    logger.info(f"Years: {start_year}-{end_year} ({end_year - start_year + 1} years each)")
    logger.info(f"Concurrent workers: {max_workers}")
    logger.info(f"Skip existing: {skip_existing}")
    logger.info("="*80)

    # Test API connection first
    logger.info("Testing API connection...")
    if not test_api_connection():
        logger.error("API connection test failed. Aborting.")
        return {'success': False, 'error': 'API connection test failed'}

    # Create thread pool and submit all station jobs
    station_results = {}
    failed_stations = []

    logger.info(f"\nStarting parallel ingestion ({max_workers} workers)...\n")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all station jobs
        future_to_station = {
            executor.submit(load_station, station, start_year, end_year, skip_existing): station
            for station in stations
        }

        # Process results as they complete
        for future in as_completed(future_to_station):
            station = future_to_station[future]
            try:
                result = future.result()
                station_results[station] = result

                if not result['success']:
                    failed_stations.append(station)

            except Exception as e:
                logger.error(f"[FAIL] {station} pipeline crashed: {e}")
                failed_stations.append(station)
                station_results[station] = {
                    'station_key': station,
                    'success': False,
                    'error': str(e)
                }

    elapsed = (datetime.now() - start_time).total_seconds()

    # Calculate summary statistics
    total_stations = len(stations)
    successful_stations = total_stations - len(failed_stations)
    total_years_completed = sum(r.get('completed_years', 0) for r in station_results.values())
    total_years_skipped = sum(r.get('skipped_years', 0) for r in station_results.values())

    # Build final summary
    summary = {
        'success': len(failed_stations) == 0,
        'total_stations': total_stations,
        'successful_stations': successful_stations,
        'failed_stations': failed_stations,
        'total_years_completed': total_years_completed,
        'total_years_skipped': total_years_skipped,
        'elapsed_seconds': round(elapsed, 2),
        'station_results': station_results
    }

    # Print final summary
    logger.info("\n" + "="*80)
    logger.info("INGESTION COMPLETE")
    logger.info("="*80)
    logger.info(f"Total stations: {total_stations}")
    logger.info(f"Successful: {successful_stations}")
    logger.info(f"Failed: {len(failed_stations)}")
    if failed_stations:
        logger.warning(f"Failed stations: {', '.join(failed_stations)}")
    logger.info(f"Years loaded: {total_years_completed}")
    logger.info(f"Years skipped: {total_years_skipped}")
    logger.info(f"Total time: {elapsed:.1f}s ({elapsed/60:.1f} minutes)")
    if total_years_completed > 0:
        logger.info(f"Average time per year: {elapsed/total_years_completed:.2f}s")
    logger.info("="*80)

    if summary['success']:
        logger.info("\n[SUCCESS] ALL STATIONS LOADED SUCCESSFULLY!")
    else:
        logger.warning(f"\n[WARN] COMPLETED WITH {len(failed_stations)} FAILURES")

    # Structured logging for pipeline summary
    structured_logger = StructuredLogger('orchestrator')
    structured_logger.log_pipeline_complete(
        total_stations=total_stations,
        successful_stations=successful_stations,
        failed_stations=len(failed_stations),
        total_years_loaded=total_years_completed,
        total_years_skipped=total_years_skipped,
        duration_sec=elapsed
    )

    return summary


def main():
    """CLI entry point for bronze raw orchestrator"""
    parser = argparse.ArgumentParser(
        description="Bronze Raw Ingestion - Parallel Station Loading",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Load single station (2000-2025)
  python -m data_orchestration.bronze_raw.orchestrate --station hupsel --start-year 2000 --end-year 2025

  # Load all 10 core stations (2000-2025)
  python -m data_orchestration.bronze_raw.orchestrate --stations core_10 --start-year 2000 --end-year 2025

  # Load specific stations
  python -m data_orchestration.bronze_raw.orchestrate --stations hupsel,deelen,de_bilt --start-year 2024 --end-year 2025

  # Test with single year
  python -m data_orchestration.bronze_raw.orchestrate --station hupsel --start-year 2024 --end-year 2024
        """
    )

    parser.add_argument(
        '--station',
        type=str,
        help='Single station to load (e.g., "hupsel")'
    )

    parser.add_argument(
        '--stations',
        type=str,
        help='Comma-separated list of stations or "core_10" for all 10 core stations'
    )

    parser.add_argument(
        '--start-year',
        type=int,
        required=True,
        help='First year to load (e.g., 2000)'
    )

    parser.add_argument(
        '--end-year',
        type=int,
        required=True,
        help='Last year to load (e.g., 2025)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Force reload (do not skip existing files)'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=MAX_CONCURRENT_STATIONS,
        help=f'Maximum concurrent station workers (default: {MAX_CONCURRENT_STATIONS})'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    # Determine which stations to load
    if args.station and args.stations:
        print("Error: Cannot specify both --station and --stations")
        sys.exit(1)

    if not args.station and not args.stations:
        print("Error: Must specify either --station or --stations")
        sys.exit(1)

    if args.station:
        stations = [args.station]
    elif args.stations == 'core_10':
        stations = CORE_10_STATIONS
    else:
        stations = [s.strip() for s in args.stations.split(',')]

    # Validate years
    if args.start_year > args.end_year:
        print(f"Error: start-year ({args.start_year}) cannot be after end-year ({args.end_year})")
        sys.exit(1)

    # Run orchestrator
    summary = orchestrate_bronze_raw(
        stations=stations,
        start_year=args.start_year,
        end_year=args.end_year,
        skip_existing=not args.force,
        max_workers=args.max_workers
    )

    # Exit with error code if failures
    sys.exit(0 if summary['success'] else 1)


if __name__ == "__main__":
    main()
