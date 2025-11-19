# Bronze Raw v3 Architecture & Next Steps

**Date**: 2025-11-18
**Status**: Bronze Raw Layer PRODUCTION-READY ✅
**Current Coverage**: 10 stations × 36 years (1990-2025) = **360 station-years**
**Latest Load Performance**: 259 years loaded in 69.8 seconds (0.27s/year average)
**Future Target**: All 77 KNMI stations (eventually)

---

## Executive Summary

We've successfully built and deployed a **production-ready Bronze Raw ingestion system** that loads historical weather data from the KNMI EDR API with exceptional performance and reliability. The system uses **per-station parallelization** with **1-year chunks**, achieving complete data coverage for all 10 core weather stations across **36 years (1990-2025)** with exceptional performance.

**Key Achievements**:
- ✅ **100% Success Rate**: All 10 stations loaded without failures
- ✅ **High Performance**: 0.27s per year average (259 years in 69.8 seconds)
- ✅ **Enhanced Observability**: Dual logging (human-readable + structured JSON)
- ✅ **Professional Metadata**: File paths, timestamps, sizes, summaries
- ✅ **Robust Architecture**: Atomic writes, retry logic, resume capability
- ✅ **Simple & Maintainable**: Avoided over-engineering, focused on pragmatism

---

## 1. Bronze Raw v3 Implementation

### Architecture Overview

The Bronze Raw v3 ingestion system is built around a **per-station parallel architecture** using Python's ThreadPoolExecutor:

```
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator (Main)                        │
│  - Manages 10 concurrent station workers                    │
│  - Coordinates ThreadPoolExecutor                            │
│  - Aggregates results & generates summary                   │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
  ┌─────────┐          ┌─────────┐          ┌─────────┐
  │Station 1│          │Station 2│   ...    │Station N│
  │Pipeline │          │Pipeline │          │Pipeline │
  └─────────┘          └─────────┘          └─────────┘
        │                    │                    │
        ▼                    ▼                    ▼
  [Year Loop: 2000-2025]  [Year Loop]         [Year Loop]
        │                    │                    │
        ▼                    ▼                    ▼
  ┌──────────────────────────────────────────────────┐
  │          API Client (with Retry Logic)           │
  └──────────────────────────────────────────────────┘
        │
        ▼
  ┌──────────────────────────────────────────────────┐
  │     Atomic Storage (Write + Rename Pattern)      │
  └──────────────────────────────────────────────────┘
        │
        ▼
  ┌──────────────────────────────────────────────────┐
  │         Metadata Tracker (Per-Station)           │
  └──────────────────────────────────────────────────┘
```

### Core Components

#### 1. **Orchestrator** (`data_orchestration/bronze_raw/orchestrate.py`)
- **Purpose**: Main CLI entry point for parallel ingestion
- **Features**:
  - ThreadPoolExecutor with 10 concurrent workers (optimal from API testing)
  - API connection pre-check before starting ingestion
  - Real-time progress logging with detailed summaries
  - Comprehensive error handling with per-station tracking
  - CLI with flexible arguments (single station, multiple stations, or `core_10`)

#### 2. **Station Pipeline** (`data_orchestration/bronze_raw/station_pipeline.py`)
- **Purpose**: Independent pipeline for each station
- **Features**:
  - Loads 1 year at a time (optimal chunk size: 365×24×23 = ~201K data points)
  - Metadata-aware skip logic (idempotent, resume-capable)
  - File size tracking for each year
  - Performance metrics (duration per year)
  - Structured event logging

#### 3. **API Client** (`data_orchestration/bronze_raw/api_client.py`)
- **Purpose**: Robust EDR API interactions
- **Features**:
  - Retry logic with tenacity (exponential backoff)
  - Honors `Retry-After` headers from API
  - Timeout handling (60s per request)
  - HTTP status code error handling
  - Connection test function for pre-flight checks

#### 4. **Storage** (`data_orchestration/bronze_raw/storage.py`)
- **Purpose**: Atomic file operations
- **Features**:
  - Write-to-temp + `os.replace()` pattern (atomic on Windows)
  - Automatic cleanup of temp files on failure
  - Hive-style partitioning: `station_id={id}/year={year}/data.json`
  - UTF-8 encoding with pretty-printed JSON

