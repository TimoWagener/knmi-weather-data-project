"""
Bronze Refined Layer Transformation: JSON -> Parquet (Schema-on-Read)

Flattens Bronze Raw JSON into Parquet format for efficient querying.
Uses schema-on-read approach - no fixed schema enforcement.
All fields from source are preserved dynamically.

Usage:
    python transform_bronze_refined.py --station hupsel --year 2024
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
from config import BRONZE_RAW_DIR, BRONZE_REFINED_DIR, STATIONS


class BronzeRefinedTransformer:
    """Transforms Bronze Raw JSON to Bronze Refined Parquet"""

    def __init__(self, station_key):
        self.station_key = station_key
        self.station_config = STATIONS[station_key]
        self.station_id = self.station_config["id"]

    def find_bronze_raw_files(self, year=None):
        """Find all Bronze Raw JSON files for this station"""
        station_dir = self.station_id.replace('-', '_')
        base_path = BRONZE_RAW_DIR / "edr_api" / f"station_id={station_dir}"

        if year:
            search_path = base_path / f"year={year}"
        else:
            search_path = base_path

        json_files = list(search_path.rglob("*.json"))
        return sorted(json_files)

    def flatten_edr_coverage(self, coverage_data):
        """
        Flatten EDR CoverageJSON format to tabular rows

        Args:
            coverage_data: The 'data' section from Bronze Raw JSON

        Returns:
            List of flat dictionaries (rows)
        """
        rows = []

        # Extract coverages
        coverages = coverage_data.get("coverages", [])

        for coverage in coverages:
            # Get domain (coordinates and timestamps)
            domain = coverage.get("domain", {})
            axes = domain.get("axes", {})

            # Extract coordinates
            x_coords = axes.get("x", {}).get("values", [])
            y_coords = axes.get("y", {}).get("values", [])
            timestamps = axes.get("t", {}).get("values", [])

            # Get station ID if available
            location_id = coverage.get("eumetnet:locationId")

            # Extract ranges (the actual data values)
            ranges = coverage.get("ranges", {})

            # For each timestamp, create a row
            for i, timestamp in enumerate(timestamps):
                row = {
                    "timestamp": timestamp,
                    "longitude": x_coords[0] if x_coords else None,
                    "latitude": y_coords[0] if y_coords else None,
                    "location_id": location_id
                }

                # Add all parameter values for this timestamp
                for param_name, param_data in ranges.items():
                    values = param_data.get("values", [])
                    if i < len(values):
                        # Store with original parameter name - no schema enforcement!
                        row[param_name] = values[i]

                rows.append(row)

        return rows

    def transform_file(self, json_path):
        """Transform a single Bronze Raw JSON file"""
        print(f"  Reading: {json_path.name}")

        # Read Bronze Raw JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            bronze_raw = json.load(f)

        metadata = bronze_raw.get("_metadata", {})
        data = bronze_raw.get("data", {})

        # Flatten to tabular format
        rows = self.flatten_edr_coverage(data)

        if not rows:
            print(f"    [WARN] No data rows extracted")
            return None

        # Convert to DataFrame (schema inferred automatically!)
        df = pd.DataFrame(rows)

        # Add tracking metadata
        df['_source_file'] = str(json_path)
        df['_ingestion_timestamp'] = metadata.get('ingestion_timestamp')
        df['_source_api'] = metadata.get('source_api')

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        print(f"    [OK] Extracted {len(df)} rows, {len(df.columns)} columns")
        print(f"    Columns: {', '.join(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}")

        return df

    def get_output_path(self, json_path):
        """Generate output path for refined Parquet file"""
        # Extract date from filename
        filename = json_path.stem  # e.g., "20240101_to_20240131"
        parts = filename.split("_to_")
        start_date = parts[0]

        year = start_date[:4]
        month = start_date[4:6]

        # Create directory structure
        station_dir = self.station_id.replace('-', '_')
        output_dir = BRONZE_REFINED_DIR / "weather_observations" / f"station_id={station_dir}" / f"year={year}" / f"month={month}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Output filename
        output_file = output_dir / f"{filename}.parquet"
        return output_file

    def transform(self, year=None):
        """
        Main transformation pipeline

        Args:
            year: Year to process (None = all years)
        """
        print("="*80)
        print("BRONZE REFINED TRANSFORMATION: JSON -> Parquet (Schema-on-Read)")
        print("="*80)

        # Find Bronze Raw files
        json_files = self.find_bronze_raw_files(year)

        if not json_files:
            print(f"[ERROR] No Bronze Raw files found for station {self.station_key}")
            return

        print(f"\nFound {len(json_files)} Bronze Raw files to transform")
        print(f"Station: {self.station_config['name']} ({self.station_id})\n")

        transformed = 0

        # Transform each file
        for i, json_path in enumerate(json_files, 1):
            print(f"[{i}/{len(json_files)}] {json_path.parent.name}/{json_path.name}")

            try:
                # Transform to DataFrame
                df = self.transform_file(json_path)

                if df is None or df.empty:
                    continue

                # Save to Parquet
                output_path = self.get_output_path(json_path)
                df.to_parquet(output_path, index=False, engine='pyarrow')

                file_size = os.path.getsize(output_path)
                print(f"    [SUCCESS] Saved {file_size:,} bytes to {output_path.name}\n")

                transformed += 1

            except Exception as e:
                print(f"    [ERROR] Failed to transform: {e}\n")
                continue

        print("="*80)
        print(f"[COMPLETE] Transformed {transformed}/{len(json_files)} files")
        print(f"Bronze Refined data saved to: {BRONZE_REFINED_DIR}")
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description="Transform Bronze Raw to Bronze Refined")
    parser.add_argument(
        "--station",
        choices=list(STATIONS.keys()),
        default="hupsel",
        help="Station to transform (default: hupsel)"
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Year to process (default: all years)"
    )

    args = parser.parse_args()

    # Run transformation
    transformer = BronzeRefinedTransformer(args.station)
    transformer.transform(year=args.year)


if __name__ == "__main__":
    main()
