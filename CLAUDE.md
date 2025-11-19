# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **data lakehouse for Dutch weather data** using the **medallion architecture** (Bronze → Silver → Gold) to process historical hourly weather observations from the KNMI (Royal Netherlands Meteorological Institute) EDR API. The project handles **immutable historical data** (1990-2025, 36 years) for 10 core weather stations with 93.5% API optimization through intelligent batching.

**Current Phase**: Bronze Raw layer is production-ready (360 station-years loaded). Focus is on hardening Bronze Refined transformation and developing the Silver layer.

## Commands

### Bronze Raw Ingestion (Production-Ready)

```bash
# Ingest all data for 10 core stations (1990-2025)
# Idempotent - skips already-loaded years automatically
python -m data_orchestration.bronze_raw.orchestrate --stations core_10 --start-year 1990 --end-year 2025

# Ingest specific station and year range
python -m data_orchestration.bronze_raw.orchestrate --stations hupsel --start-year 2024 --end-year 2025

# View ingestion metadata for a station
python -m data_orchestration.bronze_raw.view_metadata --station hupsel
```

### Transformations (In Development)

```bash
# Transform Bronze Raw (JSON) → Bronze Refined (Parquet)
python -m src.transform_bronze_refined --station hupsel --year 2024

# Transform Bronze Refined → Silver (Validated Parquet)
python -m src.transform_silver --station hupsel --year 2024
```

### Queries

```bash
# Run demo queries (DuckDB, Polars, Pandas)
python src/query_demo.py
```

### Environment Setup

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env and add KNMI_EDR_API_KEY from https://developer.dataplatform.knmi.nl/
```

## Architecture

### Medallion Layers

```
KNMI EDR API
    ↓
Bronze Raw (JSON)      - Immutable source of truth, audit trail
    ↓
Bronze Refined (Parquet) - Schema-on-read, query-optimized (6-7x compressed)
    ↓
Silver (Parquet)       - Fixed schema, validated, quality scored
    ↓
Gold (Future)          - Aggregated metrics, business intelligence
```

### Key Architectural Patterns

1. **Per-Station Parallelization**: Each station loads independently in its own thread (ThreadPoolExecutor with 10 workers). Chosen for simplicity, fault isolation, and resume capability over multi-station API batching.

2. **1-Year Chunks**: Each API call fetches 1 year of data (201K data points = 54% of 376K API limit). Simple, safe, matches natural query patterns.

3. **Two Bronze Layers**: Bronze Raw (immutable JSON) serves as audit trail and enables reprocessing. Bronze Refined (Parquet) optimizes for queries without rigid schema enforcement.

4. **Schema Evolution**: Bronze Refined uses schema-on-read (no enforcement) to handle API changes. Silver layer enforces fixed schema with validation.

5. **Metadata-Driven Resume**: Per-station JSON metadata files track loaded years, enabling instant resume (0.1s for 26 years) and idempotent re-runs.

6. **Atomic Writes**: Write-to-temp + `os.replace()` pattern prevents partial file writes.

7. **Hive-Style Partitioning**: `station_id={id}/year={year}/month={month}` enables efficient partition pruning in queries.

### Directory Structure

```
data_orchestration/bronze_raw/  - Bronze Raw ingestion orchestrator (PRODUCTION-READY)
    orchestrate.py              - Main CLI with ThreadPoolExecutor coordination
    station_pipeline.py         - Independent per-station pipeline
    api_client.py               - EDR API client with retry logic
    storage.py                  - Atomic file writes
    metadata_tracker.py         - Per-station metadata management
    structured_logger.py        - JSON + human-readable logging

src/                            - Transformation logic (layer transitions)
    config.py                   - Global project configuration
    transform_bronze_refined.py - JSON → Parquet (schema-on-read) [IN DEVELOPMENT]
    transform_silver.py         - Parquet → Validated Parquet [IN DEVELOPMENT]
    query_demo.py               - DuckDB/Polars/Pandas query examples

