# Project Status & Handoff Document

**Last Updated:** 2025-11-16
**Status:** ✅ Medallion Architecture Complete (Bronze + Silver)
**Stations:** Hupsel (0-20000-0-06283) + Deelen (0-20000-0-06275)
**Data Coverage:** 2024-01-01 to 2025-11-12 (16,345 hours per station, 32,690 total)
**Project Structure:** ✅ Reorganized into professional package structure
**Query Tools:** ✅ DuckDB + Polars + Pandas integrated

---

## What We Built

A complete **medallion data lakehouse** for KNMI weather data using modern data engineering practices.

### Architecture Layers

```
data/
  bronze/
    raw/                    ← Immutable source of truth (EDR API responses)
      edr_api/
        station_id=0_20000_0_06283/
          year=2024/        (12 JSON files, ~3 MB)
          year=2025/        (11 JSON files, ~2.7 MB)

    refined/                ← Schema-on-read Parquet
      weather_observations/
        station_id=0_20000_0_06283/
          year=2024/        (12 Parquet files, ~340 KB)
          year=2025/        (11 Parquet files, ~310 KB)

  silver/                   ← Validated, cleaned, fixed schema
    weather_observations/
      station_id=0_20000_0_06283/
        year=2024/          (12 Parquet files, ~390 KB)
        year=2025/          (11 Parquet files, ~360 KB)
```

**Partitioning Strategy:** `station_id={id}/year={year}/month={month}/`

**Total Storage:** ~7 MB (5.7 MB raw + 650 KB refined + 750 KB silver)

---

## Project Structure

**Recently reorganized (2025-11-12)** into a professional package structure:

```
LocalWeatherDataProject/
├── src/                 # Core pipeline scripts
├── scripts/             # Utility and legacy scripts
├── docs/                # Documentation and research
├── tests/               # Test files and fixtures
├── data/                # Data lakehouse (Bronze/Silver/Gold)
└── notebooks/           # (Empty - for future analysis)
```

See `docs/STRUCTURE_REORGANIZATION.md` for full reorganization details.

## Key Scripts

### Data Ingestion & Transformation (in `src/`)

**⚠️ Run all commands from project root!**

| Script | Purpose | Usage |
|--------|---------|-------|
| `src/config.py` | Configuration (API keys from .env, paths, stations) | Referenced by all scripts |
| `src/ingest_bronze_raw.py` | Download from EDR API → Bronze Raw JSON | `python src/ingest_bronze_raw.py --station hupsel --date-range full` |
| `src/transform_bronze_refined.py` | Bronze Raw JSON → Bronze Refined Parquet | `python src/transform_bronze_refined.py --station hupsel --year 2024` |
| `src/transform_silver.py` | Bronze Refined → Silver (validated) | `python src/transform_silver.py --station hupsel` |
| `src/query_demo.py` | Demo queries (DuckDB + pandas) | `python src/query_demo.py` |

### Legacy/Utility Scripts (in `scripts/`)

- `scripts/download_data.py` - Old approach using Open Data API (NetCDF files)
- `scripts/download_file.py` - Download single NetCDF file
- `scripts/inspect_file.py` - Inspect NetCDF structure
- `scripts/test_edr_api.py` - Test EDR API connection
- `scripts/explore_edr_api.py` - Explore EDR capabilities
- `scripts/explore_open_data_api.py` - Test Open Data API

---

## Configuration

### API Keys (Secure Storage)

**Location:** `C:\AI-Projects\.env` (parent directory - Claude cannot read this)

```bash
KNMI_OPEN_DATA_API_KEY=your_open_data_key
KNMI_EDR_API_KEY=your_edr_key
```

### Available Stations (config.py)

- **Hupsel** (0-20000-0-06283) - ✅ Loaded (2024-2025)
- **Deelen** (0-20000-0-06275) - ✅ Loaded (2024-2025)
- **77 total stations** available via EDR API

### Date Ranges (config.py)

- `full`: 2024-01-01 to 2025-12-31
- `2024`: Full year 2024
- `2025`: Full year 2025

---

## Data Details

### Current Data Coverage

- **Total records:** 32,690 hours (2 stations × 16,345 hours each)
- **Date range:** 2024-01-01 00:00 to 2025-11-12 01:00
- **Stations:** Hupsel (0-20000-0-06283) + Deelen (0-20000-0-06275)
- **Missing months:** December 2025 (not yet available)

### Weather Parameters (21 available)

**Core measurements:**
- Temperature (°C): T, T10N (min), TD (dewpoint)
- Humidity (%): U
- Rainfall (mm): RH, DR (duration)
- Wind: DD (direction), FF (speed), FX (gust), FH (hourly avg)
- Solar: Q (radiation), SQ (sunshine duration)
- Other: EE (evaporation), IX (radiation index), VV (visibility), N (cloud cover), WW (weather code)

