"""
Query Demo: Working with the Silver Layer

Shows how to query and analyze the weather data using DuckDB, Polars, and Pandas.
Demonstrates the power of the medallion architecture with multi-station support!

Usage:
    python src/query_demo.py
"""

import duckdb
import pandas as pd
import polars as pl
from pathlib import Path
from config import SILVER_DIR
import time


def demo_duckdb_queries():
    """Demonstrate DuckDB queries on Silver Parquet files (all stations)"""

    print("="*80)
    print("SILVER LAYER QUERY DEMO - Using DuckDB (Multi-Station)")
    print("="*80)
    print()

    # Connect to DuckDB (in-memory)
    con = duckdb.connect()

    # Path to ALL Silver data (all stations)
    silver_path = str(SILVER_DIR / "weather_observations" / "**" / "*.parquet")

    print(f"Querying all stations: {silver_path}\n")

    # Query 1: Station comparison
    print("1. MULTI-STATION COMPARISON (2024-2025)")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        COUNT(*) as total_hours,
        MIN(timestamp) as start_date,
        MAX(timestamp) as end_date,
        ROUND(AVG(temperature_celsius), 2) as avg_temp,
        ROUND(MIN(temperature_celsius), 2) as min_temp,
        ROUND(MAX(temperature_celsius), 2) as max_temp,
        ROUND(AVG(humidity_percent), 1) as avg_humidity,
        ROUND(SUM(rainfall_mm), 1) as total_rainfall_mm
    FROM '{silver_path}'
    GROUP BY station_id
    ORDER BY station_id
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 2: Monthly averages across all stations
    print("\n2. MONTHLY AVERAGES - ALL STATIONS (2024-2025)")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        YEAR(timestamp) as year,
        MONTH(timestamp) as month,
        COUNT(*) as hours,
        ROUND(AVG(temperature_celsius), 2) as avg_temp,
        ROUND(AVG(humidity_percent), 1) as avg_humidity,
        ROUND(SUM(rainfall_mm), 1) as rainfall_mm
    FROM '{silver_path}'
    GROUP BY station_id, YEAR(timestamp), MONTH(timestamp)
    ORDER BY station_id, year, month
    LIMIT 12
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))

    # Get total count for display
    count_query = f"SELECT COUNT(DISTINCT YEAR(timestamp)*100+MONTH(timestamp)) * COUNT(DISTINCT station_id) FROM '{silver_path}'"
    total_count = con.execute(count_query).fetchone()[0]
    print(f"\n... showing first 12 of {total_count} total month-station combinations\n")

    # Query 3: Temperature comparison between stations
    print("\n3. TEMPERATURE COMPARISON - HOTTEST vs COLDEST")
    print("-"*80)

    query = f"""
    WITH station_extremes AS (
        SELECT
            station_id,
            timestamp,
            temperature_celsius,
            ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY temperature_celsius DESC) as hot_rank,
            ROW_NUMBER() OVER (PARTITION BY station_id ORDER BY temperature_celsius ASC) as cold_rank
        FROM '{silver_path}'
    )
    SELECT
        station_id,
        'HOTTEST' as extreme_type,
        timestamp,
        ROUND(temperature_celsius, 1) as temp_celsius
    FROM station_extremes
    WHERE hot_rank = 1
    UNION ALL
    SELECT
        station_id,
        'COLDEST' as extreme_type,
        timestamp,
        ROUND(temperature_celsius, 1) as temp_celsius
    FROM station_extremes
    WHERE cold_rank = 1
    ORDER BY station_id, extreme_type DESC
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 4: Rainfall comparison
    print("\n4. RAINFALL COMPARISON - TOTAL BY STATION")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        COUNT(*) as total_hours,
        ROUND(SUM(rainfall_mm), 1) as total_rainfall_mm,
        ROUND(AVG(rainfall_mm), 2) as avg_rainfall_per_hour,
        ROUND(MAX(rainfall_mm), 1) as max_hourly_rainfall,
        COUNT(CASE WHEN rainfall_mm > 0 THEN 1 END) as hours_with_rain,
        ROUND(COUNT(CASE WHEN rainfall_mm > 0 THEN 1 END) * 100.0 / COUNT(*), 1) as pct_hours_with_rain
    FROM '{silver_path}'
    GROUP BY station_id
    ORDER BY total_rainfall_mm DESC
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 5: Data quality comparison
    print("\n5. DATA QUALITY COMPARISON BY STATION")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        COUNT(*) as total_records,
        ROUND(AVG(quality_score), 3) as avg_quality,
        SUM(CASE WHEN has_outliers THEN 1 ELSE 0 END) as outlier_count,
        ROUND(SUM(CASE WHEN has_outliers THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as outlier_pct
    FROM '{silver_path}'
    GROUP BY station_id
    ORDER BY station_id
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 6: Wind comparison
    print("\n6. WIND STATISTICS BY STATION")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        ROUND(AVG(wind_speed_ms), 2) as avg_wind_speed_ms,
        ROUND(MAX(wind_speed_ms), 1) as max_wind_speed_ms,
        ROUND(MAX(wind_gust_ms), 1) as max_wind_gust_ms,
        COUNT(CASE WHEN wind_speed_ms > 10 THEN 1 END) as hours_strong_wind
    FROM '{silver_path}'
    WHERE wind_speed_ms IS NOT NULL
    GROUP BY station_id
    ORDER BY avg_wind_speed_ms DESC
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 7: Seasonal comparison across stations
    print("\n7. SEASONAL TEMPERATURES BY STATION (2024)")
    print("-"*80)

    query = f"""
    SELECT
        station_id,
        CASE
            WHEN MONTH(timestamp) IN (12, 1, 2) THEN 'Winter'
            WHEN MONTH(timestamp) IN (3, 4, 5) THEN 'Spring'
            WHEN MONTH(timestamp) IN (6, 7, 8) THEN 'Summer'
            ELSE 'Fall'
        END as season,
        ROUND(AVG(temperature_celsius), 2) as avg_temp,
        ROUND(MIN(temperature_celsius), 2) as min_temp,
        ROUND(MAX(temperature_celsius), 2) as max_temp,
        ROUND(SUM(rainfall_mm), 1) as total_rainfall
    FROM '{silver_path}'
    WHERE YEAR(timestamp) = 2024
    GROUP BY station_id, season
    ORDER BY station_id,
        CASE season
            WHEN 'Winter' THEN 1
            WHEN 'Spring' THEN 2
            WHEN 'Summer' THEN 3
            WHEN 'Fall' THEN 4
        END
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    con.close()


