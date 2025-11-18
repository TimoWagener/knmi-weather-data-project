# Bronze Raw Ingestion

**Phase 1 of the Medallion Architecture Pipeline**

Parallel ingestion of KNMI weather data from the EDR API using independent per-station pipelines.

## Overview

This module implements a clean, pragmatic approach to loading historical weather data:

- **Per-station independence**: Each station loads in its own thread
- **1-year chunks**: Simple, intuitive partitioning (365 days × 24 hours × 23 params = 201,480 data points per chunk)
- **Parallel execution**: 10 stations load simultaneously (proven optimal from API testing)
- **Robust error handling**: Automatic retries with exponential backoff, honors rate limits
- **Atomic writes**: Data integrity guaranteed (no partial files)
- **Resume capability**: Skips already-loaded years

## Architecture

```
orchestrate.py (CLI)
    │
    ├─> ThreadPoolExecutor (10 workers)
    │
    └──> StationPipeline (per station)
            │
            ├─> calculate yearly chunks (2000-2025 = 26 chunks)
            │
            └─> for each year:
                    ├─> API Client (with retries) → fetch_station_year()
                    └─> Atomic Storage → write to disk
```

## Components

### `config.py`
- Station registry (loads from `metadata/stations_config.json`)
- API configuration (keys, endpoints, limits)
- Chunk size calculation (1 year = optimal)
- Retry settings

### `api_client.py`
- EDR API interaction with `requests`
- Retry logic using `tenacity`
- Exponential backoff (2s → 30s)
- Honors `Retry-After` headers on 429 errors
- Retries on 5xx server errors and network failures

### `storage.py`
- Atomic write pattern (write-to-temp + rename)
- Guarantees no partial files in data lake
- Partitioned output: `station_id={id}/year={year}/data.json`

### `station_pipeline.py`
- Independent pipeline per station
- Loads one year at a time
- Tracks progress (completed, skipped, failed)
- Resume capability

### `orchestrate.py`
- CLI entry point
- Parallel execution with `ThreadPoolExecutor`
- Progress logging
- Summary statistics

## Usage

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Test with Single Year (Recommended First Step)

```bash
# Test Hupsel for 2024 only (~10 seconds)
python -m data_orchestration.bronze_raw.orchestrate \
  --station hupsel \
  --start-year 2024 \
  --end-year 2024
```

### Load Single Station (Full Historical)

```bash
# Load Hupsel 2000-2025 (26 API calls, ~4-5 minutes)
python -m data_orchestration.bronze_raw.orchestrate \
  --station hupsel \
  --start-year 2000 \
  --end-year 2025
```

### Load All 10 Core Stations (Parallel!)

```bash
# Load all stations in parallel (~4-5 minutes total!)
python -m data_orchestration.bronze_raw.orchestrate \
  --stations core_10 \
  --start-year 2000 \
  --end-year 2025
```

### Load Specific Stations

```bash
# Load 3 stations
python -m data_orchestration.bronze_raw.orchestrate \
  --stations hupsel,deelen,de_bilt \
  --start-year 2000 \
  --end-year 2025
```

### Other Options

```bash
# Force reload (ignore existing files)
--force

# Adjust concurrency (default: 10, optimal from testing)
--max-workers 5

# Verbose logging (DEBUG level)
--verbose
```

## Output Structure

```
data/bronze/raw/edr_api/
  station_id=0-20000-0-06283/    # Hupsel
    year=2000/
      data.json                   # 201,480 data points (1 year)
    year=2001/
      data.json
    ...
    year=2025/
      data.json
  station_id=0-20000-0-06275/    # Deelen
    year=2000/
      data.json
    ...
```

**Key Benefits:**
- ✅ One file = one year (intuitive!)
- ✅ Natural partitioning (queries align with files)
- ✅ Easy debugging (rerun single year if needed)
- ✅ Clean file structure

## Performance

**From API testing:**
- Optimal workers: 10 (30 req/sec achieved)
- Time per API call: ~10 seconds average
- Data points per year: 201,480 (54% of 376K limit - safe margin)

**Expected times:**
- Single station (26 years): ~4-5 minutes
- 10 stations in parallel: ~4-5 minutes (same!)
- Per year: ~10 seconds