#### 5. **Metadata Tracker** (`data_orchestration/bronze_raw/metadata_tracker.py`)
- **Purpose**: Per-station metadata management
- **Features**:
  - One JSON file per station in `metadata/bronze_raw/`
  - Tracks: year, loaded_at timestamp, file_path, size_mb
  - Summary section with totals and year range
  - Backward compatible (migrates old format automatically)
  - Efficient lookup for resume capability

#### 6. **Structured Logger** (`data_orchestration/bronze_raw/structured_logger.py`)
- **Purpose**: Industry-standard observability
- **Features**:
  - Dual logging: human-readable + JSON
  - Event types: `year_loaded`, `station_complete`, `pipeline_complete`
  - Automatic UTC timestamps
  - Performance metrics in all events
  - Queryable JSON logs for analysis

### Configuration

All settings are centralized in `data_orchestration/bronze_raw/config.py`:

- **Station Registry**: Loads from `metadata/stations_config.json`
- **API Settings**: EDR endpoint, collection name, retry configuration
- **Chunk Size**: 1 year (optimal for API limit)
- **Concurrency**: 10 workers (proven optimal from testing)
- **Paths**: Logs, metadata, data output directories

### Performance Metrics

**Current Data Coverage**:

| Metric | Value |
|--------|-------|
| Stations | 10 (core stations) |
| Total Coverage | **1990-2025 (36 years)** |
| **Total Station-Years** | **360** |
| Future Target | All 77 KNMI stations |

**Latest Load Performance (2025-11-18, final 2000-2025 batch)**:

| Metric | Value |
|--------|-------|
| Years Loaded This Run | 259 (2000-2025, minus 1 skip) |
| Total Duration | 69.84 seconds (1.16 minutes) |
| **Average per Year** | **0.27 seconds** |
| Success Rate | **100%** |
| Failures | 0 |

**Per-Station File Sizes**:

| Station | Avg Size/Year |
|---------|---------------|
| Hupsel | 2.48 MB |
| Deelen | 3.88 MB |
| De Bilt | 3.76 MB |
| Schiphol | 3.76 MB |
| Rotterdam | 3.76 MB |
| Vlissingen | 3.77 MB |
| Maastricht | 3.76 MB |
| Eelde | 3.76 MB |
| Den Helder | 3.77 MB |
| Twenthe | 3.90 MB |

**Total Storage**: ~1.3 GB for 360 station-years of JSON data (Bronze Raw)

---

## 2. Optimizations Achieved

### ✅ Already Implemented

1. **Per-Station Parallelization**
   - 10 concurrent workers = 10 stations loading simultaneously
   - Each station independent, no cross-dependencies
   - ThreadPoolExecutor proven optimal (vs asyncio complexity)

2. **Optimal Chunk Size**
   - 1-year chunks = 201,480 data points (54% of 376K API limit)
   - Simple, intuitive, matches natural query patterns
   - Plenty of margin for API stability

3. **Metadata-Driven Resume**
   - Skip already-loaded years automatically
   - Re-running is instant (0.1s for 26 years)
   - Perfect for incremental updates

4. **Atomic Writes**
   - Write-to-temp + rename pattern
   - No partial files on failure
   - Safe for concurrent access

5. **Comprehensive Retry Logic**
   - Exponential backoff with jitter
   - Honors API `Retry-After` headers
   - Automatic recovery from transient failures

6. **Structured Observability**
   - JSON logs for automated analysis
   - Human logs for debugging
   - Performance metrics for every operation

### 🔮 Possible Future Optimizations

#### A. **API-Level Optimizations**

**Current**: 1 API call per station-year (360 calls for full historical coverage)
**Opportunity**: Multi-station batching

The EDR API supports querying multiple stations in a single request using comma-separated station IDs:

```
GET /locations/{station1},{station2},{station3}?datetime=2024-01-01/2024-12-31
```

**Potential Gains**:
- **Batch 10 stations × 1 year**: 1 API call vs 10 calls = 90% reduction
- **Load 360 station-years**: 36 API calls vs 360 = **90% reduction**
- **Trade-off**: More complex error handling (entire batch fails if one station fails)