metadata/                       - Configuration and ingestion tracking
    stations_config.json        - Station registry (10 stations, expandable to 77)
    pipeline_config.json        - Pipeline settings
    bronze_raw/{station}_metadata.json - Per-station ingestion metadata

data/                           - Data lake (not in git)
    bronze/raw/                 - Immutable JSON from API (~1.3 GB)
    bronze/refined/             - Query-optimized Parquet (~200 MB)
    silver/                     - Validated Parquet with quality scores
    gold/                       - Aggregated metrics (future)

docs/architecture/              - High-level design documents
docs/research/                  - API optimization research
docs/ingestion_strategy/        - Detailed ingestion plans

logs/                           - Runtime logs (*.log and *.json)
```

### Data Flow

**Bronze Raw Ingestion** (per-station parallelization):
```
Orchestrator (ThreadPoolExecutor, 10 workers)
    ↓
10 Parallel StationPipeline instances
    ↓ (for each year in range)
API Client (tenacity retry, exponential backoff)
    ↓
Atomic Storage (write-to-temp + os.replace)
    ↓
Metadata Tracker (per-station JSON files)
```

**Bronze Refined Transformation** (schema-on-read):
```
Bronze Raw JSON (CoverageJSON format)
    ↓ (flatten nested structure)
Pandas DataFrame (inferred schema)
    ↓ (add year/month partitions)
Parquet with monthly partitioning
```

**Silver Layer Transformation** (validation & quality):
```
Bronze Refined Parquet (flexible schema)
    ↓ (enforce fixed schema)
Validation (range checks, required fields)
    ↓ (clean data)
Quality Scoring (0.0-1.0 per record)
    ↓ (detect outliers)
