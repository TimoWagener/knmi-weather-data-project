# KNMI Open Data API: Complete Research Findings

**Date:** 2025-11-12
**Dataset:** hourly-in-situ-meteorological-observations-validated v1.0
**Goal:** Extract full 2024 + 2025 data for all stations

---

## Executive Summary

**Key Finding:** The EDR API would be ideal for filtered queries, but requires separate registration. Your current API key works only with the Open Data API (file-based). However, the Open Data API has excellent capabilities that make it viable for the project.

**Recommendation:** Use Open Data API with optimized downloading strategy. Can retrieve full 2024-2025 data in ~18 hours of API quota time using concurrent downloads.

---

## API Comparison

### 1. Open Data API (File-Based) ✅ YOU HAVE ACCESS

**Your API Key Type:** Registered
**Status:** Working and tested

**Capabilities:**
- List files with filtering and pagination
- Get temporary download URLs for files
- Download entire NetCDF files (all stations included)

**Rate Limits:**
| Metric | Limit |
|--------|-------|
| Rate | 200 requests/second |
| Quota | 1,000 requests/hour |
| File Listing | Up to 100 files/request |

**File Filtering Options:**
```python
params = {
    "maxKeys": 100,              # Number of results (max 100)
    "orderBy": "filename",       # or "lastModified", "created"
    "sorting": "desc",           # or "asc"
    "begin": "filename.nc",      # Start from specific file
}
```

**Pagination:**
- Returns `nextPageToken` for large result sets
- Can iterate through all files efficiently
- Tested: 100 files/request works well

### 2. EDR API (Query-Based) ❌ REQUIRES SEPARATE REGISTRATION

**Your Current Access:** None (403 Forbidden)
**What It Offers:**
- Query specific stations without downloading full files
- Filter by date range and parameters
- Much more efficient for single-station queries
- Only download the exact data you need

**Example EDR Query:**
```python
# If you had EDR access, you could do:
params = {
    "datetime": "2024-01-01T00:00:00Z/2025-12-31T23:59:59Z",
    "parameter-name": "T,U,RH"  # Only temp, humidity, rainfall
}
response = requests.get(
    f"{EDR_URL}/collections/hourly-observations/locations/06275",
    params=params, headers=headers
)
# Returns ONLY Deelen station data for 2024-2025
```

**To Get EDR Access:**
1. Login to https://dataplatform.knmi.nl
2. Navigate to API Catalog
3. Request EDR API key (separate from Open Data API key)

---

## Full 2024-2025 Data Extraction: The Numbers

### Data Scope
- **2024:** 366 days × 24 hours = **8,784 files** (leap year)
- **2025:** 365 days × 24 hours = **8,760 files**
- **Total:** **17,544 files**

### File Structure (tested)
- Each file: ~36 KB compressed NetCDF
- Contains: 12 stations, 29 variables, 1 hour
- Total download size: ~631 MB (17,544 × 36 KB)
- Uncompressed Parquet (all data): ~1.5 GB estimated

### API Requests Needed

**File Listing:**
- Requests: 176 (at 100 files/request)
- Time: <1 second at max rate

**Download URL Generation:**
- Requests: 17,544 (one per file)
- Time: 87.7 seconds at 200 req/sec rate

**Total API Requests:** 17,720

### Time Estimates

**Current Approach (4-second delay):**
- Time: 17,544 × 4 sec = **19.5 hours**
- Reason for delay: Unknown (possibly overly cautious)

**Quota-Limited (No Artificial Delay):**
- Quota: 1,000 requests/hour
- Time: 17,720 / 1,000 = **17.7 hours**
- This is the real bottleneck, not rate limiting

**Optimal Strategy:**
- Remove 4-second delay (unnecessary)
- Use concurrent downloads (10 threads)
- Respect quota limits (1,000/hour)
- Total time: **~18 hours** (quota-bound)
- Can run overnight easily

---

## Tested File Listing Capabilities

### ✅ Start from Specific Date
```python
params = {
    "begin": "hourly-observations-validated-20240101-00.nc",
    "maxKeys": 100,
    "orderBy": "filename",
    "sorting": "asc"
}
```
Result: Returns files starting from Jan 1, 2024

### ✅ Get Latest Files
```python
params = {
    "orderBy": "lastModified",
    "sorting": "desc",
    "maxKeys": 10
}
```
Result: Returns most recently updated files (useful for incremental updates)

### ✅ Pagination
- Returns `nextPageToken` in response
- Use token for next request
- Can fetch all 17,544 files efficiently

### ❌ Date Range Filtering
- No native date range filtering
- Must filter by filename patterns yourself
- Need to construct filename list based on dates

---

## Optimal Data Extraction Strategy

### Strategy 1: Download All Files (Recommended)
**Use Case:** Want all stations, all variables, maximum flexibility

**Approach:**
1. Generate list of filenames for 2024-2025
   ```python
   filenames = []
   for date in date_range(2024-01-01, 2025-12-31):
       for hour in range(24):
           filename = f"hourly-observations-validated-{date:%Y%m%d}-{hour:02d}.nc"
           filenames.append(filename)
   ```

