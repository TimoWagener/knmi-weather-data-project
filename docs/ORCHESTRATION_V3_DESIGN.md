# Orchestration v3 Design: Separated Phases with Massive Parallelization

**Date:** 2025-11-17
**Status:** 🔄 Design Phase
**Goal:** Refactor orchestration to follow medallion architecture best practices with maximum performance

---

## 🎯 Problem with Current v2 Orchestration

**Current Approach (v2 - Bad Practice):**
```
For each chunk (156 chunks):
  ├─ Step 1: API call → Bronze Raw (8 stations)
  ├─ Step 2: Transform → Bronze Refined (8 stations)
  └─ Step 3: Transform → Silver (8 stations)

Total time: ~3 hours (sequential, tightly coupled)
```

**Problems:**
- ❌ **Violates separation of concerns** - Layers are tightly coupled
- ❌ **Not idempotent** - Can't rerun phases independently
- ❌ **Poor failure handling** - One transform failure affects everything
- ❌ **Can't reprocess** - Must re-download to fix transform bugs
- ❌ **Underutilizes API** - Sequential calls waste API capacity (200 req/sec available!)
- ❌ **Violates medallion best practices** - Microsoft/Databricks recommend layer separation

---

## ✅ v3 Architecture: Separated Phases

### Three Independent Phases

```
Phase 1: INGEST ALL BRONZE RAW
├─ Massive parallel API calls (100-200 concurrent!)
├─ ALL 156 chunks downloaded in parallel
└─ Estimated time: 5-10 minutes (vs 3 hours!)

Phase 2: TRANSFORM ALL BRONZE REFINED
├─ Process all JSON files → Parquet
├─ Batch or parallel processing
└─ Estimated time: 5-10 minutes

Phase 3: TRANSFORM ALL SILVER
├─ Process all Parquet → Validated Silver
├─ Full history processing (no SCD needed - historical data immutable)
└─ Estimated time: 5-10 minutes

TOTAL: 15-30 minutes (vs 180 minutes v2!)
```

---

## 📊 Phase 1: Massive Parallel Bronze Raw Ingestion

### Current State (v2)
- **Sequential processing**: One chunk at a time
- **Time per chunk**: ~2 minutes (including transforms)
- **API calls**: 156 total, processed sequentially
- **Total time**: ~180 minutes

### Proposed State (v3)
- **Massive parallelization**: 100-200 concurrent API calls
- **Time per call**: ~10 seconds (API response time)
- **Concurrency limit**: 200 req/sec API limit = we can run 100+ in parallel
- **Total time**: ~5-10 minutes for ALL data!

### Optimization Calculation

**API Capacity:**
- Limit: 200 requests/second
- Average call duration: ~10 seconds
- Safe concurrent calls: 100-150 (stay under limit with safety margin)

**Performance Improvement:**
```
Current v2 (sequential):
  156 chunks × 2 minutes = 312 minutes (~5 hours with transforms)

Proposed v3 (parallel ingestion only):
  156 chunks / 100 parallel = 1.56 batches
  1.56 batches × 10 seconds = ~16 seconds
  Add overhead (startup, queuing): ~5-10 minutes total

Speedup: 30x-60x faster for ingestion!
```

### Implementation Strategy

**Option A: ThreadPoolExecutor (Simple)**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=100) as executor:
    futures = []
    for chunk in all_chunks:
        future = executor.submit(ingest_bronze_raw, chunk)
        futures.append(future)

    for future in as_completed(futures):
        result = future.result()
```

**Option B: asyncio (More control)**
```python
import asyncio
import aiohttp

async def ingest_chunk(session, chunk):
    async with session.get(url, headers=headers) as response:
        data = await response.json()
        save_bronze_raw(data, chunk)

async def ingest_all():
    async with aiohttp.ClientSession() as session:
        tasks = [ingest_chunk(session, chunk) for chunk in all_chunks]
        await asyncio.gather(*tasks, return_exceptions=True)