Silver Parquet (production-ready)
```

### Configuration Management

- **Global Config**: `src/config.py` - API endpoints, paths, rate limits
- **Station Registry**: `metadata/stations_config.json` - 10 stations with IDs, names, coordinates, station groups
- **Per-Station Metadata**: `metadata/bronze_raw/{station}_metadata.json` - Tracks loaded years, file sizes, timestamps
- **API Keys**: `.env` file (use `.env.example` as template)

### Immutable Historical Data

Weather data never changes retroactively ("weather of yesterday will never be updated"). This enables:
- Write-once read-many optimizations
- No need for update logic in historical data
- Simplified metadata tracking (year loaded = year complete)
- Safe parallel loading without coordination

## Development Principles

### Pragmatism Over Perfection

- **Simple working solutions beat complex "perfect" designs**: ThreadPoolExecutor was chosen over asyncio for simplicity despite async being "more modern"
- **1-year chunks chosen over "optimal" 2-month calculations** for simplicity and natural boundaries
- **Measure first, optimize if needed**: Current performance (0.27s/year, 70s for full load) made multi-station batching unnecessary

### Idempotency is Critical

- All operations must be safely re-runnable
- Use metadata tracking and skip logic
- Bronze Raw orchestrator skips already-loaded years automatically
- Transformations should check for existing output before reprocessing

### Separation of Concerns (Medallion Layers)

- **Bronze Raw**: Immutable audit trail (exact API responses)
- **Bronze Refined**: Query optimization without schema enforcement
- **Silver**: Data quality, validation, standardization
- **Gold**: Business aggregations

Don't mix responsibilities between layers.

### Metadata is King

- Per-station metadata enables instant resume, monitoring, debugging
- Track: timestamps, file paths, sizes, row counts, quality metrics
- Enhanced metadata in Bronze Raw enabled 0.1s resume for 26 years

### Observability

- Structured logging (JSON + human-readable) in `logs/` directory
- Event types: `year_loaded`, `station_complete`, `pipeline_complete`
- Performance metrics in all events (duration, throughput)
- UTC timestamps for analysis

## Technology Stack

- **DuckDB**: Embedded OLAP database for SQL queries on Parquet
- **Polars**: Fast dataframe library (10x faster than Pandas for large datasets)
- **Pandas**: Traditional dataframe analysis
- **PyArrow**: Parquet file I/O
- **Tenacity**: Retry logic with exponential backoff
- **Requests**: HTTP API calls (synchronous, chosen over aiohttp for simplicity)
- **ThreadPoolExecutor**: Parallel station loading (chosen over asyncio)
- **Python 3.10+**: Modern Python features

## Current Development Focus

### Bronze Refined Hardening (Priority: HIGH)

The existing `src/transform_bronze_refined.py` needs standardization:

1. **Schema-on-read**: Let Parquet infer schema, no enforcement
2. **Flatten CoverageJSON**: Convert nested structure to tabular
3. **Monthly partitioning**: `station_id={id}/year={year}/month={month}`
4. **Idempotency**: Safe to re-run without corruption
5. **Metadata tracking**: Track transformation status per station-year
6. **Create orchestrator**: Parallel transformation like Bronze Raw

Expected: 1.3 GB JSON → ~200 MB Parquet (6-7x compression)

### Silver Layer Development (Priority: HIGH)

The `src/transform_silver.py` script needs implementation:

1. **Fixed schema**: Strict column names, types, constraints
2. **Validation**: Range checks (temp: -50 to +50°C), required fields
3. **Cleaning**: Handle KNMI conventions (rainfall -1 → 0.0)
4. **Quality scoring**: 0.0-1.0 score per record based on completeness, outliers
5. **Outlier detection**: Statistical (IQR, z-score) + domain knowledge
6. **Standardized naming**: `T` → `temperature_celsius`
7. **New columns**: `quality_score`, `has_outliers`, `outlier_fields`, `completeness`

## Important Context

### Performance Metrics

- **Bronze Raw**: 360 station-years loaded (10 stations × 36 years)
- **Latest run**: 259 years in 69.8 seconds (0.27s/year average)
- **Success rate**: 100% (no failures)
- **Resume speed**: 0.1s for 26 years (instant)
- **Storage**: ~1.3 GB JSON (Bronze Raw), expected ~200 MB Parquet (Bronze Refined)

### API Limits

- **Rate limit**: 200 requests/second, 1000 requests/hour
- **Data point limit**: 376,000 data points per request
- **Current usage**: 1 year = 201,480 data points (54% of limit)
- **Headroom**: 50x increase possible before hitting rate limits

### Station Groups

Defined in `metadata/stations_config.json`:
- **core_10**: Hupsel, Deelen, De Bilt, Schiphol, Rotterdam, Vlissingen, Maastricht, Eelde, Den Helder, Twenthe
- Expandable to all 77 KNMI stations

## Documentation

- **README.md**: Project overview and quick start
- **GEMINI.md**: Current phase status (Bronze Refined focus)
- **docs/architecture/**: High-level design documents
  - `BRONZE_V3_ARCHITECTURE_AND_NEXT_STEPS.md`: Current state and next steps
  - `ORCHESTRATION_V3_DESIGN.md`: Phase-based parallel ingestion design
- **docs/research/**: API optimization research and multi-station batching studies
- **docs/ingestion_strategy/**: Detailed Bronze ingestion plans

Read the comprehensive documentation in `docs/` before making architectural changes.

## Testing Strategy

Currently uses **integration testing** through working scripts rather than formal unit tests:

1. **Incremental testing**: Test with 1 station/1 year before full load
2. **Idempotency tests**: Re-run same command, verify skip logic
3. **Query validation**: Compare results across DuckDB, Polars, Pandas
4. **Data quality checks**: Verify no NULLs in required fields, range checks

Recommended to add pytest-based tests for transformation logic and validation rules.

## Future Phases

- **Phase 3**: Query optimization and testing with full 36-year dataset
- **Phase 4**: Daily incremental updates with multi-station batching
- **Phase 5**: Gold layer (aggregated metrics, dashboards, ML features)
