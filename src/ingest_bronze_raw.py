"""
Bronze Raw Layer Ingestion: EDR API → JSON (Multi-Station Version)

Downloads weather data from KNMI EDR API with multi-station batching support.
Saves exact JSON responses to Bronze Raw layer (immutable source of truth).

Features:
- Multi-station queries (batch multiple stations per API call)
- Backward compatible with single-station queries
- Automatic response splitting by station
- Maintains same file structure as v1

Usage:
    # Single station (backward compatible)
    python ingest_bronze_raw_v2.py --station hupsel --year 2024

    # Multi-station batch (NEW!)
    python ingest_bronze_raw_v2.py --stations hupsel,deelen,de_bilt --year 2024

    # Custom date range with batch
    python ingest_bronze_raw_v2.py --stations hupsel,deelen --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests
import time
from typing import List, Dict, Optional, Tuple
from config import (
    EDR_API_KEY, EDR_BASE_URL, EDR_COLLECTION,
    BRONZE_RAW_DIR, STATIONS, DATE_RANGES, EDR_PARAMETERS
)


class BronzeRawIngesterV2:
    """Handles ingestion from EDR API to Bronze Raw layer with multi-station support"""

    def __init__(self, station_keys: List[str]):
        """
        Initialize ingester for one or more stations

        Args:
            station_keys: List of station keys (e.g., ["hupsel", "deelen"])
        """
        self.station_keys = station_keys
        self.station_configs = {key: STATIONS[key] for key in station_keys}
        self.station_ids = [STATIONS[key]["id"] for key in station_keys]
        self.headers = {"Authorization": EDR_API_KEY}

    def get_output_path(self, station_key: str, start_date: str, end_date: str) -> Path:
        """
        Generate output path for raw JSON file

        Args:
            station_key: Station identifier (e.g., "hupsel")
            start_date: Start date in ISO format
            end_date: End date in ISO format

        Returns:
            Path object for output file
        """
        # Parse dates to get year/month
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Create directory structure: bronze/raw/edr_api/station_id/year/
        year = start.year
        station_id = self.station_configs[station_key]["id"]
        station_dir = station_id.replace('-', '_')

        output_dir = BRONZE_RAW_DIR / "edr_api" / f"station_id={station_dir}" / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filename includes date range
        filename = f"{start.strftime('%Y%m%d')}_to_{end.strftime('%Y%m%d')}.json"
        return output_dir / filename

    def query_edr_api_multi_station(
        self,
        station_ids: List[str],
        start_date: str,
        end_date: str,
        parameters: Optional[List[str]] = None
    ) -> Dict:
        """
        Query EDR API for multiple stations in a single request

        Args:
            station_ids: List of station IDs (e.g., ["0-20000-0-06283", "0-20000-0-06275"])
            start_date: ISO format datetime string
            end_date: ISO format datetime string
            parameters: List of parameter names (None = all parameters)

        Returns:
            JSON response from API (CoverageCollection format)
        """
        # Join station IDs with commas for multi-station query
        location_param = ",".join(station_ids)
        datetime_range = f"{start_date}/{end_date}"

        # Build query parameters
        params = {"datetime": datetime_range}

        # Add specific parameters if requested
        if parameters:
            params["parameter-name"] = ",".join(parameters)

        # Construct URL
        url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{location_param}"

        print(f"Querying EDR API (Multi-Station)...")
        print(f"  Stations: {len(station_ids)} stations")
        for i, sid in enumerate(station_ids, 1):
            # Find station name
            station_name = "Unknown"
            for key, config in self.station_configs.items():
                if config["id"] == sid:
                    station_name = config["name"]
                    break
            print(f"    {i}. {station_name} ({sid})")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Parameters: {'All' if not parameters else ', '.join(parameters)}")

        # Make API request
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=120)
            response.raise_for_status()

            data = response.json()
            response_size = len(json.dumps(data))
            print(f"  [SUCCESS] Received response ({response_size:,} bytes)")

            # Check response type
            if data.get("type") == "CoverageCollection":
                num_coverages = len(data.get("coverages", []))
                print(f"  Response type: CoverageCollection ({num_coverages} coverages)")
            elif data.get("type") == "Coverage":
                print(f"  Response type: Coverage (single station)")
            else:
                print(f"  Response type: {data.get('type', 'Unknown')}")

            return data

        except requests.exceptions.HTTPError as e:
            print(f"  [ERROR] HTTP {e.response.status_code}: {e}")
            if hasattr(e.response, 'text'):
                print(f"  Response: {e.response.text[:200]}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Request failed: {e}")
            raise

    def split_coverage_collection(self, data: Dict) -> Dict[str, Dict]:
        """
        Split CoverageCollection response into individual station coverages

        Args:
            data: API response (CoverageCollection or single Coverage)

        Returns:
            Dictionary mapping station_id -> coverage data
        """
        result = {}

        # Check if it's a CoverageCollection (multi-station)
        if data.get("type") == "CoverageCollection":
            coverages = data.get("coverages", [])
            parameters = data.get("parameters", {})

            print(f"  Splitting CoverageCollection into {len(coverages)} station coverages...")

            for coverage in coverages:
                # Extract station ID from coverage
                station_id = coverage.get("eumetnet:locationId")

                if not station_id:
                    print(f"    [WARNING] Coverage missing 'eumetnet:locationId', skipping")
                    continue

                # Create single-station CoverageCollection format (same as v1 output)
                # IMPORTANT: Must wrap in CoverageCollection with array, even for single station
                station_data = {
                    "type": "CoverageCollection",
                    "domainType": data.get("domainType"),
                    "coverages": [coverage],  # Wrap single coverage in array for compatibility
                    "parameters": parameters,  # Shared parameters
                    "referencing": data.get("referencing", [])  # Shared referencing
                }

                result[station_id] = station_data
                print(f"    [OK] Extracted coverage for station {station_id}")

        # Single Coverage format (backward compatibility)
        elif data.get("type") == "Coverage":
            # For single station, try to determine station ID
            # (may not have eumetnet:locationId if only one station)
            # In this case, assume it's for the first/only station in our list
            station_id = self.station_ids[0] if len(self.station_ids) == 1 else None

            if station_id:
                result[station_id] = data
                print(f"  Single Coverage format (station: {station_id})")
            else:
                print(f"  [WARNING] Single Coverage but multiple stations requested")

        else:
            print(f"  [WARNING] Unexpected response type: {data.get('type')}")

        return result

    def save_bronze_raw(
        self,
        station_key: str,
        data: Dict,
        start_date: str,
        end_date: str
    ) -> Path:
        """
        Save raw JSON response to Bronze Raw layer

        Args:
            station_key: Station identifier
            data: Coverage data for this station
            start_date: Start date of data
            end_date: End date of data

        Returns:
            Path to saved file
        """
        output_path = self.get_output_path(station_key, start_date, end_date)

        # Add ingestion metadata
        metadata = {
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",
            "station_id": self.station_configs[station_key]["id"],
            "station_name": self.station_configs[station_key]["name"],
            "source_api": "KNMI EDR API",
            "api_collection": EDR_COLLECTION,
            "ingestion_method": "multi_station_batch" if len(self.station_keys) > 1 else "single_station"
        }

        # Combine metadata with raw data (same format as v1)
        bronze_raw = {
            "_metadata": metadata,
            "data": data
        }

        # Save as formatted JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(bronze_raw, f, indent=2, ensure_ascii=False)

        file_size = os.path.getsize(output_path)
        print(f"  [SAVED] {self.station_configs[station_key]['name']}: {output_path.name} ({file_size:,} bytes)")

        return output_path

    def generate_monthly_chunks(self, start_date_str: str, end_date_str: str) -> List[Dict]:
        """
        Generate monthly date ranges to avoid API limits

        Args:
            start_date_str: Start date in ISO format
            end_date_str: End date in ISO format

        Returns:
            List of chunk dictionaries with start, end, and month
        """
        start = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))

        chunks = []
        current = start

        while current < end:
            # Calculate chunk end (end of current month)
            if current.month == 12:
                chunk_end = current.replace(year=current.year + 1, month=1, day=1) - timedelta(seconds=1)
            else:
                chunk_end = current.replace(month=current.month + 1, day=1) - timedelta(seconds=1)

            # Don't exceed overall end date
            if chunk_end > end:
                chunk_end = end

            chunks.append({
                "start": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": chunk_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "month": current.strftime("%Y-%m")
            })

            # Move to next month (always use day=1 to avoid "day is out of range" errors)
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1)
            else:
                current = current.replace(month=current.month + 1, day=1)

        return chunks

    def ingest(
        self,
        date_range_key: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        parameters: Optional[List[str]] = None
    ) -> Dict[str, List[Path]]:
        """
        Main ingestion pipeline with multi-station support

        Args:
            date_range_key: Key from DATE_RANGES config (e.g., 'full', '2024')
            start_date: Custom start date in ISO format (overrides date_range_key)
            end_date: Custom end date in ISO format (overrides date_range_key)
            parameters: List of parameters to query (None = all)

        Returns:
            Dictionary mapping station_key -> list of saved file paths
        """
        print("="*80)
        print("BRONZE RAW INGESTION: EDR API -> JSON (Multi-Station v2)")
        print("="*80)

        # Determine date range
        if start_date and end_date:
            print(f"Using custom date range")
        elif date_range_key:
            date_range = DATE_RANGES[date_range_key]
            start_date = date_range["start"]
            end_date = date_range["end"]
        else:
            print("No date range specified, using default: 'full'")
            date_range = DATE_RANGES["full"]
            start_date = date_range["start"]
            end_date = date_range["end"]

        # Generate monthly chunks
        chunks = self.generate_monthly_chunks(start_date, end_date)
        print(f"\nDate range: {start_date} to {end_date}")
        print(f"Split into {len(chunks)} monthly chunks")
        print(f"Stations per batch: {len(self.station_keys)}")
        print(f"Total API calls: {len(chunks)} (vs {len(chunks) * len(self.station_keys)} single-station)\n")

        saved_files = {key: [] for key in self.station_keys}

        # Process each chunk (one API call per chunk, covers all stations)
        for i, chunk in enumerate(chunks, 1):
            print(f"[{i}/{len(chunks)}] Processing {chunk['month']}...")

            try:
                # Single API call for all stations in this chunk
                data = self.query_edr_api_multi_station(
                    self.station_ids,
                    chunk["start"],
                    chunk["end"],
                    parameters
                )

                # Split response by station
                station_coverages = self.split_coverage_collection(data)

                # Save each station's data separately
                for station_id, coverage_data in station_coverages.items():
                    # Find station key for this ID
                    station_key = None
                    for key, config in self.station_configs.items():
                        if config["id"] == station_id:
                            station_key = key
                            break

                    if station_key:
                        output_path = self.save_bronze_raw(
                            station_key,
                            coverage_data,
                            chunk["start"],
                            chunk["end"]
                        )
                        saved_files[station_key].append(output_path)
                    else:
                        print(f"  [WARNING] Station ID {station_id} not in configured stations")

                # No delay needed - API supports 200 req/sec, we're well below that

            except Exception as e:
                print(f"  [ERROR] Failed to process {chunk['month']}: {e}")
                import traceback
                traceback.print_exc()
                continue

        print("\n" + "="*80)
        print(f"[COMPLETE] Bronze Raw ingestion finished")
        for station_key, files in saved_files.items():
            print(f"  {self.station_configs[station_key]['name']}: {len(files)} files")
        print("="*80)

        return saved_files


def main():
    parser = argparse.ArgumentParser(
        description="Ingest weather data to Bronze Raw layer (Multi-Station v2)"
    )

    # Station selection (mutually exclusive)
    station_group = parser.add_mutually_exclusive_group(required=True)
    station_group.add_argument(
        "--station",
        type=str,
        help="Single station to ingest (e.g., hupsel)"
    )
    station_group.add_argument(
        "--stations",
        type=str,
        help="Comma-separated list of stations (e.g., hupsel,deelen,de_bilt)"
    )

    # Date range selection
    parser.add_argument(
        "--date-range",
        choices=list(DATE_RANGES.keys()),
        help="Date range to ingest (e.g., full, 2024, 2025)"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Custom start date in ISO format (e.g., 2020-01-01T00:00:00Z)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Custom end date in ISO format (e.g., 2020-12-31T23:59:59Z)"
    )

    # Parameters
    parser.add_argument(
        "--parameters",
        nargs="+",
        help="Specific parameters to query (default: all)"
    )

    args = parser.parse_args()

    # Determine station list
    if args.station:
        station_keys = [args.station]
    else:
        station_keys = [s.strip() for s in args.stations.split(",")]

    # Validate stations
    invalid_stations = [s for s in station_keys if s not in STATIONS]
    if invalid_stations:
        print(f"Error: Invalid stations: {', '.join(invalid_stations)}")
        print(f"Available stations: {', '.join(STATIONS.keys())}")
        return

    # Run ingestion
    ingester = BronzeRawIngesterV2(station_keys)
    ingester.ingest(
        date_range_key=args.date_range,
        start_date=args.start_date,
        end_date=args.end_date,
        parameters=args.parameters
    )


if __name__ == "__main__":
    main()
