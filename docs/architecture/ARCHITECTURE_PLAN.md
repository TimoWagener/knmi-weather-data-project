# Modern Data Warehouse Architecture Plan
## DIY Medallion Architecture for KNMI Weather Data

### Executive Summary
Redesign the weather data pipeline to use medallion architecture (Bronze/Silver/Gold) with modern data engineering practices at DIY scale. Store ALL data once, query efficiently, and build multiple analytical views without re-downloading.

---

## Current Problems

1. **Massive data waste**: Downloads 348 data points/hour, keeps only 3 (98.3% waste)
2. **No reusability**: Want different station? Re-download everything
3. **No data history**: Can't go back to raw data if needed
4. **Poor performance**: CSV scans entire file for queries
5. **No data quality**: No validation or quality checks

---

## Proposed Architecture: Medallion Layers

### **Bronze Layer (Raw/Landing Zone)**
**Purpose**: Store raw data exactly as received, immutable source of truth

**Storage Format**: Parquet files (compressed, columnar)
- Why not NetCDF? Parquet is universal, faster to query, better compression
- One-time conversion: NetCDF → Parquet with ALL stations and variables
- Partitioning: `bronze/year=YYYY/month=MM/day=DD/hour=HH/*.parquet`

**Schema**: Flatten the NetCDF structure
```
timestamp (datetime64)
station_id (string)
station_name (string)
lat (float64)
lon (float64)
height (float64)
T (float64)             # Temperature
T10N (float64)          # Min temp
U (float64)             # Humidity
RH (float64)            # Rainfall
DD (float64)            # Wind direction
FF (float64)            # Wind speed
... (all 29 variables)
_ingestion_timestamp (datetime64)  # When we downloaded it
_source_file (string)              # Original filename
```

**Estimated Size**:
- 1 hour = ~12 stations × 35 fields × 8 bytes = ~3 KB (compressed ~1 KB)
- 1 year = ~9 MB
- 10 years = ~90 MB (tiny!)

---

### **Silver Layer (Cleaned/Validated)**
**Purpose**: Cleaned, validated, standardized data ready for analysis

**Transformations**:
1. **Handle missing values**: -1 for rainfall → 0.0, NaN → NULL
2. **Data validation**: Flag outliers (temp < -50 or > 50, etc.)
3. **Add quality scores**: Based on completeness and validity
4. **Standardize units**: Ensure all temps in Celsius, rainfall in mm
5. **Deduplication**: Remove any duplicate records

**Storage**: Parquet files
- Partitioning: `silver/station_id=XXXXX/year=YYYY/month=MM/*.parquet`
- Enables fast station-specific queries

**New Columns**:
```
quality_score (float)           # 0-1 score
has_missing_values (boolean)
outlier_flags (array<string>)   # Which fields are outliers
temperature_celsius (float)     # Explicit naming
rainfall_mm (float)
humidity_percent (float)
```

---

### **Gold Layer (Analytics-Ready)**
**Purpose**: Business-ready aggregated views for specific use cases

**Multiple Gold Tables**:

1. **`gold_daily_summary_by_station`**
   - Daily aggregates: min/max/avg temp, total rainfall, avg humidity
   - Fast for dashboards and reports

2. **`gold_hourly_deelen`** (Original use case)
   - Just Deelen station, key variables, hourly
   - Replaces current CSV output

3. **`gold_monthly_comparison`**
   - All stations, monthly aggregates
   - Compare regions easily

4. **`gold_extreme_weather_events`**
   - Heavy rainfall (>20mm/hour)
   - Extreme temps (< 0°C or > 30°C)
   - Strong winds (> 60 km/h)
   - Pre-filtered for quick analysis

---

## Technology Stack (All Free/Open Source)

### 1. **DuckDB** (Primary Query Engine)
- Embedded OLAP database (no server needed!)
- Blazing fast Parquet queries
- SQL interface
- Perfect for 10GB-1TB data
- Can query Parquet files directly without loading

### 2. **Parquet** (Storage Format)
- Columnar storage (only read columns you need)
- Excellent compression (~10x vs CSV)
- Fast filtering with predicate pushdown
- Industry standard

### 3. **Polars or Pandas** (ETL)
- Polars: 10x faster than pandas, Rust-based
- Pandas: More mature, easier to learn
- Choose based on comfort level

### 4. **Optional: dbt (Data Build Tool)**
- Define transformations in SQL
- Automatic dependency management
- Documentation generation
- Testing framework
- Overkill for tiny project, but good practice

---

## File Structure

```
LocalWeatherDataProject/
├── data/
│   ├── bronze/                    # Raw data
│   │   ├── year=2025/
│   │   │   ├── month=10/
│   │   │   │   ├── day=01/
│   │   │   │   │   └── hour=00/
│   │   │   │   │       └── data.parquet
│   ├── silver/                    # Cleaned data
│   │   ├── station_id=06275/     # Deelen
│   │   │   ├── year=2025/
│   │   │   │   └── month=10/
│   │   │   │       └── data.parquet
│   ├── gold/                      # Analytics views
│   │   ├── daily_summary_by_station/
│   │   ├── hourly_deelen/
│   │   ├── monthly_comparison/
│   │   └── extreme_weather_events/
│
├── src/
│   ├── bronze/
│   │   └── ingest_knmi.py        # Download & convert to Parquet
│   ├── silver/
│   │   └── clean_and_validate.py # Transformations
│   ├── gold/
│   │   ├── create_daily_summary.py
│   │   ├── create_hourly_deelen.py
│   │   └── create_extreme_events.py
│   └── utils/
│       ├── duckdb_queries.py     # Reusable query functions
│       └── data_quality.py       # Validation rules
│
├── queries/                       # Ad-hoc DuckDB queries
│   └── examples.sql
│
├── notebooks/                     # Analysis notebooks
│   └── exploratory_analysis.ipynb
│
├── config/
│   └── pipeline_config.yaml      # Date ranges, stations, etc.
│
├── tests/                         # Data quality tests
│   └── test_silver_quality.py
│
├── requirements.txt
└── README.md
```