**Recommendation**: ⚠️ **NOT recommended** for historical loads
- Current performance is already excellent (70 seconds for full load)
- Batching adds complexity (partial failure handling)
- Individual station failures would require retry logic for entire batch
- 90% of 70 seconds = 7 seconds saved (not worth the complexity)
- **Better use case**: Daily incremental updates (fetch all 10 stations for "yesterday")

#### B. **Storage Optimizations**

**Current**: Individual JSON files per station-year (~1.3 GB total for 360 station-years)
**Opportunities**:

1. **JSON Compression**:
   - Use gzip compression on JSON files
   - Expected: 70-80% compression (~1.3 GB → ~270 MB)
   - Trade-off: Slower reads (must decompress)
   - **Recommendation**: ✅ **Worth considering** if storage becomes an issue

2. **Immediate Parquet Conversion**:
   - Skip Bronze Raw layer entirely, write Parquet directly
   - Expected: 5-10x compression vs JSON
   - Trade-off: No source-of-truth JSON for compliance/debugging
   - **Recommendation**: ❌ **Not recommended** - Bronze Raw serves as immutable audit trail

#### C. **Concurrency Tuning**

**Current**: 10 workers (one per station)
**Opportunity**: Increase to 20-50 workers for larger station counts

**Analysis**:
- API limit: 200 req/sec, 1000 req/hour
- Current usage: ~4 req/sec (typical load performance)
- Headroom: **50x increase possible** before hitting rate limits

**Recommendation**: ✅ **Increase to 20 workers** when loading 20+ stations
- For current 10 stations: no benefit (limited by station count, not API)
- For 50+ stations: could reduce load time from 5 minutes to 2 minutes

#### D. **Incremental Update Strategy**

**Current**: Manual re-run with `--start-year` and `--end-year`
**Opportunity**: Automated daily updater

**Proposed**: Daily cron job that:
1. Queries all 10 stations for "yesterday" (multi-station batch API call)
2. Appends new data to 2025 files
3. Triggers Bronze Refined & Silver transformations
4. Runs in <10 seconds total

**Recommendation**: ✅ **High priority** for Phase 3 (after Silver layer complete)

---

## 3. Bronze Refined Layer Strategy

### Current State

**Existing Script**: `src/transform_bronze_refined.py`
**Status**: Functional but needs standardization

### Recommended Approach: Schema-on-Read

The Bronze Refined layer should follow **modern data lake best practices**:

```
Bronze Raw (JSON)  →  Bronze Refined (Parquet with schema-on-read)
```

#### Key Principles

1. **Format Standardization**
   - Input: Nested JSON (CoverageJSON from EDR API)
   - Output: Columnar Parquet (query-optimized)
   - **No schema enforcement** - let Parquet infer types

2. **Basic Flattening**
   - Convert nested JSON → tabular structure
   - Extract timestamp, station_id, all parameters
   - Preserve all source fields (future-proof for API changes)

3. **Partitioning**
   - Maintain Hive-style: `station_id={id}/year={year}/month={month}`
   - **Monthly partitioning** recommended:
     - Balance between too many files (daily) and too large (yearly)
     - Perfect for queries like "all data for Jan 2024"
     - Enables efficient incremental updates

4. **Idempotency**
   - Safe to re-run without corruption
   - Use same atomic write pattern as Bronze Raw
   - Metadata tracking for resume capability

#### Recommended Implementation

```python
# Pseudocode for Bronze Refined transformation
def transform_to_bronze_refined(station_id: str, year: int):
    """
    Transform Bronze Raw JSON → Bronze Refined Parquet

    Input:  data/bronze/raw/edr_api/station_id={id}/year={year}/data.json
    Output: data/bronze/refined/edr_api/station_id={id}/year={year}/month={month}/*.parquet
    """

    # 1. Read JSON
    raw_data = read_json(f"bronze/raw/.../year={year}/data.json")

    # 2. Flatten CoverageJSON structure
    df = flatten_coverage_json(raw_data)
    # Result: DataFrame with columns: timestamp, station_id, T, RH, P, etc.

    # 3. Add partition columns
    df['year'] = df['timestamp'].dt.year
    df['month'] = df['timestamp'].dt.month

    # 4. Write to Parquet (schema-on-read)
    df.to_parquet(
        path="bronze/refined/edr_api",
        partition_cols=['station_id', 'year', 'month'],
        engine='pyarrow',
        compression='snappy',
        index=False
    )

    # 5. Update metadata
    metadata.mark_transformed(station_id, year, month, file_size, row_count)
```