```

**Recommendation: Start with ThreadPoolExecutor (simpler), move to asyncio if needed**

### Safety Considerations

**Rate Limiting:**
- API limit: 200 req/sec, 1000 req/hour
- Our 156 chunks in 10 minutes = 0.26 req/sec (well under limit!)
- Safe to run 100+ concurrent without throttling

**Error Handling:**
- Track success/failure per chunk
- Retry failed chunks (max 3 attempts)
- Continue on partial failures
- Log all results to metadata

**Memory Management:**
- Each response: ~1-5 MB
- 100 concurrent: ~100-500 MB in memory (acceptable)
- Save to disk immediately after receipt

---

## 📊 Phase 2: Batch Bronze Refined Transformation

### Current State (v2)
- **Sequential per-station processing**
- **Transforms during ingestion** (bad practice!)
- **Time**: Mixed with ingestion (~2 min per chunk)

### Proposed State (v3)
- **Batch processing**: Process all files at once
- **After ingestion complete**: Clean separation
- **Parallelization**: Process multiple stations concurrently

### Implementation Strategy

**Discover all Bronze Raw files:**
```python
bronze_raw_files = glob.glob("data/bronze/raw/edr_api/station_id=*/year=*/*.json")
print(f"Found {len(bronze_raw_files)} files to process")
```

**Option A: Process all files in parallel**
```python
from concurrent.futures import ProcessPoolExecutor

def transform_file(json_path):
    """Transform single JSON file to Parquet"""
    data = load_json(json_path)
    df = flatten_coverage_to_dataframe(data)
    output_path = get_refined_path(json_path)
    df.to_parquet(output_path)
    return output_path

with ProcessPoolExecutor(max_workers=8) as executor:
    results = executor.map(transform_file, bronze_raw_files)
```

**Option B: Process by station (simpler)**
```python
stations = get_all_stations_with_data()

for station in stations:
    print(f"Processing {station}...")
    # Process all years for this station
    transform_bronze_refined(station)
```

**Recommendation: Process all files in parallel (faster, better utilization)**

### Optimization Opportunities

1. **Polars instead of Pandas**: Faster JSON → DataFrame
2. **PyArrow native**: Direct JSON → Parquet conversion
3. **Memory mapping**: Process large files without full load
4. **Incremental processing**: Track already-processed files (skip on rerun)

---

## 📊 Phase 3: Silver Layer Transformation

### Current State (v2)
- **Sequential per-station processing**
- **Transforms during ingestion** (bad practice!)
- **Time**: Mixed with ingestion

### Proposed State (v3)
- **Full history processing**: Process all data at once
- **No SCD needed**: Historical data is immutable
- **Quality scoring**: Score all records in batch

### Implementation Strategy

**Process all Bronze Refined files:**
```python
refined_files = glob.glob("data/bronze/refined/edr_api/station_id=*/year=*/*.parquet")

def transform_to_silver(parquet_path):
    """Transform Bronze Refined → Silver with validation"""
    df = pl.read_parquet(parquet_path)

    # Validate schema
    df_validated = enforce_schema(df)

    # Quality scoring
    df_validated = score_quality(df_validated)

    # Outlier detection
    df_validated = detect_outliers(df_validated)

    # Save to Silver
    output_path = get_silver_path(parquet_path)
    df_validated.write_parquet(output_path)

    return output_path

# Parallel processing
with ProcessPoolExecutor(max_workers=8) as executor:
    results = executor.map(transform_to_silver, refined_files)