2. Download with concurrency (10 threads)
   ```python
   def download_file(filename):
       url = get_download_url(filename)  # API call 1
       download(url)                      # Not an API call
       convert_to_parquet(filename)       # Process immediately
       delete_netcdf(filename)            # Save disk space

   with ThreadPoolExecutor(max_workers=10) as executor:
       executor.map(download_file, filenames)
   ```

3. Bronze layer: Save all data to partitioned Parquet
   - Partition: `year=YYYY/month=MM/day=DD/hour=HH/`
   - Never re-download

**Benefits:**
- All 12 stations preserved
- All 29 variables preserved
- Query any combination later
- Total time: ~18 hours (run overnight)

### Strategy 2: Use EDR API (If You Register)
**Use Case:** Only need specific stations

**Approach:**
1. Register for EDR API key
2. Single query per station for entire 2024-2025 range
3. Much faster, less data transfer

**Benefits:**
- 100x less data downloaded
- Minutes instead of hours
- Direct JSON/CSV output

**Tradeoffs:**
- Need new API registration
- Locked into specific stations
- Less flexible for future analysis

---

## Recommendations

### Immediate Action Plan

**Short Term (This Week):**
1. ✅ **Use Open Data API** (you already have access)
2. ✅ **Implement concurrent downloads** (remove 4-sec delay, use 10 threads)
3. ✅ **Download to Parquet immediately** (Bronze layer)
4. ✅ **Run overnight** (~18 hours for full 2024-2025)

**Medium Term (Next Month):**
1. ⭐ **Register for EDR API key** (for future incremental updates)
2. Use EDR for daily updates (more efficient)
3. Keep Open Data API for historical bulk downloads

### Architecture Recommendation

**Bronze Layer: Keep All Data**
- Store all 12 stations, all 29 variables
- Format: Partitioned Parquet
- Size: ~1.5 GB for 2024-2025
- Download time: 18 hours (one-time)
- Storage cost: Negligible (under 2 GB)

**Why Keep Everything:**
1. You're downloading it anyway (NetCDF has all stations)
2. Storage is cheap (~1.5 GB)
3. Future flexibility (analyze different stations later)
4. No re-downloading needed
5. Disk space is cheaper than API time

**Silver/Gold Layers:**
- Filter to specific stations as needed
- Create aggregated views
- Query in milliseconds with DuckDB

---

## Revised Time Estimates

### Full 2024-2025 Download Timeline

| Phase | Time | Description |
|-------|------|-------------|
| File list generation | 1 min | Generate 17,544 filenames |
| Download URL requests | 18 min | Get temporary URLs (quota-limited) |
| File downloads | 17 hours | Concurrent downloads (10 threads) |
| NetCDF → Parquet conversion | ~2 hours | Process during download |
| **Total** | **~18-20 hours** | Run overnight |

### Daily Incremental Updates

Once you have 2024-2025 data:
- New files per day: 24 (one per hour)
- API requests: 24
- Download time: 2 minutes
- Can run hourly or daily

---

## Code Optimization Opportunities

### Current Code Issues

1. **4-Second Delay:** Unnecessary
   ```python
   time.sleep(4)  # Remove this!
   ```
   - API has built-in rate limiting
   - Will return 429 if you exceed limits
   - Delays artificially increase download time

2. **Sequential Processing:** Inefficient
   ```python
   for file in files:
       download(file)  # One at a time
   ```
   - Should use concurrent downloads
   - 10 threads recommended
   - Respect 200 req/sec rate limit

3. **Temporary File Cleanup:** Good, but could be better
   ```python
   # Current: Download NetCDF, process, delete
   # Better: Stream directly to Parquet
   ```

### Optimized Code Structure

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=1000, period=3600)  # 1000/hour quota
def get_download_url(filename):
    # API call (counted against quota)
    ...

def download_and_process(filename):
    try:
        url = get_download_url(filename)
        nc_data = download_netcdf(url)  # Not an API call
        parquet_data = convert_all_stations(nc_data)  # Keep all data!
        save_to_bronze(parquet_data)
        return {"status": "success", "file": filename}
    except Exception as e:
        return {"status": "error", "file": filename, "error": str(e)}

# Concurrent execution
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(download_and_process, f): f for f in filenames}
    for future in as_completed(futures):
        result = future.result()
        print(f"Processed: {result['file']} - {result['status']}")
```

---

## Next Steps

**Option A: Quick Start (Open Data API)**
1. Modify existing `download_data.py`:
   - Remove 4-second delay
   - Add concurrent downloads (10 threads)
   - Keep ALL stations/variables (not just one!)
   - Convert to Parquet instead of CSV
2. Start download overnight
3. Wake up to full 2024-2025 data

**Option B: Wait for EDR (More Efficient)**
1. Register for EDR API key
2. Query specific stations directly
3. Much faster, but less flexible

**My Recommendation:** Go with Option A now, register for EDR later for incremental updates.

---

## Questions for You

1. **Do you want to keep all 12 stations?**
   - Storage: only ~1.5 GB total
   - You're downloading them anyway
   - Minimal extra cost

2. **Are you okay with an 18-hour download?**
   - Can run overnight
   - One-time operation
   - Then you have everything locally

3. **Want me to implement the optimized downloader?**
   - Concurrent downloads
   - All stations preserved
   - Direct to Parquet
   - Progress tracking

Let me know and I'll build it!