#### Expected Benefits

- **6-7x compression**: ~1.3 GB JSON → ~200 MB Parquet
- **Fast queries**: Columnar format perfect for DuckDB/Polars
- **Future-proof**: No rigid schema = no breaking changes when API evolves
- **Partition pruning**: Query only relevant months

#### Orchestration Strategy

**Reuse Bronze Raw architecture**:

```python
# Create bronze_refined orchestrator (similar to bronze_raw)
python -m data_orchestration.bronze_refined.orchestrate \
    --stations core_10 \
    --start-year 2000 \
    --end-year 2025
```

**Components**:
- `data_orchestration/bronze_refined/orchestrate.py` (parallel coordinator)
- `data_orchestration/bronze_refined/station_pipeline.py` (per-station transformer)
- `data_orchestration/bronze_refined/metadata_tracker.py` (transformation tracking)
- Reuse same logging infrastructure

---

## 4. Silver Layer Strategy

### Purpose

The Silver layer is where **strict data quality** and **schema enforcement** happen:

```
Bronze Refined (flexible schema)  →  Silver (fixed schema + quality)
```

### Key Features

1. **Fixed Schema Enforcement**
   - Define exact column names, types, constraints
   - Reject records that don't match schema
   - Standardized naming (e.g., `T` → `temperature_celsius`)

2. **Data Validation**
   - Range checks (temperature: -50 to +50°C)
   - Required fields (timestamp, station_id must exist)
   - Type validation (numeric fields must be numbers)

3. **Data Cleaning**
   - Handle KNMI conventions (rainfall -1 → 0.0)
   - Standardize units (ensure consistency)
   - Deduplication (same timestamp+station)

4. **Quality Scoring**
   - Assign quality score to each record (0.0 to 1.0)
   - Flag suspicious values (outliers, impossible readings)
   - Track completeness (how many fields populated)

5. **Outlier Detection**
   - Statistical analysis (IQR, z-score)
   - Domain knowledge (physical limits for weather)
   - Flag but don't remove (preserve for analysis)

### Recommended Schema

```python
SILVER_SCHEMA = {
    # Core fields
    'timestamp': 'timestamp[ns]',
    'station_id': 'string',
    'station_name': 'string',

    # Weather parameters (standardized names)
    'temperature_celsius': 'float64',
    'humidity_percent': 'float64',
    'pressure_hpa': 'float64',
    'wind_speed_ms': 'float64',
    'wind_direction_degrees': 'float64',
    'precipitation_mm': 'float64',
    'visibility_m': 'float64',

    # Quality metadata
    'quality_score': 'float64',  # 0.0 to 1.0
    'has_outliers': 'bool',
    'outlier_fields': 'list[string]',  # Which fields are outliers
    'completeness': 'float64',  # % of fields populated

    # Partitioning
    'year': 'int32',
    'month': 'int32',
}
```

### Quality Scoring Algorithm

```python
def calculate_quality_score(record):
    """Calculate quality score for a single record"""
    score = 1.0

    # Penalize missing required fields
    required = ['timestamp', 'station_id', 'temperature_celsius']
    for field in required:
        if pd.isna(record[field]):
            score -= 0.3

    # Penalize outliers (flag but don't remove)
    if is_outlier(record['temperature_celsius'], bounds=(-50, 50)):
        score -= 0.2
        mark_outlier(record, 'temperature_celsius')

    # Penalize low completeness
    completeness = count_populated_fields(record) / total_fields
    if completeness < 0.7:
        score -= 0.1

    return max(0.0, score)
```

### Orchestration Strategy

**Same pattern as Bronze layers**:

```python
python -m data_orchestration.silver.orchestrate \
    --stations core_10 \
    --start-year 2000 \
    --end-year 2025
```

**Input**: `bronze/refined/edr_api/station_id={id}/year={year}/month={month}/*.parquet`
**Output**: `silver/edr_api/station_id={id}/year={year}/month={month}/*.parquet`

---

## 5. Recommended Next Steps

### Phase 1: Bronze Refined Hardening (Priority: HIGH)

