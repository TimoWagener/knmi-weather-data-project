"""
Query Demo: Working with the Silver Layer

Shows how to query and analyze the weather data using DuckDB and pandas.
Demonstrates the power of the medallion architecture!

Usage:
    python query_demo.py
"""

import duckdb
import pandas as pd
from pathlib import Path
from config import SILVER_DIR


def demo_duckdb_queries():
    """Demonstrate DuckDB queries on Silver Parquet files"""

    print("="*80)
    print("SILVER LAYER QUERY DEMO - Using DuckDB")
    print("="*80)
    print()

    # Connect to DuckDB (in-memory)
    con = duckdb.connect()

    # Path to Silver data
    silver_path = str(SILVER_DIR / "weather_observations" / "station_id=0_20000_0_06283" / "**" / "*.parquet")

    print(f"Querying: {silver_path}\n")

    # Query 1: Basic statistics
    print("1. OVERALL STATISTICS (2024-2025)")
    print("-"*80)

    query = f"""
    SELECT
        COUNT(*) as total_hours,
        MIN(timestamp) as start_date,
        MAX(timestamp) as end_date,
        ROUND(AVG(temperature_celsius), 2) as avg_temp,
        ROUND(MIN(temperature_celsius), 2) as min_temp,
        ROUND(MAX(temperature_celsius), 2) as max_temp,
        ROUND(AVG(humidity_percent), 1) as avg_humidity,
        ROUND(SUM(rainfall_mm), 1) as total_rainfall_mm
    FROM '{silver_path}'
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 2: Monthly averages
    print("\n2. MONTHLY AVERAGE TEMPERATURES (2024-2025)")
    print("-"*80)

    query = f"""
    SELECT
        YEAR(timestamp) as year,
        MONTH(timestamp) as month,
        COUNT(*) as hours,
        ROUND(AVG(temperature_celsius), 2) as avg_temp,
        ROUND(AVG(humidity_percent), 1) as avg_humidity,
        ROUND(SUM(rainfall_mm), 1) as rainfall_mm
    FROM '{silver_path}'
    GROUP BY YEAR(timestamp), MONTH(timestamp)
    ORDER BY year, month
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 3: Extreme weather events
    print("\n3. EXTREME WEATHER EVENTS")
    print("-"*80)

    query = f"""
    SELECT
        timestamp,
        ROUND(temperature_celsius, 1) as temp,
        ROUND(rainfall_mm, 1) as rain,
        ROUND(wind_speed_ms, 1) as wind,
        CASE
            WHEN temperature_celsius < 0 THEN 'Freezing'
            WHEN temperature_celsius > 30 THEN 'Heat'
            WHEN rainfall_mm > 10 THEN 'Heavy Rain'
            WHEN wind_speed_ms > 15 THEN 'Strong Wind'
        END as event_type
    FROM '{silver_path}'
    WHERE temperature_celsius < 0
       OR temperature_celsius > 30
       OR rainfall_mm > 10
       OR wind_speed_ms > 15
    ORDER BY timestamp DESC
    LIMIT 10
    """

    result = con.execute(query).df()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("No extreme events found in this period")
    print()

    # Query 4: Hottest and coldest days
    print("\n4. HOTTEST AND COLDEST DAYS")
    print("-"*80)

    query = f"""
    WITH daily_temps AS (
        SELECT
            DATE_TRUNC('day', timestamp) as date,
            ROUND(AVG(temperature_celsius), 2) as avg_temp,
            ROUND(MAX(temperature_celsius), 2) as max_temp,
            ROUND(MIN(temperature_celsius), 2) as min_temp
        FROM '{silver_path}'
        GROUP BY date
    )
    (
        SELECT 'HOTTEST' as type, date, max_temp as temperature
        FROM daily_temps
        ORDER BY max_temp DESC
        LIMIT 5
    )
    UNION ALL
    (
        SELECT 'COLDEST' as type, date, min_temp as temperature
        FROM daily_temps
        ORDER BY min_temp ASC
        LIMIT 5
    )
    ORDER BY type, temperature DESC
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 5: Rainy days
    print("\n5. RAINIEST DAYS")
    print("-"*80)

    query = f"""
    SELECT
        DATE_TRUNC('day', timestamp) as date,
        ROUND(SUM(rainfall_mm), 1) as total_rainfall_mm,
        COUNT(*) as hours_measured,
        COUNT(CASE WHEN rainfall_mm > 0 THEN 1 END) as hours_with_rain
    FROM '{silver_path}'
    GROUP BY date
    HAVING SUM(rainfall_mm) > 0
    ORDER BY total_rainfall_mm DESC
    LIMIT 10
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 6: Data quality summary
    print("\n6. DATA QUALITY SUMMARY")
    print("-"*80)

    query = f"""
    SELECT
        YEAR(timestamp) as year,
        MONTH(timestamp) as month,
        COUNT(*) as total_records,
        ROUND(AVG(quality_score), 3) as avg_quality,
        SUM(CASE WHEN has_outliers THEN 1 ELSE 0 END) as outlier_count,
        ROUND(SUM(CASE WHEN has_outliers THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) as outlier_pct
    FROM '{silver_path}'
    GROUP BY YEAR(timestamp), MONTH(timestamp)
    ORDER BY year, month
    """

    result = con.execute(query).df()
    print(result.to_string(index=False))
    print()

    # Query 7: Seasonal comparison
    print("\n7. SEASONAL COMPARISON (2024)")
    print("-"*80)

    query = f"""
    SELECT
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
    GROUP BY season
    ORDER BY
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


def demo_pandas_analysis():
    """Demonstrate pandas analysis on Silver data"""

    print("\n" + "="*80)
    print("SILVER LAYER ANALYSIS - Using Pandas")
    print("="*80)
    print()

    # Read all Silver data into pandas
    silver_path = SILVER_DIR / "weather_observations" / "station_id=0_20000_0_06283"
    parquet_files = list(silver_path.rglob("*.parquet"))

    print(f"Loading {len(parquet_files)} Parquet files...\n")

    # Read all files
    dfs = [pd.read_parquet(f) for f in parquet_files]
    df = pd.concat(dfs, ignore_index=True)

    # Convert timestamp to datetime if needed
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    print(f"Total records loaded: {len(df):,}\n")

    # Analysis 1: Temperature distribution
    print("1. TEMPERATURE STATISTICS")
    print("-"*80)
    print(df['temperature_celsius'].describe())
    print()

    # Analysis 2: Correlation between humidity and rainfall
    print("\n2. CORRELATION: HUMIDITY vs RAINFALL")
    print("-"*80)
    correlation = df[['humidity_percent', 'rainfall_mm']].corr()
    print(correlation)
    print()

    # Analysis 3: Windiest hours
    print("\n3. TOP 10 WINDIEST HOURS")
    print("-"*80)
    windiest = df.nlargest(10, 'wind_speed_ms')[
        ['timestamp', 'wind_speed_ms', 'wind_gust_ms', 'wind_direction_degrees']
    ]
    print(windiest.to_string(index=False))
    print()

    # Analysis 4: Missing data summary
    print("\n4. MISSING DATA SUMMARY")
    print("-"*80)
    missing = df.isnull().sum()
    missing_pct = (missing / len(df)) * 100
    missing_summary = pd.DataFrame({
        'Missing Count': missing,
        'Missing %': missing_pct.round(2)
    })
    print(missing_summary[missing_summary['Missing Count'] > 0].to_string())
    print()


def main():
    """Run all demos"""

    # Check if Silver data exists
    silver_path = Path("data/silver/weather_observations")
    if not silver_path.exists():
        print("ERROR: Silver layer not found!")
        print("Please run: python transform_silver.py --station hupsel")
        return

    # Run DuckDB demos
    demo_duckdb_queries()

    # Run pandas demos
    demo_pandas_analysis()

    print("\n" + "="*80)
    print("DEMO COMPLETE!")
    print("="*80)
    print("\nYou now have:")
    print("  - Bronze Raw: Immutable source of truth (JSON)")
    print("  - Bronze Refined: Queryable Parquet (schema-on-read)")
    print("  - Silver: Validated, cleaned, ready for analysis")
    print("\nNext steps:")
    print("  - Build Gold layer when you have multiple stations")
    print("  - Create dashboards with your favorite BI tool")
    print("  - Run ML models for weather prediction")
    print("  - Analyze climate trends")
    print()


if __name__ == "__main__":
    main()
