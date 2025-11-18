# EDR API Optimization Opportunities

**Date:** 2025-11-17
**Analysis By:** Claude Code
**Status:** 🔍 Research & Recommendations

---

## Executive Summary

After deep analysis of the KNMI EDR API OpenAPI specification, I've identified **5 major optimization opportunities** that could significantly improve loading performance:

1. **Multi-station queries** - Load multiple stations in a single API call (MAJOR - 80%+ reduction in API calls)
2. **Optimized chunking strategy** - Calculate optimal chunk sizes based on API limits
3. **Parameter filtering** - Only download needed weather parameters
4. **Response format optimization** - Test netCDF4 vs CoverageJSON for bulk downloads
5. **Better error handling & resume** - More granular retry logic

**Estimated Impact:** 3-5x faster bulk loading, 80% fewer API calls, better rate limit utilization

---

## Current Implementation Analysis

### How We Currently Load Data

**Per Station Loading:**
```
For each station:
  └─ For each monthly chunk:
      └─ API Call: /locations/{single_station_id}?datetime=...
```

**Example:** Loading 10 stations for 25 years:
- Stations: 10
- Years: 25
- Chunks per year: 12 (monthly)
- **Total API calls: 10 × 25 × 12 = 3,000 API calls**

**Current Performance:**
- 1 year (1 station): ~12 seconds
- 25 years (2 stations): ~8 minutes (parallel)
- 25 years (10 stations): ~45-60 minutes (estimated)

### Rate Limits
- **Per Second:** 200 requests/sec (registered users)
- **Per Hour:** 1000 requests/hour (registered users)
- **Data Point Limit:** ~376,000 data points per request
  - Calculation: hours × parameters × stations

---

## Optimization #1: Multi-Station Queries (MAJOR)

### Current API Capability

The EDR API **supports comma-separated station IDs** in a single request:

**From OpenAPI Spec:**
```
GET /collections/{collection}/locations/{location_id}

Path Parameter:
  location_id: Comma-separated station identifiers
  Example: "0-20000-0-06240,0-20000-0-06260,0-20000-0-06275"
```

### Proposed Implementation

**Load multiple stations per API call:**
```
For each time chunk:
  └─ For each station batch (e.g., 3-5 stations):
      └─ API Call: /locations/station1,station2,station3?datetime=...
```

### Impact Analysis

**Example:** Loading 10 stations for 25 years with 5-station batches:
- Station batches: 10 ÷ 5 = 2 batches
- Years: 25
- Chunks per year: 12 (monthly)
- **Total API calls: 2 × 25 × 12 = 600 API calls**

**Savings: 80% reduction (3,000 → 600 API calls)**

### Implementation Strategy

**Option A: Small Batches (3-5 stations)**
- **Pros:**
  - Safer (less risk of hitting data point limit)
  - Better parallelization
  - Easier error recovery
- **Cons:**
  - More API calls than larger batches
- **Recommended batch size:** 5 stations

**Option B: Large Batches (8-10 stations)**
- **Pros:**
  - Fewer API calls
  - Maximum reduction in HTTP overhead
- **Cons:**
  - Risk of exceeding data point limit
  - Harder to parallelize
  - Error recovery affects more stations
- **Risk:** May hit 376K data point limit

**Data Point Calculation:**
```python
# For hourly data with all parameters
hours_per_month = 30 * 24 = 720 hours
parameters = 23 (all available parameters)
stations = 5 (batch size)

data_points = 720 × 23 × 5 = 82,800 points/month
data_points_yearly = 82,800 × 12 = 993,600 points/year  # EXCEEDS LIMIT!

# Safe batch size for yearly chunks:
max_stations = 376,000 / (8,760 hours × 23 params) ≈ 1.87 stations/year
```

**Recommendation:**
- **Monthly chunks with 5-station batches** = 82,800 points (safe)
- **Quarterly chunks with 3-station batches** = ~160,000 points (safe)
- **Yearly chunks with 1 station** = 201,480 points (current approach, safe)

### Proposed Code Changes