---

## Implementation Plan: Phased Approach

### Phase 1: Bronze Layer (Foundation)
**Goal**: Store all raw data efficiently

1. **Rewrite ingestion script**:
   - Download NetCDF files
   - Extract ALL stations and variables (not just one!)
   - Convert to Parquet with partitioning
   - Store in `data/bronze/`

2. **Benefits unlocked**:
   - Never re-download the same data
   - 90%+ storage savings vs keeping NetCDF files
   - Can query any station/variable later

### Phase 2: Silver Layer (Quality)
**Goal**: Clean data for reliable analysis

1. **Data quality pipeline**:
   - Read bronze Parquet files
   - Apply cleaning rules
   - Validate and flag issues
   - Write to `data/silver/` partitioned by station

2. **Add DuckDB**:
   - Create database connection
   - Register Parquet files as tables
   - Write simple queries

3. **Benefits unlocked**:
   - Fast station-specific queries
   - Data quality visibility
   - Foundation for gold layer

### Phase 3: Gold Layer (Analytics)
**Goal**: Pre-built views for common analyses

1. **Create gold tables**:
   - Daily summaries
   - Station-specific hourly (replaces current CSV)
   - Extreme weather events

2. **Query optimization**:
   - Materialized views for fast access
   - Indexes where needed

3. **Benefits unlocked**:
   - Sub-second query times
   - Multiple analytical views
   - Ready for dashboards/ML

### Phase 4: Orchestration (Optional)
**Goal**: Automated pipeline execution

Options:
- **Cron jobs**: Simple, built-in (Windows Task Scheduler)
- **Prefect**: Modern, Python-native, free
- **Dagster**: Asset-based, great UI, free
- **Airflow**: Overkill for DIY project

---

## Example DuckDB Queries

```sql
-- Query bronze: Get all stations for a specific hour
SELECT * FROM 'data/bronze/year=2025/month=11/day=11/**/*.parquet'
WHERE station_id = '0-20000-0-06275';

-- Query silver: Deelen station, last 7 days
SELECT timestamp, temperature_celsius, rainfall_mm, humidity_percent
FROM 'data/silver/station_id=06275/**/*.parquet'
WHERE timestamp >= CURRENT_DATE - INTERVAL 7 DAY
ORDER BY timestamp;

-- Query gold: Wettest days across all stations
SELECT station_name, date_trunc('day', timestamp) as day,
       SUM(rainfall_mm) as total_rainfall_mm
FROM 'data/gold/daily_summary_by_station/**/*.parquet'
GROUP BY station_name, day
ORDER BY total_rainfall_mm DESC
LIMIT 10;

-- Compare temperatures across stations (no re-download needed!)
SELECT station_name,
       AVG(temperature_celsius) as avg_temp,
       MIN(temperature_celsius) as min_temp,
       MAX(temperature_celsius) as max_temp
FROM 'data/silver/**/*.parquet'
WHERE timestamp >= '2025-10-01'
GROUP BY station_name;
```

---

## Performance Estimates

**Bronze Ingestion**:
- Current: ~4 sec/file (API delay) × 24 files/day = ~2 min/day
- New: Same download, but stores ALL data (no extra cost)

**Silver Processing**:
- 1 day of data (~24 KB) processes in <100ms with Polars
- Full year: ~10 MB, processes in <1 second

**Gold Queries**:
- DuckDB on Parquet: 100-1000x faster than pandas on CSV
- Hourly data for 1 station, 1 year: ~10ms
- Daily aggregates for all stations, 10 years: ~100ms

---

## Migration Path from Current Code

1. **Keep current script working** (don't break things!)
2. **Build bronze layer in parallel** (run new script, generates Parquet)
3. **Validate**: Compare bronze→gold output vs current CSV
4. **Switch**: Use gold layer output instead of CSV
5. **Deprecate**: Remove old script once validated

---

## Cost Benefit Analysis

**Storage**:
- Current CSV for 1 station, 1 year: ~2 MB
- Bronze (ALL 12 stations, ALL variables), 1 year: ~9 MB (4.5x for 12x data!)
- Silver + Gold add ~20% overhead

**Time Savings**:
- Want to analyze a different station?
  - Current: Re-download everything (~2 min/day)
  - New: Query silver layer (~10ms)
- Add new gold view: Minutes, not hours
- Data quality issues: Traceable to source

**Flexibility**:
- Current: 3 variables from 1 station
- New: 29 variables from 12 stations, infinitely queryable

---

## Next Steps

**Option A**: Full rewrite (recommended)
- Start fresh with medallion architecture
- Implement Bronze → Silver → Gold
- Migrate once validated

**Option B**: Incremental
- Add bronze layer to existing script
- Gradually add silver/gold
- Lower risk but slower progress

**Your choice!** I can implement either approach.

Would you like me to:
1. Start building the Bronze layer (Parquet ingestion)?
2. Set up DuckDB first and show you example queries?
3. Create a config file for pipeline parameters?
4. Something else?
