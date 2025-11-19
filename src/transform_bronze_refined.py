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
from src.config import BRONZE_RAW_DIR, BRONZE_REFINED_DIR, STATIONS


class BronzeRefinedTransformer:
    """Transforms Bronze Raw JSON to Bronze Refined Parquet"""

    def __init__(self, station_key):
        self.station_key = station_key
        self.station_config = STATIONS[station_key]
        self.station_id = self.station_config["id"]

    def find_bronze_raw_files(self, year=None):
        """Find all Bronze Raw JSON files for this station"""
        # Bronze Raw uses full station ID format (e.g., "0-20000-0-06283")
        base_path = BRONZE_RAW_DIR / "edr_api" / f"station_id={self.station_id}"

        if year:
            # Look for specific year
            file_path = base_path / f"year={year}" / "data.json"
            return [file_path] if file_path.exists() else []
        else:
            # Find all years for this station
            json_files = []
            if base_path.exists():
                for year_dir in sorted(base_path.iterdir()):
                    if year_dir.is_dir() and year_dir.name.startswith("year="):
                        data_file = year_dir / "data.json"
                        if data_file.exists():
                            json_files.append(data_file)
            return sorted(json_files)

    def flatten_edr_coverage(self, coverage_json):
        """
        Flatten EDR CoverageJSON format to tabular rows

        Args:
            coverage_json: The complete CoverageJSON object from Bronze Raw

        Returns:
            List of flat dictionaries (rows)
        """
        rows = []

        # Extract coverages from root level
        coverages = coverage_json.get("coverages", [])

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
        """Transform a single Bronze Raw JSON file (1 year of data)"""
        print(f"  Reading: {json_path.parent.name}/{json_path.name}")

        # Read Bronze Raw JSON - it's the direct CoverageJSON from API
        with open(json_path, 'r', encoding='utf-8') as f:
            coverage_json = json.load(f)

        # Flatten to tabular format
        rows = self.flatten_edr_coverage(coverage_json)

        if not rows:
            print(f"    [WARN] No data rows extracted")
            return None

        # Convert to DataFrame (schema inferred automatically!)
        df = pd.DataFrame(rows)

        # Add tracking metadata
        df['_source_file'] = str(json_path)
        df['_transform_timestamp'] = datetime.now().isoformat()

        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Add year and month columns for partitioning
        df['year'] = df['timestamp'].dt.year
        df['month'] = df['timestamp'].dt.month

        print(f"    [OK] Extracted {len(df)} rows, {len(df.columns)} columns")
        print(f"    Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        print(f"    Columns: {', '.join(df.columns[:10])}{'...' if len(df.columns) > 10 else ''}")

        return df

    def get_output_path(self, year, month):
        """Generate output path for refined Parquet file with monthly partitioning

        Args:
            year: Year (e.g., 2024)
            month: Month (e.g., 1-12)

        Returns:
            Path for the Parquet file
        """
        # Use full station ID in path (consistent with Bronze Raw)
        output_dir = (BRONZE_REFINED_DIR / "edr_api" /
                     f"station_id={self.station_id}" /
                     f"year={year}" /
                     f"month={month:02d}")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Output filename
        output_file = output_dir / "data.parquet"
        return output_file

    def month_already_transformed(self, year, month):
        """Check if a month has already been transformed

        Args:
            year: Year to check
            month: Month to check

        Returns:
            True if Parquet file exists, False otherwise
        """
        output_path = self.get_output_path(year, month)
        return output_path.exists()

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
        total_months = 0
        skipped_months = 0

        # Transform each file (1 file = 1 year of data)
        for i, json_path in enumerate(json_files, 1):
            print(f"[{i}/{len(json_files)}] {json_path.parent.name}/{json_path.name}")

            try:
                # Check if all months already exist (idempotency)
                # Extract year from path
                year_str = json_path.parent.name.replace("year=", "")
                year = int(year_str)

                # Check which months are already transformed
                months_to_transform = []
                for month in range(1, 13):
                    if not self.month_already_transformed(year, month):
                        months_to_transform.append(month)

                if not months_to_transform:
                    print(f"    [SKIP] All 12 months already transformed\n")
                    skipped_months += 12
                    continue

                # Transform to DataFrame (contains full year)
                df = self.transform_file(json_path)

                if df is None or df.empty:
                    continue

                # Split by month and save each month separately
                year_from_data = df['year'].iloc[0]  # All rows should have same year

                for month in sorted(df['month'].unique()):
                    # Skip if already transformed
                    if month not in months_to_transform:
                        print(f"      [SKIP] Month {month:02d}: Already exists")
                        skipped_months += 1
                        continue

                    month_df = df[df['month'] == month].copy()

                    # Drop partition columns before saving (they're in the path)
                    month_df = month_df.drop(columns=['year', 'month'])

                    # Save to Parquet with monthly partitioning
                    output_path = self.get_output_path(year_from_data, month)
                    month_df.to_parquet(output_path, index=False, engine='pyarrow',
                                       compression='snappy')

                    file_size = os.path.getsize(output_path)
                    print(f"      [OK] Month {month:02d}: {len(month_df)} rows, "
                          f"{file_size:,} bytes -> {output_path.name}")
                    total_months += 1

                transformed += 1
                print()

            except Exception as e:
                print(f"    [ERROR] Failed to transform: {e}\n")
                import traceback
                traceback.print_exc()
                continue

        print("="*80)
        print(f"[COMPLETE] Transformed {transformed}/{len(json_files)} years")
        print(f"           Created {total_months} new monthly Parquet files")
        if skipped_months > 0:
            print(f"           Skipped {skipped_months} already-transformed months")
        print(f"           Bronze Refined data saved to: {BRONZE_REFINED_DIR}")
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