**New Function in `ingest_bronze_raw.py`:**
```python
def query_edr_api_multi_station(self, station_ids: List[str], start_date: str,
                                 end_date: str, parameters=None):
    """
    Query EDR API for multiple stations in a single call

    Args:
        station_ids: List of station IDs (e.g., ["0-20000-0-06283", "0-20000-0-06275"])
        start_date: ISO format datetime string
        end_date: ISO format datetime string
        parameters: List of parameter names (None = all parameters)

    Returns:
        JSON response containing data for all stations
    """
    # Join station IDs with commas
    location_param = ",".join(station_ids)
    datetime_range = f"{start_date}/{end_date}"

    params = {"datetime": datetime_range}
    if parameters:
        params["parameter-name"] = ",".join(parameters)

    url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{location_param}"

    response = requests.get(url, params=params, headers=self.headers, timeout=120)
    response.raise_for_status()

    return response.json()
```

**Modified Orchestrator:**
```python
def load_station_batch_chunk(self, station_keys: List[str], start_date: str,
                              end_date: str) -> Dict:
    """
    Load a chunk of data for multiple stations at once

    Args:
        station_keys: List of station identifiers (e.g., ["hupsel", "deelen"])
        start_date: Start date in ISO format
        end_date: End date in ISO format

    Returns:
        Result dictionary with status for each station
    """
    # Get station IDs
    station_ids = [STATIONS[key]["id"] for key in station_keys]

    # Single API call for all stations
    data = query_edr_api_multi_station(station_ids, start_date, end_date)

    # Split response by station and save individually
    # (Response format needs to be analyzed to see how multi-station data is returned)
    for station_key in station_keys:
        # Extract data for this station from combined response
        station_data = extract_station_data(data, station_key)

        # Save to bronze raw
        save_bronze_raw(station_data, station_key, start_date, end_date)
```

### Testing Needed

1. **Response Format Analysis:**
   - Test multi-station query to understand response structure
   - Determine how to split combined response by station

2. **Data Point Limit Testing:**
   - Test with increasing batch sizes to find safe limits
   - Measure actual data points returned vs theoretical limit

3. **Performance Benchmarking:**
   - Compare single-station vs multi-station loading times
   - Measure reduction in total loading time

### Rollout Strategy

1. **Phase 1:** Test with 2 stations (hupsel + deelen) for 1 month
2. **Phase 2:** Test with 5 stations for 1 year
3. **Phase 3:** Test edge cases (all 10 stations, multi-year)
4. **Phase 4:** Update orchestrator to use multi-station by default

---

## Optimization #2: Optimized Chunking Strategy

### Current Approach

**Fixed monthly chunking** regardless of:
- Number of stations
- Number of parameters
- API data point limit

### Proposed Approach

**Dynamic chunking** based on batch size:

```python
def calculate_optimal_chunk_size(num_stations: int, num_parameters: int = 23,
                                  max_data_points: int = 376000) -> int:
    """
    Calculate optimal chunk size to maximize data per request while staying
    under API limit

    Args:
        num_stations: Number of stations in batch
        num_parameters: Number of parameters (default: 23)
        max_data_points: API limit (default: 376,000)

    Returns:
        Optimal chunk size in days
    """
    # Leave 20% safety margin
    safe_limit = max_data_points * 0.8

    # Calculate hours per station-parameter
    hours_available = safe_limit / (num_stations * num_parameters)

    # Convert to days
    days = int(hours_available / 24)

    return days

# Examples:
# 1 station:  300,800 / 23 = 13,078 hours = 545 days (~18 months)
# 3 stations: 300,800 / (3 × 23) = 4,359 hours = 181 days (~6 months)
# 5 stations: 300,800 / (5 × 23) = 2,616 hours = 109 days (~3.5 months)
# 10 stations: 300,800 / (10 × 23) = 1,308 hours = 54 days (~2 months)
```

### Impact

**Current:** Fixed monthly chunks (30 days) regardless of batch size
**Optimized:** Dynamic chunks (30-180 days) based on batch size

**Reduction in API calls:**
- 5 stations, quarterly chunks: 600 → 200 API calls (67% reduction)
- 10 stations, bi-monthly chunks: 600 → 300 API calls (50% reduction)

**Combined with multi-station batching:**
- **Total reduction: 90%+ (3,000 → 200-300 API calls)**

---

## Optimization #3: Parameter Filtering

### Current Behavior

