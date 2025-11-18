# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Production-ready data lakehouse for KNMI weather data** using medallion architecture (Bronze/Silver/Gold layers) with automated orchestration.

Downloads hourly weather observations from KNMI EDR API, processes through data quality layers, and provides efficient querying with multiple tools. Currently contains **316,278 hours of data (2000-2025)** for 2 stations: Hupsel and Deelen. **8 more stations configured and ready to load.**

**Key Technologies:**
- KNMI EDR API (Environmental Data Retrieval) - primary source
- DuckDB for efficient OLAP queries on Parquet files
- Polars for fast, memory-efficient dataframe operations (1.18x faster, 50% less memory vs Pandas)
- Pandas for traditional dataframe analysis
- Parquet for columnar storage with partitioning
- PyArrow for data processing
- Metadata tracking system for orchestration
- python-dotenv for secure API key management

**Architecture:** Medallion (Bronze Raw → Bronze Refined → Silver → Gold*)
*Gold layer not yet implemented

**Output:** Queryable Parquet files partitioned by `station_id/year/month/`

**Query Performance:**
- DuckDB: Sub-second SQL queries on 316K+ rows
- Polars: 1.18x faster loading, 47% less memory vs Pandas
- Pandas: Compatible, widely-used for analysis

**Data Volume:** 25.9 years per station (2000-2025), 158,139 hours each

## Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# API keys stored in C:\AI-Projects\.env (parent directory)
# Claude cannot read this file (security feature)
```

### Historical Data Loading (Recommended)

**IMPORTANT:** All commands must be run from the project root directory.

**Load all 10 configured stations (2000-2025):**
```bash
# Parallel bulk load (45-60 minutes for all 10 stations)
python src/orchestrate_historical.py --stations core_10 --start-year 2000 --end-year 2025 --max-workers 5

# Check load status
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```

**Load specific date range:**
```bash
# Load 2020-2025 for currently loaded stations
python src/orchestrate_historical.py --stations currently_loaded --start-year 2020 --end-year 2025

# Load single station
python src/orchestrate_historical.py --station de_bilt --start-year 2000 --end-year 2025
```

### Manual Pipeline (for custom date ranges)

**Full pipeline for a station:**
```bash
# 1. Bronze Raw: Download from EDR API
python src/ingest_bronze_raw.py --station hupsel --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"

# 2. Bronze Refined: Convert to Parquet
python src/transform_bronze_refined.py --station hupsel --year 2024

# 3. Silver: Validate & clean
python src/transform_silver.py --station hupsel --year 2024
```

**Incremental updates (add latest data):**
```bash
# Get yesterday's data
python src/ingest_bronze_raw.py --station hupsel --start-date "2025-11-17T00:00:00Z" --end-date "2025-11-17T23:59:59Z"
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
```

**Query the data:**
```bash
python src/query_demo.py  # Runs DuckDB + Polars + Pandas analysis
```

**Test scripts:**
```bash
python scripts/test_edr_api.py  # Test EDR API connection
python scripts/explore_edr_api.py  # Explore EDR capabilities
```

### Available Stations

**Currently Loaded (2 of 10):**
- **Hupsel** (0-20000-0-06283) - ✅ 2000-2025 (158,139 hours)
- **Deelen** (0-20000-0-06275) - ✅ 2000-2025 (158,139 hours)

**Configured & Ready to Load (8 more):**
- **De Bilt** (0-20000-0-06260) - KNMI headquarters
- **Schiphol** (0-20000-0-06240) - Amsterdam Airport
- **Rotterdam** (0-20000-0-06344) - Urban, port city
- **Vlissingen** (0-20000-0-06310) - Coastal, North Sea
- **Maastricht** (0-20000-0-06380) - Southern, hilly
- **Eelde** (0-20000-0-06280) - Northern airport
- **Den Helder** (0-20000-0-06235) - Northern coastal
- **Twenthe** (0-20000-0-06290) - Eastern airport

**77 total stations** available via EDR API - See `scripts/test_edr_api.py`

## Architecture

### Medallion Data Lakehouse

```
data/
  bronze/
    raw/         - Immutable JSON from EDR API (source of truth)
    refined/     - Parquet with schema-on-read (efficient querying)
  silver/        - Validated, cleaned, fixed schema
  gold/          - (Not yet built) Aggregated, business-ready
