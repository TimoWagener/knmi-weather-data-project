"""
Bronze Refined Orchestration CLI

Coordinates parallel transformation of Bronze Raw (JSON) → Bronze Refined (Parquet)
for multiple stations. Uses ThreadPoolExecutor for concurrent processing.

Usage:
    python -m data_orchestration.bronze_refined.orchestrate --stations core_10 --start-year 1990 --end-year 2025
    python -m data_orchestration.bronze_refined.orchestrate --stations hupsel deelen --start-year 2024 --end-year 2024
"""

import argparse
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple

# Load station configuration
PROJECT_ROOT = Path(__file__).parent.parent.parent
STATIONS_CONFIG_PATH = PROJECT_ROOT / "metadata" / "stations_config.json"

with open(STATIONS_CONFIG_PATH, 'r') as f:
    stations_data = json.load(f)
    STATIONS = stations_data['stations']
    STATION_GROUPS = stations_data['station_groups']


def transform_station_range(station_key: str, start_year: int, end_year: int) -> Dict:
    """
    Transform a station's data for a range of years.

    Args:
        station_key: Station key (e.g., 'hupsel')
        start_year: Start year (inclusive)
        end_year: End year (inclusive)

    Returns:
        Dict with transformation results
    """
    from src.transform_bronze_refined import BronzeRefinedTransformer

    station = STATIONS[station_key]
    print(f"\n[{station['name']}] Starting transformation: {start_year}-{end_year}")

    start_time = time.time()
    transformer = BronzeRefinedTransformer(station_key)

    years_transformed = 0
    months_created = 0
    months_skipped = 0

    # Transform each year
    for year in range(start_year, end_year + 1):
        try:
            # Find files for this year
            files = transformer.find_bronze_raw_files(year=year)
            if not files:
                continue

            # Check idempotency before reading file
            months_to_transform = []
            for month in range(1, 13):
                if not transformer.month_already_transformed(year, month):
                    months_to_transform.append(month)

            if not months_to_transform:
                months_skipped += 12
                continue

            # Transform the year
            df = transformer.transform_file(files[0])
            if df is None or df.empty:
                continue

            # Save each month
            year_from_data = df['year'].iloc[0]
            for month in sorted(df['month'].unique()):
                if month not in months_to_transform:
                    months_skipped += 1
                    continue

                month_df = df[df['month'] == month].copy()
                month_df = month_df.drop(columns=['year', 'month'])

                output_path = transformer.get_output_path(year_from_data, month)
                month_df.to_parquet(output_path, index=False, engine='pyarrow',
                                   compression='snappy')
                months_created += 1

            years_transformed += 1

        except Exception as e:
            print(f"[{station['name']}] ERROR year {year}: {e}")
            continue

    duration = time.time() - start_time

    result = {
        'station_key': station_key,
        'station_name': station['name'],
        'years_transformed': years_transformed,
        'months_created': months_created,
        'months_skipped': months_skipped,
        'duration_seconds': round(duration, 2),
        'success': True
    }

    print(f"[{station['name']}] Complete: {years_transformed} years, "
          f"{months_created} new months, {months_skipped} skipped "
          f"({duration:.1f}s)")

    return result


def orchestrate(station_keys: List[str], start_year: int, end_year: int,
               max_workers: int = 10) -> List[Dict]:
    """
    Orchestrate parallel transformation of multiple stations.

    Args:
        station_keys: List of station keys to transform
        start_year: Start year (inclusive)
        end_year: End year (inclusive)
        max_workers: Number of concurrent workers

    Returns:
        List of transformation results
    """
    print("="*80)
    print("BRONZE REFINED ORCHESTRATION: Parallel Station Transformation")
    print("="*80)
    print(f"Stations: {len(station_keys)}")
    print(f"Year Range: {start_year}-{end_year}")
    print(f"Workers: {max_workers}")
    print("="*80)

    start_time = time.time()
    results = []

    # Use ThreadPoolExecutor for parallel processing
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all station transformations
        futures = {
            executor.submit(transform_station_range, station_key, start_year, end_year): station_key
            for station_key in station_keys
        }

        # Collect results as they complete
        for future in as_completed(futures):
            station_key = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                print(f"\n[ERROR] Station {station_key} failed: {e}")
                results.append({
                    'station_key': station_key,
                    'success': False,
                    'error': str(e)
                })

    total_duration = time.time() - start_time

    # Print summary
    print("\n" + "="*80)
    print("TRANSFORMATION COMPLETE")
    print("="*80)

    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]

    total_years = sum(r.get('years_transformed', 0) for r in successful)
    total_months = sum(r.get('months_created', 0) for r in successful)
    total_skipped = sum(r.get('months_skipped', 0) for r in successful)

    print(f"Stations: {len(successful)}/{len(results)} successful")
    print(f"Years Transformed: {total_years}")
    print(f"Months Created: {total_months}")
    print(f"Months Skipped: {total_skipped}")
    print(f"Total Duration: {total_duration:.1f}s")

    if failed:
        print(f"\n❌ Failed Stations ({len(failed)}):")
        for r in failed:
            print(f"  - {r['station_key']}: {r.get('error', 'Unknown error')}")

    print("="*80)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Orchestrate Bronze Refined transformation across multiple stations"
    )

    parser.add_argument(
        '--stations',
        nargs='+',
        help='Station keys or group name (e.g., hupsel deelen OR core_10)'
    )

    parser.add_argument(
        '--start-year',
        type=int,
        required=True,
        help='Start year (inclusive)'
    )

    parser.add_argument(
        '--end-year',
        type=int,
        required=True,
        help='End year (inclusive)'
    )

    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='Number of concurrent workers (default: 10)'
    )

    args = parser.parse_args()

    # Resolve station keys
    if len(args.stations) == 1 and args.stations[0] in STATION_GROUPS:
        # It's a group name
        station_keys = STATION_GROUPS[args.stations[0]]
        print(f"Using station group '{args.stations[0]}': {len(station_keys)} stations")
    else:
        # Individual station keys
        station_keys = args.stations
        # Validate all keys exist
        invalid = [k for k in station_keys if k not in STATIONS]
        if invalid:
            print(f"ERROR: Invalid station keys: {invalid}")
            print(f"Available: {list(STATIONS.keys())}")
            return

    # Run orchestration
    results = orchestrate(station_keys, args.start_year, args.end_year, args.workers)

    # Exit with error code if any stations failed
    if any(not r.get('success') for r in results):
        exit(1)


if __name__ == "__main__":
    main()