**Downloads all 23+ parameters** even if only a subset is needed:
- Temperature (T, T10N, TD, etc.)
- Humidity (U)
- Rainfall (RH, DR)
- Wind (DD, FF, FX, FH)
- Solar (Q, SQ)
- Pressure (P)
- Visibility (VV)
- Cloud cover (N)
- Weather codes (WW)
- ...and more

### API Capability

**From OpenAPI spec:**
```
Query Parameter:
  parameter-name: Comma-delimited parameter list
  Example: "T,RH,FF"  (only temperature, rainfall, wind speed)
```

**Alternative - Standard Names:**
```
Query Parameter:
  standard_name: CF-compliant parameter names
  Example: "air_temperature,wind_speed"
```

### Use Cases

**Scenario 1: Temperature Analysis Only**
```python
parameters = ["T", "T10N", "TX", "TN", "TD"]
# Reduces from 23 params → 5 params
# 78% reduction in data points
# Smaller files, faster downloads
```

**Scenario 2: Core Weather Only**
```python
parameters = ["T", "RH", "FF", "DD", "P", "U"]
# Reduces from 23 params → 6 params
# 74% reduction in data points
```

**Scenario 3: Full Dataset (Current)**
```python
parameters = None  # All parameters
# Keep for archival/compliance purposes
```

### Implementation

**Add parameter profiles to config.py:**
```python
PARAMETER_PROFILES = {
    "full": None,  # All parameters (current default)
    "core": ["T", "RH", "FF", "DD", "P", "U"],  # Core weather
    "temperature": ["T", "T10N", "TX", "TN", "TD"],  # Temp analysis
    "precipitation": ["RH", "DR", "EE"],  # Rainfall analysis
    "wind": ["FF", "FH", "FX", "DD"],  # Wind analysis
}
```

**Update ingestion to support profiles:**
```bash
# Full dataset (default)
python src/ingest_bronze_raw.py --station hupsel --year 2024

# Core parameters only
python src/ingest_bronze_raw.py --station hupsel --year 2024 --profile core

# Custom parameters
python src/ingest_bronze_raw.py --station hupsel --year 2024 --parameters T RH FF
```

### Impact

- **Storage savings:** 70-80% for filtered profiles
- **Download speed:** 3-5x faster for core parameters
- **Processing speed:** Faster transforms (less data to process)
- **Cost:** Reduced bandwidth usage

**Trade-off:** Flexibility vs efficiency
- Bronze Raw should remain "full" for archival
- Silver/Gold can use filtered versions for analytics

---

## Optimization #4: Response Format Testing

### Available Formats

**From OpenAPI spec:**
```
Query Parameter:
  f: Output format
  Options:
    - application/prs.coverage+json (CoverageJSON - default)
    - application/netcdf (netCDF4)
```

### Current: CoverageJSON (Default)

**Pros:**
- JSON format (easy to parse)
- Human-readable
- Direct Python dict conversion

**Cons:**
- Larger file size (verbose JSON)
- Slower parsing for large datasets

### Alternative: netCDF4

**Pros:**
- Binary format (more compact)
- Industry standard for scientific data
- Built-in compression
- Efficient for large arrays

**Cons:**
- Requires netCDF library (xarray, netCDF4-python)
- Less human-readable
- More complex parsing

### Testing Needed

**Benchmark comparison:**
```python
# Test 1: Download 1 year of data (1 station)
# - Format: CoverageJSON
# - Measure: Download time, file size, parse time

# Test 2: Same data
# - Format: netCDF4
# - Measure: Download time, file size, parse time

# Compare:
# - Total time (download + parse)
# - Storage efficiency
# - Memory usage
```

**Hypothesis:** netCDF4 may be 2-3x more efficient for bulk downloads

### Implementation

**Add format option to config:**
```python
# config.py
EDR_RESPONSE_FORMAT = "application/prs.coverage+json"  # or "application/netcdf"
```

**Update query function:**
```python
def query_edr_api(self, start_date, end_date, parameters=None, format=None):
    """Query EDR API with format option"""
    params = {"datetime": f"{start_date}/{end_date}"}

    if format:
        params["f"] = format

    # ... rest of implementation
```

---

## Optimization #5: Better Error Handling & Resume

### Current Behavior

**Orchestrator resume logic:**
- Tracks station-level completion
- All-or-nothing per station
- Some manual gap filling needed (as documented in PROJECT_STATUS.md)