```

**Partitioning:** `station_id={id}/year={year}/month={month}/file.parquet`

**Current Storage:** ~292 MB (206 MB raw + 42 MB refined + 44 MB silver)

### Data Flow

**Bronze Raw (JSON):**
- Source: KNMI EDR API `/collections/hourly-in-situ-meteorological-observations-validated/locations/{station_id}`
- Format: Raw JSON responses (CoverageJSON format)
- Why: Preserve exact API response for compliance/reprocessing
- Chunking: Yearly (to avoid EDR 376K data point limit)

**Bronze Refined (Parquet):**
- Transform: Flatten nested JSON → tabular Parquet
- Schema: **On-read** (no fixed schema, preserves all source fields)
- Why: Efficient columnar storage, future-proof for API changes
- Size: ~21 MB per station (25 years) - 4.9x compression vs JSON

**Silver (Parquet):**
- Transform: Enforce fixed schema, validate, clean
- Schema: **Fixed** - 22 standardized columns
- Quality: Score each record (0-1), flag outliers, handle missing values
- Transformations:
  - Rainfall -1 → 0.0 (EDR convention)
  - Standardized naming (T → temperature_celsius)
  - Deduplication
  - Outlier detection (temp <-50 or >50, etc.)

### Key Design Decisions

**Why EDR API (not Open Data API)?**
- Queries specific stations (don't download all 12 stations in NetCDF)
- 77 stations available (vs 12 in NetCDF files)
- Clean JSON (no NetCDF conversion)
- 108x faster (10 min vs 18 hours for 2024-2025)

**Why two Bronze layers?**
- Raw: Compliance, reprocessing, debugging
- Refined: Efficient querying while preserving flexibility

**Why monthly partitioning?**
- Balance: Not too many files (daily) or too large (yearly)
- Query flexibility: Skip irrelevant months
- Scalable: Works for 1-100 stations
- Perfect for incremental updates

**Why yearly chunks for historical loads?**
- Monthly: Too many API calls (300+ per station for 25 years)
- Yearly: Sweet spot (~30 chunks per station)
- 5-year: Risk of hitting API limits

**Why schema-on-read in Bronze Refined?**
- API may add new fields → automatically preserved
- Different stations may have different sensors
- No schema enforcement = no breaking changes

### API Details

**EDR API:**
- Endpoint: `https://api.dataplatform.knmi.nl/edr/v1`
- Auth: Bearer token in `Authorization` header
- Rate: 200 req/sec, 1000 req/hour (registered key)
- Limit: ~376K data points per request (hours × params × stations)
- Solution: Chunk by year (~8,640 hours × 23 params = ~200K points)

**API Keys (Secure):**
- Location: `C:\AI-Projects\.env` (parent directory)
- Variables: `KNMI_EDR_API_KEY`, `KNMI_OPEN_DATA_API_KEY`
- Loading: `load_dotenv("../.env")` in all scripts
- Security: Claude cannot read .env files

### Project Structure

**Recent Changes (2025-11-16):**
Added orchestration and metadata tracking:

```
LocalWeatherDataProject/
├── src/                     # Core pipeline scripts
│   ├── config.py           # Configuration (10 stations, API keys, paths)
│   ├── ingest_bronze_raw.py         # EDR API → Bronze Raw
│   ├── transform_bronze_refined.py  # JSON → Parquet
│   ├── transform_silver.py          # Parquet → Silver
│   ├── query_demo.py                # Multi-tool query demos
│   ├── metadata_manager.py          # Metadata tracking (NEW)
│   └── orchestrate_historical.py    # Parallel loader (NEW)
├── metadata/                # Orchestration metadata (NEW)
│   ├── stations_config.json         # 10 station registry
│   ├── load_metadata.json           # Load history tracking
│   └── pipeline_config.json         # Pipeline settings
├── logs/                    # Orchestration logs
├── scripts/                 # Utility and test scripts
├── docs/                    # Research and planning
├── tests/                   # Test files
└── data/                    # Data lakehouse
```

See `docs/STRUCTURE_REORGANIZATION.md` for reorganization details (2025-11-12).

### Configuration (src/config.py)

**Key settings:**
- `STATIONS`: Dict of 10 stations (2 loaded, 8 ready)
- `DATE_RANGES`: Predefined ranges (full, 2024, 2025)
- `EDR_PARAMETERS`: Leave empty for all params (23 available)
- `PROJECT_ROOT`: Automatically calculated from config.py location

**To load more stations:**
```bash
# All stations already configured in metadata/stations_config.json
python src/orchestrate_historical.py --stations core_10 --start-year 2000 --end-year 2025
```

## Orchestration Features (NEW)

### Metadata Management

**System tracks:**
- Loaded date ranges per station
- Data gaps and missing periods
- Load history and timestamps
- Station groups (coastal, inland, airports, etc.)

**Usage:**
```python
from src.metadata_manager import MetadataManager

mm = MetadataManager()
mm.print_status_summary()  # Shows load status for all stations
mm.get_station_info('hupsel')  # Get station metadata
mm.get_stations_needing_load('core_10')  # Find incomplete stations
```

### Historical Orchestration

**Features:**
- Parallel downloads (configurable workers)
- Smart chunking (yearly for efficiency)
- Progress tracking with tqdm
- Automatic retry on failure
- Resume capability (skips already-loaded)
- Respects API rate limits