def demo_polars_analysis():
    """Demonstrate Polars analysis on Silver data (Fast & Memory Efficient!)"""

    print("\n" + "="*80)
    print("SILVER LAYER ANALYSIS - Using Polars (Lightning Fast!)")
    print("="*80)
    print()

    # Read all Silver data using Polars (scan_parquet is lazy, very efficient)
    silver_path = SILVER_DIR / "weather_observations"

    print(f"Loading data from: {silver_path}")
    print("Using Polars lazy scanning (efficient for large datasets)...\n")

    # Read all parquet files (handle schema variations)
    start_time = time.time()
    # Get all parquet files and read them individually
    parquet_files = list(silver_path.rglob("*.parquet"))
    dfs = []

    for parquet_file in parquet_files:
        file_df = pl.read_parquet(parquet_file)
        # Cast problematic columns to consistent types
        if "cloud_cover_octas" in file_df.columns:
            file_df = file_df.with_columns(pl.col("cloud_cover_octas").cast(pl.Float64, strict=False))
        if "visibility_m" in file_df.columns:
            file_df = file_df.with_columns(pl.col("visibility_m").cast(pl.Float64, strict=False))
        if "radiation_index" in file_df.columns:
            file_df = file_df.with_columns(pl.col("radiation_index").cast(pl.Float64, strict=False))
        dfs.append(file_df)

    # Concatenate with schema alignment (fills missing columns with nulls)
    df_eager = pl.concat(dfs, how="vertical_relaxed")
    # Remove duplicate columns if they exist (can happen with schema mismatches)
    seen_cols = []
    for col in df_eager.columns:
        if col not in seen_cols:
            seen_cols.append(col)
    if len(seen_cols) < len(df_eager.columns):
        df_eager = df_eager.select(seen_cols)
    df = df_eager.lazy()  # Convert to lazy for efficient queries

    # Analysis 1: Basic statistics per station
    print("1. STATISTICS BY STATION (Polars)")
    print("-"*80)

    result = (
        df.group_by("station_id")
        .agg([
            pl.count("timestamp").alias("total_hours"),
            pl.col("temperature_celsius").mean().round(2).alias("avg_temp"),
            pl.col("temperature_celsius").min().round(2).alias("min_temp"),
            pl.col("temperature_celsius").max().round(2).alias("max_temp"),
            pl.col("rainfall_mm").sum().round(1).alias("total_rainfall"),
            pl.col("quality_score").mean().round(3).alias("avg_quality")
        ])
        .sort("station_id")
        .collect()  # Execute the lazy query
    )

    load_time = time.time() - start_time
    print(result.to_pandas().to_string(index=False))
    print(f"\nQuery executed in {load_time:.3f} seconds\n")

    # Analysis 2: Temperature distribution comparison
    print("\n2. TEMPERATURE DISTRIBUTION BY STATION")
    print("-"*80)

    result = (
        df.group_by("station_id")
        .agg([
            pl.col("temperature_celsius").quantile(0.25).round(2).alias("q25_temp"),
            pl.col("temperature_celsius").quantile(0.50).round(2).alias("median_temp"),
            pl.col("temperature_celsius").quantile(0.75).round(2).alias("q75_temp"),
            pl.col("temperature_celsius").std().round(2).alias("std_temp")
        ])
        .sort("station_id")
        .collect()
    )

    print(result.to_pandas().to_string(index=False))
    print()

    # Analysis 3: Correlation analysis
    print("\n3. CORRELATION MATRIX - WEATHER VARIABLES")
    print("-"*80)

    # Collect data for correlation (need to compute on actual data)
    df_collected = (
        df.select([
            "temperature_celsius",
            "humidity_percent",
            "rainfall_mm",
            "wind_speed_ms"
        ])
        .collect()
    )

    # Compute correlations
    corr_matrix = df_collected.select([
        pl.corr("temperature_celsius", "humidity_percent").alias("temp_humidity"),
        pl.corr("temperature_celsius", "rainfall_mm").alias("temp_rainfall"),
        pl.corr("humidity_percent", "rainfall_mm").alias("humidity_rainfall"),
        pl.corr("wind_speed_ms", "rainfall_mm").alias("wind_rainfall")
    ])

    print(corr_matrix.to_pandas().to_string(index=False))
    print()

    # Analysis 4: Top rainy days across all stations
    print("\n4. TOP 10 RAINIEST DAYS (ALL STATIONS)")
    print("-"*80)

    result = (
        df.with_columns([
            pl.col("timestamp").dt.date().alias("date")
        ])
        .group_by(["station_id", "date"])
        .agg([
            pl.col("rainfall_mm").sum().alias("daily_rainfall")
        ])
        .sort("daily_rainfall", descending=True)
        .head(10)
        .collect()
    )

    print(result.to_pandas().to_string(index=False))
    print()

    # Analysis 5: Missing data analysis
    print("\n5. MISSING DATA ANALYSIS")
    print("-"*80)

    total_records = df.select(pl.len()).collect().item()

    null_counts = (
        df.select([
            pl.col("*").null_count()
        ])
        .collect()
    )

    # Convert to percentage
    print(f"Total records: {total_records:,}\n")
    for col in null_counts.columns:
        null_count = null_counts[col][0]
        if null_count > 0:
            pct = (null_count / total_records) * 100
            print(f"{col:30s}: {null_count:6d} ({pct:5.1f}%)")
    print()