### Proposed Improvements

**1. Chunk-Level Resume:**
```python
# Instead of:
station_complete: True/False

# Track:
chunks_completed: {
    "2024-01": {"status": "complete", "records": 744},
    "2024-02": {"status": "complete", "records": 696},
    "2024-03": {"status": "failed", "error": "timeout"},
    "2024-04": {"status": "pending"}
}
```

**2. Automatic Retry Logic:**
```python
def load_chunk_with_retry(self, station_key, start_date, end_date,
                          max_retries=3, backoff=2):
    """Load chunk with exponential backoff retry"""
    for attempt in range(max_retries):
        try:
            return self.load_station_chunk(station_key, start_date, end_date)
        except requests.exceptions.Timeout:
            if attempt < max_retries - 1:
                sleep_time = backoff ** attempt
                logger.warning(f"Timeout, retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                raise
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                logger.warning("Rate limit hit, backing off...")
                time.sleep(60)  # Wait 1 minute
            else:
                raise
```

**3. Gap Detection & Auto-Fill:**
```python
def detect_gaps(self, station_key: str) -> List[Tuple[str, str]]:
    """Detect missing date ranges for a station"""
    expected_range = (datetime(2000, 1, 1), datetime(2025, 12, 31))
    loaded_chunks = self.mm.get_loaded_chunks(station_key)

    gaps = []
    # Calculate gaps between loaded chunks
    # Return list of (start_date, end_date) tuples for missing data

    return gaps

def fill_gaps(self, station_key: str):
    """Automatically fill detected gaps"""
    gaps = self.detect_gaps(station_key)
    for start, end in gaps:
        logger.info(f"Filling gap: {start} to {end}")
        self.load_station_chunk(station_key, start, end)
```

### Impact

- **Reliability:** Automatic recovery from transient failures
- **Efficiency:** Don't re-download successfully loaded chunks
- **Completeness:** Automatic gap detection and filling
- **Maintenance:** Less manual intervention needed

---

## Implementation Priority & Roadmap

### Priority 1: HIGH IMPACT (Implement First)