**Goal**: Transform all Bronze Raw data → Bronze Refined Parquet

**Tasks**:
1. Review and refactor `src/transform_bronze_refined.py`
2. Ensure schema-on-read (no rigid enforcement)
3. Add monthly partitioning
4. Create orchestrator for parallel transformation
5. Add metadata tracking
6. Test with full 360 station-years

**Timeline**: 1-2 sessions
**Output**: ~1.3 GB JSON → ~200 MB Parquet (6-7x compression, queryable)

### Phase 2: Silver Layer Development (Priority: HIGH)

**Goal**: Create validated, production-ready Silver layer

**Tasks**:
1. Define fixed schema for Silver layer
2. Implement quality scoring algorithm
3. Implement outlier detection
4. Create Silver orchestrator
5. Transform all Bronze Refined → Silver
6. Test quality metrics on full dataset

**Timeline**: 2-3 sessions
**Output**: Production-ready analytical dataset with quality scores

### Phase 3: Query Optimization & Testing (Priority: MEDIUM)

**Goal**: Demonstrate medallion architecture value

**Tasks**:
1. Create comprehensive query demos (DuckDB, Polars, Pandas)
2. Benchmark query performance on full 360 station-years
3. Create example analyses:
   - Temperature trends by station
   - Multi-station comparisons
   - Data quality reports
4. Document query best practices

**Timeline**: 1 session
**Output**: Proof-of-value for medallion architecture

### Phase 4: Incremental Updates (Priority: MEDIUM)

**Goal**: Automate daily data updates

**Tasks**:
1. Create daily updater script
2. Use multi-station API batching (10 stations × 1 day)
3. Cascade through all layers (Raw → Refined → Silver)
4. Add scheduling (cron/Task Scheduler)
5. Add monitoring and alerting

**Timeline**: 1-2 sessions
**Output**: Automated daily updates for all stations

### Phase 5: Gold Layer & Analytics (Priority: LOW)

**Goal**: Create business-ready aggregated datasets

**Tasks**:
1. Define Gold layer schema (daily summaries, etc.)
2. Create aggregation pipelines
3. Build dashboards (Streamlit?)
4. Add ML-ready features

**Timeline**: 3-4 sessions
**Output**: Business intelligence layer

---

## 6. Key Design Decisions & Rationale

### ✅ Why Per-Station Parallelization?

**Decision**: Each station loads independently in its own thread

**Rationale**:
- **Simplicity**: No complex coordination between stations
- **Fault Isolation**: One station failure doesn't affect others
- **Resume Capability**: Can restart individual stations
- **Performance**: Proven optimal (70 seconds for 10 stations)

**Alternative Considered**: Multi-station API batching
**Why Rejected**: Added complexity, minimal gains for historical loads

### ✅ Why 1-Year Chunks?

**Decision**: Load data in 1-year increments (365 days per API call)

**Rationale**:
- **API Safety**: 201K data points = 54% of 376K limit (plenty of margin)
- **Simplicity**: Easy to understand and debug
- **Natural Boundaries**: Matches query patterns and reporting periods
- **Resume Granularity**: Can resume at year level

**Alternative Considered**: 2-month chunks (from v2 design)
**Why Rejected**: Unnecessary complexity, no performance benefit

### ✅ Why Two Bronze Layers?

**Decision**: Bronze Raw (JSON) + Bronze Refined (Parquet)

**Rationale**:
- **Bronze Raw**: Immutable source of truth for compliance/auditing
- **Bronze Refined**: Query-optimized without losing flexibility
- **Separation of Concerns**: Keep raw data untouched, optimize separately

**Alternative Considered**: Single Bronze layer (Parquet only)
**Why Rejected**: Loses audit trail, harder to reprocess if transformation logic changes

### ✅ Why Schema-on-Read for Bronze Refined?

**Decision**: Let Parquet infer schema, don't enforce

**Rationale**:
- **Future-Proof**: API may add new parameters → automatically preserved
- **Flexibility**: Different stations may have different sensors
- **No Breaking Changes**: Schema evolution handled gracefully

**Alternative Considered**: Fixed schema in Bronze Refined
**Why Rejected**: Too rigid, defeats purpose of having separate Silver layer

