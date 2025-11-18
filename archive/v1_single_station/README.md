# Archived: Single-Station Implementation (v1)

**Archived Date:** 2025-11-17
**Reason:** Migrating to multi-station batch loading for API efficiency

## What's Archived

This directory contains the original single-station implementation before optimization.

### Files

- `ingest_bronze_raw.py` - Original ingestion script (one station per API call)
- `orchestrate_historical.py` - Original orchestrator (station-level parallelism)

## Performance Characteristics (v1)

**Approach:** One API call per station per time chunk

**Performance:**
- 10 stations × 25 years × 12 months = **3,000 API calls**
- Loading time: ~45-60 minutes for 10 stations
- Rate limit usage: 3 hours of quota (1000 calls/hour)

## Why We Changed

The KNMI EDR API supports **comma-separated station IDs** in a single request:
```
/locations/station1,station2,station3?datetime=...
```

This enables:
- **80-90% reduction in API calls** (3,000 → 200-300)
- **3-5x faster loading** (~10-15 minutes for 10 stations)
- **Better rate limit utilization** (can load 30+ stations per session)

## How to Use Archived Version

If needed, you can revert to this implementation:

```bash
# Copy archived version back to src/
cp archive/v1_single_station/ingest_bronze_raw.py src/ingest_bronze_raw.py
cp archive/v1_single_station/orchestrate_historical.py src/orchestrate_historical.py

# Use as before
python src/orchestrate_historical.py --stations core_10
```

## Migration Notes

**Data Compatibility:** The new multi-station implementation produces identical output files. Bronze Raw structure remains unchanged, so existing data is fully compatible.

**Fallback Strategy:** If multi-station queries encounter issues, this archived version can be restored without data loss.

---

**Status:** ✅ Stable, production-tested on 2 stations (316K+ records)
**Replaced By:** v2 Multi-Station Batch Loading (implemented 2025-11-17)