**Scalability:**
- Can load 70+ stations in ~10-15 minutes
- Resume capability allows incremental loading
- No API quota issues (well under 1000 req/hour)

## Error Handling

The system handles:

1. **Rate limiting (429 errors)**
   - Honors `Retry-After` header
   - Exponential backoff if header missing

2. **Server errors (5xx)**
   - Automatic retry with backoff
   - Max 5 attempts

3. **Network errors**
   - Connection timeouts
   - DNS failures
   - Automatic retry

4. **Data integrity**
   - Atomic writes prevent partial files
   - Failed writes cleaned up automatically

5. **Resume**
   - Skips already-loaded years by default
   - Use `--force` to reload

## Logging

Logs are written to:
- **Console**: INFO level (or DEBUG with `--verbose`)
- **File**: `logs/bronze_raw_orchestrator_YYYYMMDD_HHMMSS.log`

Log format:
```
2025-11-18 14:30:15 | INFO     | Loading Hupsel: 2000-2025 (26 years)
2025-11-18 14:30:16 | INFO     |   Fetching Hupsel 2000...
2025-11-18 14:30:26 | INFO     |   ✅ Hupsel 2000 → data/bronze/raw/edr_api/station_id=0-20000-0-06283/year=2000/data.json
```

## Validation

After loading, verify data:

```bash
# Check files created
ls -lah data/bronze/raw/edr_api/station_id=*/year=*/

# Count JSON files
find data/bronze/raw/edr_api/ -name "data.json" | wc -l

# Check a file
python -c "
import json
with open('data/bronze/raw/edr_api/station_id=0-20000-0-06283/year=2024/data.json') as f:
    data = json.load(f)
    print(f'Type: {data[\"type\"]}')
    print(f'Coverages: {len(data.get(\"coverages\", []))}')
"
```

## Next Steps

After Bronze Raw is complete:

1. **Phase 2**: `data_orchestration/bronze_refined/` - Transform JSON → Parquet
2. **Phase 3**: `data_orchestration/silver/` - Data quality and validation

## Design Decisions

### Why 1-year chunks?
- **Simplicity**: One file = one year (easy to understand)
- **Query alignment**: Most analyses are yearly
- **File size**: ~200K data points per file (manageable)
- **Safe API usage**: 54% of limit (plenty of margin)
- **Easy debugging**: Rerun single year if needed

### Why per-station parallelization?
- **Independence**: Station A failure doesn't affect Station B
- **Clean logs**: Each station's progress clearly visible
- **Scalability**: Can run 10-70 stations in parallel
- **Resume**: Restart single station if needed

### Why not async?
- **Testing showed**: 10 workers is optimal (ThreadPoolExecutor)
- **Simplicity**: No async/await complexity
- **Performance**: Same results as async for this use case
- **Debugging**: Easier to debug synchronous code

## Troubleshooting

**"API connection test failed"**
- Check API key in `C:\AI-Projects\.env`
- Verify network connectivity
- Check API status at https://dataplatform.knmi.nl

**"Station not found"**
- Check station key spelling (e.g., "hupsel" not "Hupsel")
- See available stations in `metadata/stations_config.json`

**"Max retries exceeded"**
- API may be down - check status
- Rate limit exceeded - wait 1 hour
- Network issue - check connection

**Slow performance**
- Expected: ~10 sec per API call
- Parallel loading should be ~4-5 min for all 10 stations
- If slower: check network bandwidth

**Files not created**
- Check disk space
- Check write permissions
- Check logs for errors

## API Details

**Endpoint:**
```
GET https://api.dataplatform.knmi.nl/edr/v1/collections/hourly-in-situ-meteorological-observations-validated/locations/{station_id}?datetime={start}/{end}
```

**Rate Limits:**
- 200 requests/second
- 1000 requests/hour
- ~376,000 data points per request (hard limit)

**Data Point Calculation:**
```
hours × parameters × stations = data points
(365 × 24) × 23 × 1 = 201,480 points (1 station, 1 year)
```

**Authentication:**
- Bearer token in `Authorization` header
- Key from `.env`: `KNMI_EDR_API_KEY`

---

**Ready to load! 🚀**

Start with a test:
```bash
python -m data_orchestration.bronze_raw.orchestrate --station hupsel --start-year 2024 --end-year 2024
```