**1. Multi-Station Queries** (Optimization #1)
- **Impact:** 80% reduction in API calls
- **Effort:** Medium (2-3 hours)
- **Risk:** Low-Medium (need to test response format)
- **Action:**
  1. Test multi-station query with 2 stations
  2. Analyze response structure
  3. Implement batch loading
  4. Update orchestrator

### Priority 2: MEDIUM IMPACT (Quick Wins)

**2. Better Error Handling** (Optimization #5)
- **Impact:** Improved reliability
- **Effort:** Low (1-2 hours)
- **Risk:** Low
- **Action:** Add retry logic and chunk-level tracking

**3. Optimized Chunking** (Optimization #2)
- **Impact:** 50%+ additional reduction in API calls when combined with #1
- **Effort:** Low (1 hour)
- **Risk:** Low
- **Action:** Implement dynamic chunk size calculator

### Priority 3: LOW IMPACT (Nice to Have)

**4. Parameter Filtering** (Optimization #3)
- **Impact:** Storage/speed improvements for specific use cases
- **Effort:** Low (1 hour)
- **Risk:** Low
- **Action:** Add parameter profiles to config

**5. Response Format Testing** (Optimization #4)
- **Impact:** Potential 2-3x efficiency gain (needs testing)
- **Effort:** Medium (2-3 hours for testing + implementation)
- **Risk:** Medium (may not provide significant benefit)
- **Action:** Benchmark CoverageJSON vs netCDF4

---

## Estimated Total Impact

### Current Performance (10 stations, 25 years):
- **API Calls:** 3,000
- **Time:** ~45-60 minutes
- **Rate Limit Usage:** 3,000 requests (3 hours of quota)

### Optimized Performance (with all improvements):
- **API Calls:** ~200-300 (90% reduction)
- **Time:** ~10-15 minutes (70% reduction)
- **Rate Limit Usage:** 200-300 requests (20 minutes of quota)
- **Reliability:** Near 100% with automatic retry

### Storage Efficiency (if using parameter filtering):
- **Full dataset:** ~300 MB (current)
- **Core parameters:** ~70-80 MB (74% reduction)
- **Temperature only:** ~65 MB (78% reduction)

---

## Testing Plan

### Phase 1: Multi-Station Query Testing (Priority 1)

**Test 1.1: Basic Multi-Station Query**
```bash
# Test with 2 stations, 1 month
curl -H "Authorization: ${KNMI_EDR_API_KEY}" \
  "https://api.dataplatform.knmi.nl/edr/v1/collections/hourly-in-situ-meteorological-observations-validated/locations/0-20000-0-06283,0-20000-0-06275?datetime=2024-01-01T00:00:00Z/2024-01-31T23:59:59Z"

# Analyze:
# - Response structure
# - How data is organized by station
# - File size vs single-station queries
```

**Test 1.2: Batch Size Limits**
```python
# Test increasing batch sizes to find data point limit
test_batch_sizes = [2, 3, 5, 8, 10]
test_period = "1 month"

for batch_size in test_batch_sizes:
    try:
        response = query_multi_station(stations[:batch_size], period)
        print(f"✓ Batch size {batch_size}: Success")
    except Exception as e:
        print(f"✗ Batch size {batch_size}: Failed - {e}")
```

**Test 1.3: Performance Benchmarking**
```python
# Compare single vs multi-station loading
import time

# Single station approach (current)
start = time.time()
for station in stations:
    query_edr_api(station, date_range)
single_time = time.time() - start

# Multi-station approach (optimized)
start = time.time()
query_edr_api_multi_station(stations, date_range)
multi_time = time.time() - start

improvement = (single_time - multi_time) / single_time * 100
print(f"Improvement: {improvement:.1f}%")
```

### Phase 2: Integration Testing

**Test 2.1: End-to-End Pipeline**
```bash
# Load 5 stations for 1 year using optimized pipeline
python src/orchestrate_historical.py \
  --stations "hupsel,deelen,de_bilt,schiphol,rotterdam" \
  --start-year 2024 \
  --end-year 2024 \
  --use-multi-station \
  --batch-size 5

# Verify:
# - All data loaded correctly
# - No duplicates
# - Performance improvement vs current approach
```

**Test 2.2: Error Recovery**
```python
# Simulate failures and test retry logic
# - Network timeout
# - Rate limit exceeded (429)
# - Server error (500)

# Verify automatic recovery
```

### Phase 3: Production Rollout

**Step 1:** Load new station (test case)
**Step 2:** Re-load 1 year for existing station (validation)
**Step 3:** Load remaining 8 stations with optimized pipeline
**Step 4:** Monitor and measure improvements

---

## Recommendations

### Immediate Actions (This Week)

1. **Test multi-station queries** with 2-3 stations for 1 month
2. **Analyze response format** to understand data structure
3. **Implement basic multi-station support** in `ingest_bronze_raw.py`
4. **Add retry logic** to orchestrator

### Short Term (Next 2 Weeks)

5. **Implement dynamic chunking** based on batch size
6. **Update orchestrator** to use multi-station batching
7. **Add parameter filtering** support (optional feature)
8. **Comprehensive testing** of optimized pipeline

### Long Term (Next Month)

9. **Benchmark response formats** (CoverageJSON vs netCDF4)
10. **Implement automated gap detection** and filling
11. **Load all 10 core stations** using optimized pipeline
12. **Document optimizations** and update CLAUDE.md

---

## Questions for User

1. **Should we preserve the current single-station approach** as a fallback, or fully migrate to multi-station?

2. **Parameter filtering:** Should Bronze Raw remain "full" (all parameters) for archival purposes?

3. **Response format:** Is it worth testing netCDF4, or stick with CoverageJSON?

4. **Testing approach:** Should we test on a new station, or re-load existing data to validate?

5. **Rollout timeline:** Aggressive (implement all optimizations now) vs conservative (test thoroughly first)?

---

## References

- **KNMI EDR API OpenAPI Spec:** https://api.dataplatform.knmi.nl/edr/v1/openapi.json
- **EDR Standard:** OGC Environmental Data Retrieval API
- **Developer Docs:** https://developer.dataplatform.knmi.nl/edr-api
- **Rate Limits:** 200 req/sec, 1000 req/hour (registered)
- **Data Point Limit:** ~376,000 points per request

---

**Next Steps:** Review this analysis and prioritize optimizations based on project goals.
