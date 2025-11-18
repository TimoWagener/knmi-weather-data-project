# Load Monitor - 2025-11-17

**Load Command:**
```bash
python src/orchestrate_historical_v2.py \
  --stations not_loaded \
  --start-year 2000 \
  --end-year 2025 \
  --batch-size 8 \
  --chunk-months 2
```

**Configuration:**
- Stations: 8 (all remaining core_10 stations)
- Total chunks: 156
- Batch size: 8 stations per API call
- Chunk size: 2 months (bi-monthly)

**Progress Log:**

| Time | Chunks | % | Year Loading | Pace (sec/chunk) | Est. Completion |
|------|--------|---|--------------|------------------|-----------------|
| 19:34 | 0/156 | 0% | Starting | - | - |
| 19:35 | 1/156 | 1% | 2000 | 17.8 | 46 min |
| 19:37 | 10/156 | 6% | 2001 | 21.0 | 51 min |
| 19:48 | 30/156 | 19% | 2005 | 34.3 | 72 min |
| - | - | - | - | - | ~21:00-21:15 |

**Status:** Running smoothly, pace slowed to ~34 sec/chunk (normal for sustained loads)

**Monitoring command:**
```bash
tail -f logs/orchestration_historical_v2.log
```

**Check completion:**
```bash
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```