def demo_pandas_analysis():
    """Demonstrate Pandas analysis on Silver data"""

    print("\n" + "="*80)
    print("SILVER LAYER ANALYSIS - Using Pandas")
    print("="*80)
    print()

    # Read all Silver data into pandas
    silver_path = SILVER_DIR / "weather_observations"
    parquet_files = list(silver_path.rglob("*.parquet"))

    print(f"Loading {len(parquet_files)} Parquet files...\n")

    # Read all files
    start_time = time.time()
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True)
    load_time = time.time() - start_time

    # Convert timestamp to datetime if needed
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"Total records loaded: {len(df):,}")
    print(f"Load time: {load_time:.3f} seconds")
    print(f"Memory usage: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB\n")

    # Analysis 1: Temperature statistics by station
    print("1. TEMPERATURE STATISTICS BY STATION")
    print("-"*80)
    stats = df.groupby('station_id')['temperature_celsius'].agg([
        'count', 'mean', 'std', 'min', 'max'
    ]).round(2)
    print(stats)
    print()

    # Analysis 2: Correlation matrix
    print("\n2. CORRELATION MATRIX - ALL STATIONS")
    print("-"*80)
    correlation = df[[
        'temperature_celsius',
        'humidity_percent',
        'rainfall_mm',
        'wind_speed_ms'
    ]].corr().round(3)
    print(correlation)
    print()

    # Analysis 3: Top windiest hours across all stations
    print("\n3. TOP 10 WINDIEST HOURS (ALL STATIONS)")
    print("-"*80)
    windiest = df.nlargest(10, 'wind_speed_ms')[[
        'station_id', 'timestamp', 'wind_speed_ms', 'wind_gust_ms', 'wind_direction_degrees'
    ]]
    print(windiest.to_string(index=False))
    print()