### ✅ Why ThreadPoolExecutor over Asyncio?

**Decision**: Use ThreadPoolExecutor for concurrency

**Rationale**:
- **Simplicity**: Much simpler code, easier to debug
- **Proven Performance**: Testing showed no benefit from async
- **I/O-Bound**: Network requests are I/O-bound (threading is fine)
- **No Over-Engineering**: Async would add complexity without gains

**Alternative Considered**: Asyncio with aiohttp
**Why Rejected**: Over-engineering for this use case

---

## 7. Lessons Learned

### ✅ Pragmatism Over Perfection

**Lesson**: Simple, working solution beats complex, "perfect" design

**Applied**:
- Chose ThreadPoolExecutor over async
- Used 1-year chunks (simple) over optimal 20-month calculations
- Avoided Pydantic models for simple config
- Structured logging added only when needed

**Impact**: Saved days of development time, maintained code clarity

### ✅ Metadata is Critical

**Lesson**: Good metadata enables resume, monitoring, and debugging

**Applied**:
- Per-station JSON metadata files
- Enhanced tracking (file paths, sizes, timestamps)
- Summary statistics in metadata
- Backward compatibility for migration

**Impact**: Instant resume (0.1s for 26 years), easy monitoring

### ✅ Observability Pays Off

**Lesson**: Structured logging is worth the upfront investment

**Applied**:
- Dual logging (human + JSON)
- Event types for easy filtering
- Performance metrics in every log
- UTC timestamps for analysis

**Impact**: Easy debugging, performance analysis, production monitoring

### ✅ Test with Real Data Early

**Lesson**: Don't design in a vacuum, test with real API and data

**Applied**:
- Tested single year first (Hupsel 2024)
- Then full station (Hupsel 2000-2025)
- Then all 10 stations
- Caught Windows Unicode bug early

**Impact**: Confidence in design, caught issues early

### ✅ Don't Optimize Prematurely

**Lesson**: Measure first, optimize if needed

**Applied**:
- Built simple version first (per-station)
- Measured: 70 seconds for full load (excellent!)
- Decided multi-station batching not worth complexity

**Impact**: Avoided over-optimization, shipped faster

---

## 8. Success Metrics

### Performance ✅

- **Total Coverage**: 360 station-years (1990-2025, 10 stations)
- **Latest Load**: 69.8 seconds for 259 years (2000-2025 batch)
- **Average**: 0.27 seconds per year
- **Success Rate**: 100% (no failures)
- **Resume Speed**: 0.1 seconds (instant)

### Reliability ✅

- **Atomic Writes**: No partial files on failure
- **Retry Logic**: Automatic recovery from transient errors
- **Resume Capability**: Skip already-loaded data
- **Error Handling**: Graceful degradation, detailed error messages

### Observability ✅

- **Structured Logging**: JSON + human-readable
- **Metadata Tracking**: Complete audit trail
- **Performance Metrics**: Tracked for every operation
- **Production-Ready**: Can monitor and debug in production

### Maintainability ✅

- **Simple Architecture**: Easy to understand and modify
- **Modular Design**: Clear separation of concerns
- **Well-Documented**: Comprehensive README and inline comments
- **Configuration-Driven**: Easy to add stations or change settings

---

## 9. Conclusion

The **Bronze Raw v3 ingestion system is production-ready** and serves as a solid foundation for the medallion architecture. We achieved:

1. ✅ **Complete Coverage**: 360 station-years (1990-2025, 10 core stations)
2. ✅ **Exceptional Performance**: 0.27s per year average, 100% success rate
3. ✅ **100% Reliability**: No failures, complete error recovery
4. ✅ **Professional Observability**: Structured logging and metadata
5. ✅ **Simple & Maintainable**: Avoided over-engineering
6. ✅ **Scalable Design**: Can easily expand to all 77 KNMI stations

**Next priorities**:
1. **Bronze Refined**: Transform JSON → Parquet with schema-on-read
2. **Silver Layer**: Add validation, cleaning, and quality scoring
3. **Incremental Updates**: Build daily updater with multi-station batching

The architecture is **battle-tested**, **well-documented**, and ready for the next phases of development.

---

**Generated**: 2025-11-18
**Author**: Claude Code + User
**Status**: ✅ PRODUCTION-READY
