"""
Silver Layer Transformation: Bronze Refined -> Silver (Validated & Cleaned)

Enforces fixed schema, validates data, handles missing values, flags outliers.
This is where data quality rules are applied.

Usage:
    python transform_silver.py --station hupsel
    python transform_silver.py --station hupsel --year 2024
"""

import os
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np
from config import BRONZE_REFINED_DIR, SILVER_DIR, STATIONS


class SilverTransformer:
    """Transforms Bronze Refined to Silver layer with data quality"""

    # Define the FIXED schema for Silver layer
    SILVER_SCHEMA = {
        # Core identification
        "timestamp": "datetime64[ns, UTC]",
        "station_id": "string",
        "latitude": "float64",
        "longitude": "float64",

        # Weather measurements (standardized names)
        "temperature_celsius": "float64",           # T
        "temperature_min_celsius": "float64",       # T10N
        "dewpoint_celsius": "float64",              # TD
        "humidity_percent": "float64",              # U
        "rainfall_mm": "float64",                   # RH
        "rainfall_duration_minutes": "float64",     # DR
        "wind_direction_degrees": "float64",        # DD
        "wind_speed_ms": "float64",                 # FF
        "wind_gust_ms": "float64",                  # FX
        "wind_speed_hourly_ms": "float64",          # FH
        "solar_radiation_jcm2": "float64",          # Q
        "sunshine_duration_minutes": "float64",     # SQ
        "visibility_m": "float64",                  # VV
        "air_pressure_hpa": "float64",              # P (if available)
        "cloud_cover_octas": "float64",             # N
        "weather_code": "Int64",                    # WW
        "evaporation_mm": "float64",                # EE
        "radiation_index": "Int64",                 # IX
    }

    # Data quality thresholds
    THRESHOLDS = {
        "temperature_celsius": (-50, 50),
        "humidity_percent": (0, 100),
        "rainfall_mm": (0, 200),
        "wind_speed_ms": (0, 50),
        "wind_direction_degrees": (0, 360),
    }

    def __init__(self, station_key):
        self.station_key = station_key
        self.station_config = STATIONS[station_key]
        self.station_id = self.station_config["id"]

    def find_bronze_refined_files(self, year=None):
        """Find all Bronze Refined Parquet files for this station"""
        station_dir = self.station_id.replace('-', '_')
        base_path = BRONZE_REFINED_DIR / "weather_observations" / f"station_id={station_dir}"

        if year:
            search_path = base_path / f"year={year}"
        else:
            search_path = base_path

        parquet_files = list(search_path.rglob("*.parquet"))
        return sorted(parquet_files)

    def map_bronze_to_silver_schema(self, df):
        """
        Map Bronze Refined columns to Silver schema with standardized names

        This is where we enforce the fixed schema!
        """
        # Create mapping from Bronze names to Silver names
        column_mapping = {
            "timestamp": "timestamp",
            "location_id": "station_id",
            "latitude": "latitude",
            "longitude": "longitude",
            "T": "temperature_celsius",
            "T10N": "temperature_min_celsius",
            "TD": "dewpoint_celsius",
            "U": "humidity_percent",
            "RH": "rainfall_mm",
            "DR": "rainfall_duration_minutes",
            "DD": "wind_direction_degrees",
            "FF": "wind_speed_ms",
            "FX": "wind_gust_ms",
            "FH": "wind_speed_hourly_ms",
            "Q": "solar_radiation_jcm2",
            "SQ": "sunshine_duration_minutes",
            "VV": "visibility_m",
            "N": "cloud_cover_octas",
            "WW": "weather_code",
            "EE": "evaporation_mm",
            "IX": "radiation_index",
        }

        # Select and rename columns that exist in Bronze
        silver_df = pd.DataFrame()

        for bronze_col, silver_col in column_mapping.items():
            if bronze_col in df.columns:
                silver_df[silver_col] = df[bronze_col]
            elif silver_col in self.SILVER_SCHEMA:
                # Column doesn't exist in Bronze, add as NULL
                silver_df[silver_col] = pd.NA

        return silver_df

    def apply_data_quality(self, df):
        """Apply data quality checks and add quality flags"""

        # Initialize quality columns
        df["quality_score"] = 1.0  # Perfect score = 1.0
        df["quality_flags"] = ""
        df["has_missing_values"] = False
        df["has_outliers"] = False

        # Check for missing values (only for columns that exist!)
        existing_data_columns = [col for col in self.SILVER_SCHEMA.keys() if col in df.columns]
        missing_mask = df[existing_data_columns].isna().any(axis=1)
        df.loc[missing_mask, "has_missing_values"] = True
        df.loc[missing_mask, "quality_score"] -= 0.2

        # Check for outliers
        for column, (min_val, max_val) in self.THRESHOLDS.items():
            if column in df.columns:
                outlier_mask = (df[column] < min_val) | (df[column] > max_val)
                if outlier_mask.any():
                    df.loc[outlier_mask, "has_outliers"] = True
                    df.loc[outlier_mask, "quality_score"] -= 0.3

                    # Add to quality flags
                    df.loc[outlier_mask, "quality_flags"] += f"{column}_outlier;"

        # Handle special values
        # Rainfall: -1 means < 0.05mm, convert to 0.0
        if "rainfall_mm" in df.columns:
            df.loc[df["rainfall_mm"] == -1, "rainfall_mm"] = 0.0

        # Ensure quality_score doesn't go negative
        df["quality_score"] = df["quality_score"].clip(lower=0.0)

        return df

    def add_metadata(self, df):
        """Add Silver layer metadata"""
        df["_processed_timestamp"] = pd.Timestamp.now(tz='UTC')
        df["_bronze_to_silver_version"] = "1.0"
        return df

    def transform_file(self, parquet_path):
        """Transform a single Bronze Refined Parquet file"""
        print(f"  Reading: {parquet_path.name}")

        # Read Bronze Refined
        df = pd.read_parquet(parquet_path)

        if df.empty:
            print(f"    [WARN] Empty file, skipping")
            return None

        original_rows = len(df)

        # 1. Map to Silver schema (enforce fixed schema!)
        df = self.map_bronze_to_silver_schema(df)

        # 2. Apply data quality checks
        df = self.apply_data_quality(df)

        # 3. Remove duplicates
        df = df.drop_duplicates(subset=["timestamp", "station_id"], keep="first")
        duplicates_removed = original_rows - len(df)

        # 4. Add metadata
        df = self.add_metadata(df)

        # 5. Sort by timestamp
        df = df.sort_values("timestamp").reset_index(drop=True)

        # Report quality stats
        avg_quality = df["quality_score"].mean()
        missing_pct = (df["has_missing_values"].sum() / len(df)) * 100
        outlier_pct = (df["has_outliers"].sum() / len(df)) * 100

        print(f"    [OK] {len(df)} rows (removed {duplicates_removed} duplicates)")
        print(f"    Quality: {avg_quality:.2f} avg | {missing_pct:.1f}% missing | {outlier_pct:.1f}% outliers")

        return df

    def get_output_path(self, parquet_path):
        """Generate output path for Silver Parquet file"""
        # Extract date info from Bronze path
        parts = parquet_path.parts
        year_part = [p for p in parts if p.startswith("year=")][0]
        month_part = [p for p in parts if p.startswith("month=")][0]

        year = year_part.split("=")[1]
        month = month_part.split("=")[1]

        # Create directory structure (same partitioning as Bronze)
        station_dir = self.station_id.replace('-', '_')
        output_dir = SILVER_DIR / "weather_observations" / f"station_id={station_dir}" / f"year={year}" / f"month={month}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Output filename
        output_file = output_dir / parquet_path.name
        return output_file

    def transform(self, year=None):
        """
        Main Silver transformation pipeline

        Args:
            year: Year to process (None = all years)
        """
        print("="*80)
        print("SILVER LAYER TRANSFORMATION: Bronze Refined -> Silver (Validated)")
        print("="*80)

        # Find Bronze Refined files
        parquet_files = self.find_bronze_refined_files(year)

        if not parquet_files:
            print(f"[ERROR] No Bronze Refined files found for station {self.station_key}")
            return

        print(f"\nFound {len(parquet_files)} Bronze Refined files to transform")
        print(f"Station: {self.station_config['name']} ({self.station_id})")
        print(f"Applying fixed schema with {len(self.SILVER_SCHEMA)} columns\n")

        transformed = 0
        total_rows = 0

        # Transform each file
        for i, parquet_path in enumerate(parquet_files, 1):
            print(f"[{i}/{len(parquet_files)}] {parquet_path.parent.name}/{parquet_path.name}")

            try:
                # Transform to Silver
                df = self.transform_file(parquet_path)

                if df is None or df.empty:
                    continue

                # Save to Silver
                output_path = self.get_output_path(parquet_path)
                df.to_parquet(output_path, index=False, engine='pyarrow')

                file_size = os.path.getsize(output_path)
                print(f"    [SUCCESS] Saved {file_size:,} bytes\n")

                transformed += 1
                total_rows += len(df)

            except Exception as e:
                print(f"    [ERROR] Failed to transform: {e}\n")
                continue

        print("="*80)
        print(f"[COMPLETE] Transformed {transformed}/{len(parquet_files)} files")
        print(f"Total rows in Silver: {total_rows:,}")
        print(f"Silver data saved to: {SILVER_DIR}")
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description="Transform Bronze Refined to Silver")
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
    transformer = SilverTransformer(args.station)
    transformer.transform(year=args.year)


if __name__ == "__main__":
    main()