**Missing parameters** (defined in schema but not in source):
- Air pressure (P) - not available from this EDR collection
- Visibility, cloud cover, weather code - all NULL in current dataset

### Data Quality Metrics

- **Average quality score:** 0.79-0.80 (good)
- **Records with outliers:** 0.3-3.1% (very low)
- **Duplicates:** 0 (removed)
- **Missing values:** 100% have some (due to air_pressure_hpa not in source)

---

## Key Design Decisions

### 1. Two-Stage Bronze Layer

**Why:** Preserve raw data (JSON) while providing efficient querying (Parquet)

- **Bronze Raw:** Exact API responses for compliance/reprocessing
- **Bronze Refined:** Flattened Parquet with schema-on-read (no fixed schema)

### 2. Schema-on-Read vs Schema-on-Write

- **Bronze:** Schema-on-read (flexible, future-proof)
- **Silver:** Fixed schema enforced (standardized, validated)

### 3. Monthly Partitioning

**Why:** Balance between query performance and file count
- Alternative: Quarterly (fewer files) or Daily (too many files)
- Monthly works well for 1-100 stations

### 4. EDR API vs Open Data API

**Chosen:** EDR API
**Why:**
- Query specific stations (don't download all 12 stations)
- Clean JSON format (no NetCDF conversion)
- 77 stations available (vs 12 in NetCDF files)
- Much faster (minutes vs hours)

**Limitation:** EDR has data point limits (~100K per request)
- **Solution:** Chunk by month (avoids limits)

---

## Technical Challenges Solved

1. **API Rate Limits:** EDR returns 413 for requests >376K data points
   - **Solution:** Monthly chunking in `ingest_bronze_raw.py`

2. **Security:** API keys in code
   - **Solution:** `.env` in parent directory (Claude can't read)

3. **Unicode Issues:** Windows console doesn't support emojis/special chars
   - **Solution:** Use ASCII arrows (-> not →)

4. **Schema Flexibility:** Source data structure may change
   - **Solution:** Schema-on-read in Bronze Refined, enforce in Silver

5. **Data Quality:** No validation in Bronze
   - **Solution:** Quality scoring in Silver layer

---

## What's Working

✅ **Bronze Raw ingestion** - Downloads all data from EDR API
✅ **Bronze Refined transformation** - Converts to queryable Parquet
✅ **Silver layer** - Validates, cleans, scores quality
✅ **DuckDB queries** - Sub-second SQL queries on 32K+ rows
✅ **Polars integration** - Fast, memory-efficient dataframe operations (2025-11-16)
✅ **Multi-station support** - 2 stations loaded (Hupsel + Deelen)
✅ **Partitioning** - Efficient data organization
✅ **Security** - API keys protected
✅ **Documentation** - Scripts are well-documented
✅ **Project structure** - Professional package organization (2025-11-12)

---

## What's NOT Built Yet

❌ **Gold layer** - Aggregated/business-ready data
❌ **More stations** - Only 2 of 77 stations loaded so far
❌ **Automated pipeline** - Manual script execution
❌ **Data validation tests** - No automated quality checks
❌ **Incremental updates** - No daily/hourly refresh
❌ **Dashboards** - No visualization layer
❌ **Documentation** - No user guide for analysis

---

## Next Steps (Recommended Priority)

### Short Term (Next Session)

1. **Add more stations** (5-10 stations recommended)
   ```bash
   python ingest_bronze_raw.py --station deelen --date-range full
   python transform_bronze_refined.py --station deelen
   python transform_silver.py --station deelen
   ```

2. **Build Gold layer** for multi-station comparison
   - Daily aggregates across all stations
   - Station comparison tables
   - Extreme weather events catalog

3. **Create analysis notebooks**
   - Jupyter notebook for exploratory analysis
   - Climate trend analysis
   - Seasonal patterns

### Medium Term

4. **Automated pipeline**
   - Daily incremental updates
   - Orchestration (Prefect/Dagster/Airflow)
   - Error handling & notifications

5. **Data quality tests**
   - Automated validation checks
   - Anomaly detection
   - Completeness monitoring

6. **Visualization**
   - Dashboards (Streamlit/Plotly/Grafana)
   - Temperature/rainfall trends
   - Station comparisons

### Long Term

7. **Machine Learning**
   - Weather prediction models
   - Anomaly detection
   - Climate pattern recognition

8. **Additional data sources**
   - Combine with soil data
   - Crop data integration
   - Build comprehensive agricultural data platform

---

## How to Resume Work

### If Adding More Stations

```bash
# 1. Add station to src/config.py STATIONS dict (if not already there)

# 2. Download data
python src/ingest_bronze_raw.py --station {station_key} --date-range full

# 3. Transform to Bronze Refined
python src/transform_bronze_refined.py --station {station_key}

# 4. Transform to Silver
python src/transform_silver.py --station {station_key}

# 5. Query all stations
python src/query_demo.py  # DuckDB reads all stations automatically
```

### If Building Gold Layer

Create `transform_gold.py` following Silver pattern:
- Read from Silver layer (all stations)
- Aggregate by station/day/month
- Create comparison tables
- Save to `data/gold/`

### If Downloading Latest Data

```bash
# Re-run for 2025 (gets latest data)
python src/ingest_bronze_raw.py --station hupsel --date-range 2025
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
```

---

## Important Notes for Future Sessions

1. **API Keys are in parent directory** (`C:\AI-Projects\.env`)
   - Claude cannot read this file (security feature)
   - Scripts load from `../.env`

2. **Monthly partitioning is intentional**
   - Don't aggregate into yearly files
   - Keeps query flexibility

3. **Schema-on-read in Bronze Refined**
   - Don't enforce fixed schema
   - Let data define structure
   - Silver is where schema is enforced

4. **Data quality scores**
   - 100% missing values = expected (air_pressure not in source)
   - Focus on outlier % (currently <3%)

5. **File naming convention**
   - Bronze Raw: `YYYYMMDD_to_YYYYMMDD.json`
   - Bronze Refined/Silver: Same name as Bronze Raw but `.parquet`

---

## Quick Reference Commands

**⚠️ All commands must be run from project root!**

```bash
# View data
python src/query_demo.py

# Download new data
python src/ingest_bronze_raw.py --station hupsel --date-range 2025

# Full pipeline for new station
python src/ingest_bronze_raw.py --station deelen --date-range full && \
python src/transform_bronze_refined.py --station deelen && \
python src/transform_silver.py --station deelen

# Test EDR API
python scripts/test_edr_api.py

# Query with DuckDB (interactive)
python
>>> import duckdb
>>> con = duckdb.connect()
>>> con.execute("SELECT * FROM 'data/silver/**/*.parquet' LIMIT 10").df()
```

---

## Contact & Resources

- **KNMI Developer Portal:** https://developer.dataplatform.knmi.nl/
- **EDR API Docs:** https://developer.dataplatform.knmi.nl/edr-api
- **Available Stations:** Run `test_edr_api.py` to see all 77 stations
- **Data Dictionary:** See EDR API parameter documentation

---

## Session Summary

**What we accomplished in previous sessions:**
- ✅ Researched KNMI EDR API (vs Open Data API)
- ✅ Secured API keys (.env setup)
- ✅ Built Bronze Raw layer (JSON from EDR)
- ✅ Built Bronze Refined layer (schema-on-read Parquet)
- ✅ Built Silver layer (validated, fixed schema)
- ✅ Downloaded 2024-2025 data for Hupsel
- ✅ Created query demo (DuckDB + pandas)
- ✅ Analyzed data quality (0.79-0.80 score)
- ✅ Identified extreme weather events (36.5°C max!)

**What we accomplished (2025-11-12):**
- ✅ Completed project structure reorganization
- ✅ Moved core scripts to `src/`
- ✅ Moved utility scripts to `scripts/`
- ✅ Moved documentation to `docs/`
- ✅ Organized test files in `tests/`
- ✅ Updated all import paths and configuration
- ✅ Updated documentation (CLAUDE.md, PROJECT_STATUS.md)
- ✅ Created STRUCTURE_REORGANIZATION.md guide
- ✅ Tested scripts to verify everything works

**What we accomplished (2025-11-16):**
- ✅ Added second weather station (Deelen 0-20000-0-06275)
- ✅ Integrated Polars for modern dataframe operations
- ✅ Created comprehensive Polars analysis section with lazy evaluation
- ✅ Added performance comparison: Polars vs Pandas
- ✅ Implemented multi-station query support
- ✅ Fixed schema compatibility issues between stations
- ✅ Updated query demo with 3 tools: DuckDB + Polars + Pandas
- ✅ Performance results: Polars 1.2x faster, 50% less memory
- ✅ Fixed Windows Unicode compatibility issues

**Time saved vs old approach:**
- Old (Open Data API): ~18 hours download
- New (EDR API): ~10 minutes download
- **108x faster!** 🚀

**Performance improvements (Polars vs Pandas):**
- Loading: **1.18x faster**
- Memory: **49.9% reduction** (6.1 MB vs 12.1 MB)
- Queries: **Sub-second** with lazy evaluation

---

**Ready for next session! Just reference this document to continue.**