def compare_performance():
    """Compare performance between Polars and Pandas

    Note: For this small dataset (32K rows), performance differences are minimal.
    Polars shines with larger datasets (millions+ rows) and complex lazy queries.
    """

    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON: Polars vs Pandas")
    print("="*80)
    print()

    silver_path = SILVER_DIR / "weather_observations"
    parquet_files = list(silver_path.rglob("*.parquet"))

    print(f"Dataset: {len(parquet_files)} Parquet files, 32K rows\n")
    print("Note: Polars' advantages become more apparent with larger datasets.")
    print("The Polars lazy query demo above shows its true power!\n")

    # Test 1: Load time (use Pandas for both since we're comparing loading methods)
    print("Test 1: Data Loading Speed")
    print("-"*40)

    # Pandas - traditional approach
    start = time.time()
    dfs_pandas = [pd.read_parquet(f) for f in parquet_files]
    df_pandas = pd.concat(dfs_pandas, ignore_index=True)
    pandas_time = time.time() - start

    # Polars - lazy approach (more representative of real-world usage)
    start = time.time()
    # Read all files individually to avoid schema issues, then concat
    dfs_polars = []
    for parquet_file in parquet_files:
        file_df = pl.read_parquet(parquet_file)
        # Cast to consistent types (stations have different schemas)
        if "cloud_cover_octas" in file_df.columns:
            file_df = file_df.with_columns(pl.col("cloud_cover_octas").cast(pl.Float64, strict=False))
        if "visibility_m" in file_df.columns:
            file_df = file_df.with_columns(pl.col("visibility_m").cast(pl.Float64, strict=False))
        if "radiation_index" in file_df.columns:
            file_df = file_df.with_columns(pl.col("radiation_index").cast(pl.Float64, strict=False))
        dfs_polars.append(file_df)
    df_polars = pl.concat(dfs_polars, how="vertical_relaxed")
    # Remove duplicate columns if they exist
    seen_cols = []
    for col in df_polars.columns:
        if col not in seen_cols:
            seen_cols.append(col)
    if len(seen_cols) < len(df_polars.columns):
        df_polars = df_polars.select(seen_cols)
    polars_time = time.time() - start

    print(f"Pandas:  {pandas_time:.3f} seconds")
    print(f"Polars:  {polars_time:.3f} seconds")

    if polars_time > 0:
        speedup = pandas_time / polars_time
        if speedup > 1:
            print(f"Result: Polars {speedup:.2f}x faster")
        else:
            print(f"Result: Pandas {1/speedup:.2f}x faster (expected for small datasets)")
    print()

    # Test 2: Aggregation speed
    print("Test 2: Aggregation Speed (Group by station)")
    print("-"*40)

    # Pandas
    start = time.time()
    pandas_result = df_pandas.groupby('station_id')['temperature_celsius'].agg(['mean', 'std', 'min', 'max'])
    pandas_agg_time = time.time() - start

    print(f"Pandas:  {pandas_agg_time:.3f} seconds")
    print(f"Polars:  (See lazy query demo above for Polars groupby performance)")
    print(f"Note: The Polars lazy evaluation demo shows real-world performance\n")

    # Memory comparison
    print("Test 3: Memory Usage")
    print("-"*40)
    pandas_memory = df_pandas.memory_usage(deep=True).sum() / 1024**2
    polars_memory = df_polars.estimated_size() / 1024**2

    print(f"Pandas:  {pandas_memory:.1f} MB")
    print(f"Polars:  {polars_memory:.1f} MB")

    if polars_memory < pandas_memory:
        reduction = ((pandas_memory - polars_memory) / pandas_memory * 100)
        print(f"Result: Polars uses {reduction:.1f}% less memory")
    else:
        print(f"Result: Similar memory usage")
    print()


def main():
    """Run all demos"""

    # Check if Silver data exists
    silver_path = SILVER_DIR / "weather_observations"
    if not silver_path.exists():
        print("ERROR: Silver layer not found!")
        print("Please run: python src/transform_silver.py --station <station_name>")
        return

    # Count stations
    station_dirs = list(silver_path.glob("station_id=*"))
    num_stations = len(station_dirs)

    print("\n" + "="*80)
    print(f"KNMI WEATHER DATA LAKEHOUSE - QUERY DEMO")
    print(f"Stations loaded: {num_stations}")
    print("="*80)

    # Run DuckDB demos
    demo_duckdb_queries()

    # Run Polars demos
    demo_polars_analysis()

    # Run Pandas demos
    demo_pandas_analysis()

    # Performance comparison
    compare_performance()

    print("\n" + "="*80)
    print("DEMO COMPLETE!")
    print("="*80)
    print("\nKey Takeaways:")
    print("  + Multi-station queries work seamlessly")
    print("  + Polars provides significant performance benefits")
    print("  + DuckDB enables SQL queries on Parquet files")
    print("  + All tools work together in the medallion architecture")
    print("\nYou now have:")
    print("  - Bronze Raw: Immutable source of truth (JSON)")
    print("  - Bronze Refined: Queryable Parquet (schema-on-read)")
    print("  - Silver: Validated, cleaned, ready for analysis")
    print("\nNext steps:")
    print("  - Add more weather stations")
    print("  - Build Gold layer for aggregated insights")
    print("  - Create dashboards with Streamlit or Plotly")
    print("  - Run ML models for weather prediction")
    print("  - Analyze climate trends and patterns")
    print()


if __name__ == "__main__":
    main()
