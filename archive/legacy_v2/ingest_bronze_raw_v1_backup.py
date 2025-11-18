"""
Bronze Raw Layer Ingestion: EDR API → JSON

Downloads weather data from KNMI EDR API and saves exact JSON responses
to Bronze Raw layer. This is the immutable source of truth.

Usage:
    python ingest_bronze_raw.py --station hupsel --year 2024
    python ingest_bronze_raw.py --station hupsel --date-range full
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import requests
import time
from config import (
    EDR_API_KEY, EDR_BASE_URL, EDR_COLLECTION,
    BRONZE_RAW_DIR, STATIONS, DATE_RANGES, EDR_PARAMETERS
)

class BronzeRawIngester:
    """Handles ingestion from EDR API to Bronze Raw layer"""

    def __init__(self, station_key):
        self.station_key = station_key
        self.station_config = STATIONS[station_key]
        self.station_id = self.station_config["id"]
        self.headers = {"Authorization": EDR_API_KEY}

    def get_output_path(self, start_date, end_date):
        """Generate output path for raw JSON file"""
        # Parse dates to get year/month
        start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))

        # Create directory structure: bronze/raw/edr_api/station_id/year/
        year = start.year
        station_dir = self.station_id.replace('-', '_')

        output_dir = BRONZE_RAW_DIR / "edr_api" / f"station_id={station_dir}" / f"year={year}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Filename includes date range
        filename = f"{start.strftime('%Y%m%d')}_to_{end.strftime('%Y%m%d')}.json"
        return output_dir / filename

    def query_edr_api(self, start_date, end_date, parameters=None):
        """
        Query EDR API for station data

        Args:
            start_date: ISO format datetime string
            end_date: ISO format datetime string
            parameters: List of parameter names (None = all parameters)

        Returns:
            JSON response from API
        """
        datetime_range = f"{start_date}/{end_date}"

        # Build query parameters
        params = {
            "datetime": datetime_range
        }

        # Add specific parameters if requested
        if parameters:
            params["parameter-name"] = ",".join(parameters)

        # Construct URL
        url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{self.station_id}"

        print(f"Querying EDR API...")
        print(f"  Station: {self.station_config['name']} ({self.station_id})")
        print(f"  Date range: {start_date} to {end_date}")
        print(f"  Parameters: {'All' if not parameters else ', '.join(parameters)}")
        print(f"  URL: {url}")

        # Make API request
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=60)
            response.raise_for_status()

            data = response.json()
            print(f"  [SUCCESS] Received response ({len(json.dumps(data))} bytes)")
            return data

        except requests.exceptions.HTTPError as e:
            print(f"  [ERROR] HTTP {e.response.status_code}: {e}")
            if hasattr(e.response, 'text'):
                print(f"  Response: {e.response.text[:200]}")
            raise
        except requests.exceptions.RequestException as e:
            print(f"  [ERROR] Request failed: {e}")
            raise

    def save_bronze_raw(self, data, output_path):
        """Save raw JSON response to Bronze Raw layer"""
        print(f"Saving to Bronze Raw: {output_path}")

        # Add ingestion metadata
        metadata = {
            "ingestion_timestamp": datetime.utcnow().isoformat() + "Z",
            "station_id": self.station_id,
            "station_name": self.station_config["name"],
            "source_api": "KNMI EDR API",
            "api_collection": EDR_COLLECTION
        }

        # Combine metadata with raw data
        bronze_raw = {
            "_metadata": metadata,
            "data": data
        }

        # Save as formatted JSON
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(bronze_raw, f, indent=2, ensure_ascii=False)

        file_size = os.path.getsize(output_path)
        print(f"  [SUCCESS] Saved {file_size:,} bytes")

        return output_path

    def generate_monthly_chunks(self, start_date_str, end_date_str):
        """
        Generate monthly date ranges to avoid API limits

        EDR API has a limit on data points per request.
        Chunking by month keeps requests manageable.
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

    def ingest(self, date_range_key=None, start_date=None, end_date=None, parameters=None):
        """
        Main ingestion pipeline with chunking

        Args:
            date_range_key: Key from DATE_RANGES config (e.g., 'full', '2024')
            start_date: Custom start date in ISO format (overrides date_range_key)
            end_date: Custom end date in ISO format (overrides date_range_key)
            parameters: List of parameters to query (None = all)
        """
        print("="*80)
        print("BRONZE RAW INGESTION: EDR API -> JSON")
        print("="*80)

        # Determine date range: custom dates take precedence
        if start_date and end_date:
            # Use custom dates (already provided)
            print(f"Using custom date range")
        elif date_range_key:
            # Get date range from config
            date_range = DATE_RANGES[date_range_key]
            start_date = date_range["start"]
            end_date = date_range["end"]
        else:
            # Default to 'full'
            print("No date range specified, using default: 'full'")
            date_range = DATE_RANGES["full"]
            start_date = date_range["start"]
            end_date = date_range["end"]

        # Generate monthly chunks to avoid API limits
        chunks = self.generate_monthly_chunks(start_date, end_date)
        print(f"\nDate range split into {len(chunks)} monthly chunks to avoid API limits")
        print(f"Date range: {start_date} to {end_date}\n")

        saved_files = []

        # Process each chunk
        for i, chunk in enumerate(chunks, 1):
            print(f"[{i}/{len(chunks)}] Processing {chunk['month']}...")

            try:
                # Query API for this chunk
                data = self.query_edr_api(chunk["start"], chunk["end"], parameters)

                # Save to Bronze Raw
                output_path = self.get_output_path(chunk["start"], chunk["end"])
                self.save_bronze_raw(data, output_path)
                saved_files.append(output_path)

                # Small delay to be respectful to API
                if i < len(chunks):
                    time.sleep(0.5)

            except Exception as e:
                print(f"  [ERROR] Failed to process {chunk['month']}: {e}")
                continue

        print("\n" + "="*80)
        print(f"[COMPLETE] Bronze Raw ingestion finished")
        print(f"Successfully saved {len(saved_files)} files")
        print("="*80)

        return saved_files


def main():
    parser = argparse.ArgumentParser(description="Ingest weather data to Bronze Raw layer")
    parser.add_argument(
        "--station",
        choices=list(STATIONS.keys()),
        default="hupsel",
        help="Station to ingest (default: hupsel)"
    )
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
    parser.add_argument(
        "--parameters",
        nargs="+",
        help="Specific parameters to query (default: all)"
    )

    args = parser.parse_args()

    # Run ingestion with custom dates or predefined range
    ingester = BronzeRawIngester(args.station)
    ingester.ingest(
        date_range_key=args.date_range,
        start_date=args.start_date,
        end_date=args.end_date,
        parameters=args.parameters
    )


if __name__ == "__main__":
    main()