**Usage:**
```bash
# Load all configured stations
python src/orchestrate_historical.py --stations core_10 --start-year 2000 --end-year 2025

# Custom concurrency
python src/orchestrate_historical.py --stations core_10 --max-workers 10

# Force reload (skip resume)
python src/orchestrate_historical.py --stations currently_loaded --force
```

## Robustness Improvements (2025-11-16)

### 1. Fixed Date Calculation Bug
**Problem:** Crashes when day=31 (e.g., Jan 31 → Feb 31 doesn't exist)
**Fix:** Always use `day=1` when advancing months
```python
# Fixed in ingest_bronze_raw.py:160-162
current = current.replace(month=current.month + 1, day=1)
```

### 2. Gap Filling
**Problem:** 6 chunks failed in initial historical load due to date bug
**Solution:** Manually loaded missing chunks, all gaps now filled
**Result:** 99.6% data completeness (2000-2025)

### 3. Incremental Updates
**Problem:** Data only went to 2025-11-12, missing latest days
**Solution:** Custom date range loading
**Result:** Now up-to-date to 2025-11-16

## Quick Tips for Claude

**When loading historical data:**
- Use `orchestrate_historical.py` for bulk loads (not individual scripts)
- Check `metadata/load_metadata.json` for current status
- Use `--force` flag to reload already-loaded data

**When adding new stations:**
- Already configured in metadata (10 total)
- Just run: `python src/orchestrate_historical.py --stations core_10`

**When querying data:**
- DuckDB: Best for SQL queries
- Polars: Best for dataframe operations (faster, less memory)
- Pandas: Best for compatibility with existing code

**When debugging:**
- Check `logs/orchestration_historical.log`
- Use `MetadataManager().print_status_summary()`
- Verify API keys in `C:\AI-Projects\.env` (parent dir)

**Date handling:**
- Always use ISO format: `"2025-01-01T00:00:00Z"`
- Orchestrator handles chunking automatically
- Manual loads: Use `--start-date` and `--end-date`

## Common Tasks

**Load all 10 stations (recommended first step):**
```bash
python src/orchestrate_historical.py --stations core_10 --start-year 2000 --end-year 2025 --max-workers 5
```

**Check what's loaded:**
```bash
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```

**Get latest data (incremental update):**
```bash
# For each loaded station
python src/ingest_bronze_raw.py --station hupsel --start-date "2025-11-17T00:00:00Z" --end-date "2025-11-17T23:59:59Z"
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
```

**Query complete dataset:**
```bash
python src/query_demo.py  # Comprehensive analysis with all 3 tools
```

**Quick DuckDB query:**
```python
import duckdb
con = duckdb.connect()
con.execute("SELECT station_id, COUNT(*) as hours, MIN(timestamp) as start, MAX(timestamp) as end FROM 'data/silver/**/*.parquet' GROUP BY station_id").df()
```

## Performance Notes

**Loading Performance:**
- 1 year (1 station): ~12 seconds
- 25 years (2 stations): ~8 minutes with parallel loading
- 25 years (10 stations): ~45-60 minutes with 5 workers

**Query Performance:**
- Polars: 1.18x faster than Pandas
- Polars: 47% less memory than Pandas
- DuckDB: Sub-second queries on 316K+ rows

**Storage Efficiency:**
- Parquet compression: 4.9x vs JSON
- Per station (25 years): ~103 MB raw → ~22 MB silver

## Important Gotchas

1. **API Keys Location:**
   - In parent directory: `C:\AI-Projects\.env`
   - Claude cannot read this (security)
   - Scripts use `load_dotenv("../.env")`

2. **Monthly Partitioning:**
   - Don't aggregate into yearly files
   - Keeps flexibility for incremental updates
   - Enables efficient querying

3. **Schema Handling:**
   - Bronze Refined: Schema-on-read (flexible)
   - Silver: Fixed schema (enforced)
   - Never enforce schema in Bronze!

4. **Date Calculation:**
   - Fixed bug: always use day=1 when advancing months
   - Handles leap years correctly
   - Use ISO format with Z suffix

5. **Metadata Tracking:**
   - Orchestrator skips already-loaded data
   - Use `--force` to reload
   - Check `load_metadata.json` for status

6. **Parallel Loading:**
   - Default: 5 workers (safe for most systems)
   - Can increase to 10 for faster loads
   - Respects API rate limits (200 req/sec)

## Next Steps

**Immediate (recommended):**
1. Load all 10 configured stations (2000-2025)
2. Build automated daily updater
3. Create analysis notebooks

**Short term:**
4. Build Gold layer for aggregated analytics
5. Create dashboards (Streamlit)
6. Add data quality tests

**Long term:**
7. Machine learning models
8. Expand to all 77 KNMI stations
9. Integrate additional data sources

---

**Ready for production! 316,278 hours of validated weather data spanning 25+ years.**
