# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Production-ready data lakehouse for KNMI weather data** using medallion architecture (Bronze/Silver/Gold layers) with automated orchestration.

Downloads hourly weather observations from KNMI EDR API, processes through data quality layers, and provides efficient querying with multiple tools. Currently contains **316,278 hours of data (2000-2025)** for 2 stations: Hupsel and Deelen. **8 more stations loading now with v2 multi-station optimization (93.5% fewer API calls).**

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

### Historical Data Loading (Recommended - v2 Multi-Station)

**IMPORTANT:** All commands must be run from the project root directory.

**🚀 NEW: v2 Multi-Station Batch Loading (93.5% fewer API calls!)**

**Load all 10 configured stations (2000-2025):**
```bash
# Multi-station batch load (~80-90 minutes for 8 stations, 2000-2025)
# Uses optimized batching: 8 stations per API call, 2-month chunks
python src/orchestrate_historical_v2.py --stations not_loaded --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2

# Or for all 10 stations (if starting fresh)
python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2

# Check load status
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```

**Load specific station groups:**
```bash
# Load coastal stations
python src/orchestrate_historical_v2.py --stations coastal --start-year 2000 --end-year 2025 --batch-size 3 --chunk-months 2

# Load single station (backward compatible)
python src/orchestrate_historical_v2.py --station de_bilt --start-year 2000 --end-year 2025
```

**Legacy v1 (archived):**
Old single-station loader available in `archive/v1_single_station/` for fallback.

### Manual Pipeline (for custom date ranges)

**Full pipeline for a station:**
```bash
# 1. Bronze Raw: Download from EDR API (single station)
python src/ingest_bronze_raw.py --station hupsel --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"

# OR multi-station (NEW v2 feature!)
python src/ingest_bronze_raw.py --stations hupsel,deelen,de_bilt --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"

# 2. Bronze Refined: Convert to Parquet
python src/transform_bronze_refined.py --station hupsel --year 2024

# 3. Silver: Validate & clean
python src/transform_silver.py --station hupsel --year 2024
```

**Incremental updates (add latest data):**
```bash
# Single station
python src/ingest_bronze_raw.py --station hupsel --start-date "2025-11-17T00:00:00Z" --end-date "2025-11-17T23:59:59Z"

# ALL stations at once (future daily updater will use this!)
python src/ingest_bronze_raw.py --stations hupsel,deelen,de_bilt,schiphol,rotterdam,vlissingen,maastricht,eelde,den_helder,twenthe --start-date "2025-11-17T00:00:00Z" --end-date "2025-11-17T23:59:59Z"

# Then transform each
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

**Why multi-station batching with bi-monthly chunks? (v2 optimization)**
- **Multi-station batching**: API supports comma-separated station IDs - 93.5% fewer API calls!
- **Bi-monthly chunks**: 2-month chunks with 8 stations = 264,960 data points (70% of 376K limit)
- **Result**: 8 stations × 25 years = 156 API calls (vs 2,400 single-station!)
- **Scalability**: Can load 48-60 stations per session (under 1000 call limit)

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
- **v2 Solution**: Multi-station batching + bi-monthly chunks
  - 8 stations × 1,440 hours × 23 params = 264,960 points (70% of limit)
  - One API call loads 8 stations for 2 months!
  - 93.5% fewer API calls vs single-station approach

**API Keys (Secure):**
- Location: `C:\AI-Projects\.env` (parent directory)
- Variables: `KNMI_EDR_API_KEY`, `KNMI_OPEN_DATA_API_KEY`
- Loading: `load_dotenv("../.env")` in all scripts
- Security: Claude cannot read .env files

### Project Structure

**Recent Changes:**
- **2025-11-17**: 🚀 v2 Multi-station optimization - 93.5% fewer API calls!
- **2025-11-16**: Added orchestration and metadata tracking

```
LocalWeatherDataProject/
├── src/                     # Core pipeline scripts
│   ├── config.py                       # Configuration (10 stations, API keys, paths)
│   ├── ingest_bronze_raw.py            # EDR API → Bronze Raw (v2 multi-station!)
│   ├── orchestrate_historical_v2.py    # Multi-station batch loader (NEW v2)
│   ├── transform_bronze_refined.py     # JSON → Parquet
│   ├── transform_silver.py             # Parquet → Silver
│   ├── query_demo.py                   # Multi-tool query demos
│   └── metadata_manager.py             # Metadata tracking
├── archive/
│   └── v1_single_station/              # Legacy single-station code (backup)
├── metadata/                # Orchestration metadata
│   ├── stations_config.json         # 10 station registry
│   ├── load_metadata.json           # Load history tracking
│   └── pipeline_config.json         # Pipeline settings
├── logs/                    # Orchestration logs
├── scripts/                 # Utility and test scripts
│   └── test_multi_station_api.py    # Multi-station API tester (NEW)
├── docs/                    # Research and planning
│   ├── API_OPTIMIZATION_OPPORTUNITIES.md  # v2 optimization analysis (NEW)
│   └── MULTI_STATION_OPTIMIZATION_SUMMARY.md  # Complete v2 guide (NEW)
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
# All 10 stations already configured in metadata/stations_config.json
# Use v2 multi-station optimizer for maximum efficiency!
python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2
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