```

### Why No SCD (Slowly Changing Dimensions)?

**Typical use case for SCD:**
- Source data can change retroactively
- Need to track history of changes
- Example: Customer address changes

**Our case (no SCD needed):**
- Historical weather data is **immutable**
- KNMI validates and publishes final data
- Once published, it doesn't change
- No need to track "versions" of past weather

**Simplification:**
- Process all data as-is
- No need for temporal tracking
- No need for version columns
- Simpler, faster, clearer

---

## 🏗️ Implementation Plan

### Step 1: Create Phase-Based Scripts

**New scripts to create:**
```
src/
├── orchestrate_phase1_ingest.py       # Parallel Bronze Raw ingestion
├── orchestrate_phase2_refined.py      # Batch Bronze Refined transform
├── orchestrate_phase3_silver.py       # Batch Silver transform
└── orchestrate_full_pipeline.py       # Run all 3 phases in sequence
```

### Step 2: Refactor ingest_bronze_raw.py

**Changes needed:**
- Remove monthly chunking (orchestrator handles this)
- Accept single date range (one chunk)
- Return success/failure status
- Support async/concurrent calls

**New function signature:**
```python
def ingest_chunk(
    station_ids: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    Ingest single chunk for multiple stations
    Returns: {'success': bool, 'files': List[Path], 'error': Optional[str]}
    """
```

### Step 3: Create Parallel Orchestrator

**Key features:**
- ThreadPoolExecutor with configurable workers (default: 100)
- Progress tracking (tqdm or logging)
- Error handling and retry logic
- Metadata tracking (which chunks completed)
- Resume capability (skip already-downloaded chunks)

### Step 4: Create Batch Transform Scripts

**Bronze Refined transformer:**
- Find all Bronze Raw JSON files
- Process in parallel (ProcessPoolExecutor)
- Track progress and errors
- Idempotent (skip already-processed files)

**Silver transformer:**
- Find all Bronze Refined Parquet files
- Process in parallel
- Full quality pipeline
- Idempotent

### Step 5: Testing Strategy

**Test each phase independently:**
1. **Phase 1**: Ingest small date range (1 month, 2 stations)
2. **Phase 2**: Transform those specific files
3. **Phase 3**: Process to Silver
4. **Verify**: Query and validate results

**Then scale up:**
- Test with 10 concurrent workers
- Test with 50 concurrent workers
- Test with 100 concurrent workers
- Monitor API responses and adjust

---

## 📈 Expected Performance Improvements

### Time Comparison

| Metric | v2 (Current) | v3 (Proposed) | Improvement |
|--------|--------------|---------------|-------------|
| **Phase 1: Ingestion** | 180 min (sequential) | 5-10 min (parallel) | **18-36x faster** |
| **Phase 2: Bronze Refined** | Mixed in | 5-10 min (batch) | ✅ Separated |
| **Phase 3: Silver** | Mixed in | 5-10 min (batch) | ✅ Separated |
| **Total Time (8 stations, 25 years)** | 180 min | 15-30 min | **6-12x faster** |
| **Reprocessing (fix transform bug)** | Must re-download | Phases 2+3 only (~10-20 min) | **Instant fix** |

### Scalability Comparison

| Stations | Years | v2 Time | v3 Time | v3 Advantage |
|----------|-------|---------|---------|--------------|
| 8 | 25 | 180 min | 15-30 min | 6-12x faster |
| 10 | 25 | 225 min | 15-30 min | 7-15x faster |
| 30 | 25 | 675 min | 20-40 min | 17-34x faster |
| 70 | 25 | 1,575 min | 30-60 min | **26-52x faster** |

**Key insight:** v3 scales almost linearly with parallelization, while v2 scales linearly with data volume!

---

## 🎯 Benefits of v3 Architecture

### 1. **Separation of Concerns** ✅
- Each phase is independent
- Can test/debug/optimize separately
- Clear boundaries and responsibilities

### 2. **Idempotency** ✅
- Rerun any phase without affecting others
- Fix bugs without re-downloading
- Safe to retry failures

### 3. **Performance** ✅
- 6-12x faster for initial load
- 18-36x faster for ingestion phase
- Scales to 70+ stations easily

### 4. **Failure Handling** ✅
- Phase 1 failure: Retry specific chunks
- Phase 2 failure: Bronze Raw preserved
- Phase 3 failure: Bronze Refined preserved

### 5. **Best Practices** ✅
- Follows Microsoft/Databricks recommendations
- Medallion architecture done right
- Industry-standard orchestration pattern

### 6. **Development Velocity** ✅
- Iterate on transforms quickly (no re-download)
- Test new transform logic easily
- Add new stations incrementally

### 7. **Cost Efficiency** ✅
- Minimize API calls (same as v2)
- Maximize throughput (parallel processing)
- Reduce compute time (faster = cheaper)

---

## 🚀 Migration Strategy

### For Current Load (v2 - In Progress)
- ✅ **Let it finish** (84% complete, ~30 minutes remaining)
- ✅ **Data is valid** (Bronze Raw + Refined + Silver all complete)
- ✅ **No action needed** for these 8 stations

### Going Forward (v3)
1. **Build v3 orchestrator** (new scripts)
2. **Test with 2-3 new stations** (small scale validation)
3. **Scale to next 20-30 stations** (prove performance gains)
4. **Archive v2** (same as we did with v1)
5. **Document v3 as new standard**

### Backward Compatibility
- ✅ **Data format unchanged** (same Bronze/Silver structure)
- ✅ **Transform scripts work as-is** (just called differently)
- ✅ **Query layer unaffected** (DuckDB/Polars queries work identically)

---

## 📋 Next Steps

### Immediate (While v2 Load Completes)
1. ✅ Create this design document
2. ⏳ Review and validate approach
3. ⏳ Get user approval to proceed

### Phase 1: Build v3 Orchestrator
1. Create `orchestrate_phase1_ingest.py` with parallel ingestion
2. Refactor `ingest_bronze_raw.py` for single-chunk operation
3. Test with 10, 50, 100 concurrent workers
4. Measure actual performance gains

### Phase 2: Build Batch Transforms
1. Create `orchestrate_phase2_refined.py` for batch processing
2. Create `orchestrate_phase3_silver.py` for batch processing
3. Create `orchestrate_full_pipeline.py` to run all 3 phases
4. Test end-to-end on small dataset

### Phase 3: Production Deployment
1. Test on 2-3 new stations (full 25 years)
2. Measure time savings vs v2
3. Scale to 20-30 stations
4. Document and update all guides

---

## 🔬 Technical Considerations

### API Rate Limiting
- **Limit**: 200 req/sec, 1000 req/hour
- **Our usage**: 156 chunks / 600 seconds = 0.26 req/sec
- **Conclusion**: Massive headroom for parallelization

### Memory Management
- **Per chunk**: 1-5 MB response
- **100 concurrent**: 100-500 MB peak
- **System**: 16+ GB recommended (typical dev machine)
- **Mitigation**: Save to disk immediately after receipt

### Network Considerations
- **Bandwidth**: 156 chunks × 2 MB = ~312 MB total
- **Download time**: ~1-2 minutes on typical connection
- **Not a bottleneck**: API response time dominates

### Error Handling Strategy
```python
# Retry logic for failed chunks
max_retries = 3
failed_chunks = []

for attempt in range(max_retries):
    if not failed_chunks and attempt == 0:
        # First attempt - all chunks
        chunks_to_process = all_chunks
    else:
        # Retry only failed chunks
        chunks_to_process = failed_chunks

    results = parallel_process(chunks_to_process)
    failed_chunks = [c for c in chunks_to_process if not results[c].success]

    if not failed_chunks:
        break

    print(f"Retry {attempt+1}: {len(failed_chunks)} chunks failed")
```

---

## 📚 References

### Best Practice Sources
- [Microsoft: Medallion Architecture](https://learn.microsoft.com/en-us/azure/databricks/lakehouse/medallion)
- [Databricks: Medallion Architecture](https://www.databricks.com/glossary/medallion-architecture)
- [Medium: Medallion Best Practices](https://piethein.medium.com/medallion-architecture-best-practices-for-managing-bronze-silver-and-gold-486de7c90055)

### Key Quotes
> "By separating data into clearly defined layers, Medallion Architecture allows teams to manage ingestion, transformation, and analytics independently."

> "Azure Databricks does not recommend writing to silver tables directly from ingestion."

---

**Status:** Ready for review and implementation
**Owner:** To be implemented
**Target:** v3 orchestration for next station batch (20-30 stations)
