# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Modern data lakehouse for KNMI weather data** using medallion architecture (Bronze/Silver/Gold layers).

Downloads hourly weather observations from KNMI EDR API, processes through data quality layers, and provides efficient querying with DuckDB. Currently contains 16,345 hours of data (2024-2025) for Hupsel station.

**Key Technologies:**
- KNMI EDR API (Environmental Data Retrieval) - primary source
- DuckDB for efficient OLAP queries on Parquet files
- Parquet for columnar storage with partitioning
- pandas/pyarrow for data processing
- python-dotenv for secure API key management

**Architecture:** Medallion (Bronze Raw → Bronze Refined → Silver → Gold*)
*Gold layer not yet implemented

**Output:** Queryable Parquet files partitioned by `station_id/year/month/`

## Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# API keys stored in C:\AI-Projects\.env (parent directory)
# Claude cannot read this file (security feature)
```

### Data Pipeline (Medallion Architecture)

**IMPORTANT:** All commands must be run from the project root directory.

**Full pipeline for a station:**
```bash
# 1. Bronze Raw: Download from EDR API
python src/ingest_bronze_raw.py --station hupsel --date-range full

# 2. Bronze Refined: Convert to Parquet
python src/transform_bronze_refined.py --station hupsel

# 3. Silver: Validate & clean
python src/transform_silver.py --station hupsel
```

**Incremental updates (add new months):**
```bash
python src/ingest_bronze_raw.py --station hupsel --date-range 2025
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
```

**Query the data:**
```bash
python src/query_demo.py  # Runs DuckDB queries + pandas analysis
```

**Test scripts:**
```bash
python scripts/test_edr_api.py  # Test EDR API connection
python scripts/explore_edr_api.py  # Explore EDR capabilities
```

### Available Stations

- **Hupsel** (0-20000-0-06283) - Currently loaded, 2024-2025
- **Deelen** (0-20000-0-06275) - Available but not loaded
- **77 total stations** - See `scripts/test_edr_api.py` for full list

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

### Data Flow

**Bronze Raw (JSON):**
- Source: KNMI EDR API `/collections/hourly-in-situ-meteorological-observations-validated/locations/{station_id}`
- Format: Raw JSON responses (CoverageJSON format)
- Why: Preserve exact API response for compliance/reprocessing
- Chunking: Monthly (to avoid EDR 376K data point limit)

**Bronze Refined (Parquet):**
- Transform: Flatten nested JSON → tabular Parquet
- Schema: **On-read** (no fixed schema, preserves all source fields)
- Why: Efficient columnar storage, future-proof for API changes
- Size: ~28 KB/month (10x compression vs JSON)

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
- Solution: Chunk by month (~744 hours × 23 params × 1 station = 17K points)

**API Keys (Secure):**
- Location: `C:\AI-Projects\.env` (parent directory)
- Variables: `KNMI_EDR_API_KEY`, `KNMI_OPEN_DATA_API_KEY`
- Loading: `load_dotenv("../.env")` in all scripts
- Security: Claude cannot read .env files

### Project Structure

**Recent Reorganization (2025-11-12):**
The project has been reorganized into a professional package structure:

```
LocalWeatherDataProject/
├── src/                  # Core pipeline scripts (run these!)
│   ├── config.py        # Configuration
│   ├── ingest_bronze_raw.py
│   ├── transform_bronze_refined.py
│   ├── transform_silver.py
│   └── query_demo.py
├── scripts/             # Utility scripts (testing, exploration)
├── docs/                # Research and planning documents
├── tests/               # Test files and fixtures
├── data/                # Data lakehouse (Bronze/Silver/Gold)
└── notebooks/           # (Empty - for future analysis)
```

See `docs/STRUCTURE_REORGANIZATION.md` for full details.

### Configuration (src/config.py)

**Key settings:**
- `STATIONS`: Dict of available stations (hupsel, deelen)
- `DATE_RANGES`: Predefined ranges (full, 2024, 2025)
- `EDR_PARAMETERS`: Leave empty for all params (23 available)
- `PROJECT_ROOT`: Automatically calculated from config.py location

**To add a station:**
1. Add to `STATIONS` dict in src/config.py
2. Run ingestion pipeline (see Commands section)