### Historical Orchestration (v2 - Multi-Station Optimization)

**🚀 v2 Features (93.5% fewer API calls!):**
- **Multi-station batching**: Query multiple stations in one API call
- **Optimal chunking**: Dynamic calculation of chunk size based on batch size
- **Smart data point limits**: Maximizes efficiency while staying under 376K limit
- Progress tracking with detailed logging
- Automatic retry on failure
- Resume capability (skips already-loaded)
- Respects API rate limits (well under 200 req/sec)

**Performance:**
- v1 (single-station): 2,400 API calls for 8 stations × 25 years
- v2 (multi-station): 156 API calls for same data (93.5% reduction!)
- Enables loading 48-60 stations per session (under 1000 call limit)

**Usage:**
```bash
# Load all configured stations with optimal settings
python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2

# Load specific station group
python src/orchestrate_historical_v2.py --stations coastal --start-year 2000 --end-year 2025 --batch-size 3 --chunk-months 2

# Single station (backward compatible with v1)
python src/orchestrate_historical_v2.py --station de_bilt --start-year 2000 --end-year 2025
```

**Legacy v1:** Available in `archive/v1_single_station/orchestrate_historical.py` for fallback.

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
- 🚀 Use `orchestrate_historical_v2.py` for bulk loads (93.5% fewer API calls!)
- Default: `--batch-size 8 --chunk-months 2` (optimal for most scenarios)
- Check `metadata/load_metadata.json` for current status
- Legacy v1 available in `archive/v1_single_station/` if needed

**When adding new stations:**
- Already configured in metadata (10 total)
- v2 command: `python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2`

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

**Load all 10 stations (recommended first step - v2 optimized!):**
```bash
python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2
```

**Check what's loaded:**
```bash
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```

**Get latest data (incremental update - multi-station!):**
```bash
# All 10 stations at once (v2 feature!)
python src/ingest_bronze_raw.py --stations hupsel,deelen,de_bilt,schiphol,rotterdam,vlissingen,maastricht,eelde,den_helder,twenthe --start-date "2025-11-17T00:00:00Z" --end-date "2025-11-17T23:59:59Z"

# Then transform each station
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
# (repeat for other stations)
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

**Loading Performance (v2 Multi-Station):**
- **API efficiency**: 93.5% fewer calls vs v1 single-station
- 25 years (8 stations): ~80-90 minutes (156 API calls vs 2,400 single-station!)
- 25 years (10 stations): ~90-120 minutes estimated
- **Scalability**: Can load 48-60 stations per session (under 1000 API call limit)
- **Path to 70+ stations**: 2-3 sessions total (2-3 hours for entire KNMI network!)

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

6. **v2 Multi-Station Optimization (NEW - 2025-11-17):**
   - Always use `orchestrate_historical_v2.py` for new loads
   - Default settings: `--batch-size 8 --chunk-months 2` (optimal)
   - Legacy v1 code archived in `archive/v1_single_station/`
   - 93.5% fewer API calls = massive scalability improvement
   - Can query multiple stations in single API call using comma-separated IDs

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
