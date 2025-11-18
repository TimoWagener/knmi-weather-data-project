# KNMI Weather Data Lakehouse 🌦️

A production-ready data lakehouse for Dutch weather data using **medallion architecture** (Bronze/Silver/Gold layers) with **93.5% API optimization** through multi-station batch loading.

Downloads hourly weather observations from the KNMI EDR API, processes through data quality layers, and provides efficient querying with DuckDB, Polars, and Pandas.

![Data Architecture](https://img.shields.io/badge/Architecture-Medallion-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Optimization](https://img.shields.io/badge/API_Efficiency-93.5%25-brightgreen)

## 🌟 Features

- 🚀 **93.5% API Optimization**: Multi-station batch loading (v2) - load 8 stations with 156 API calls vs 2,400!
- ✅ **Medallion Architecture**: Bronze (raw) → Silver (validated) → Gold (aggregated)
- ✅ **Modern Stack**: DuckDB, Polars, Pandas, Parquet, Python 3.10+
- ✅ **Data Quality**: Automated validation, outlier detection, quality scoring
- ✅ **Efficient Storage**: Columnar Parquet with monthly partitioning
- ✅ **Fast Queries**: Sub-second queries on millions of records
- ✅ **77 Stations Available**: Access to all KNMI weather stations across Netherlands
- ✅ **Scalable**: Can load 48-60 stations per session (entire KNMI network in 2-3 hours!)
- ✅ **Metadata Tracking**: Automated load status, gap detection, resume capability
- ✅ **Secure**: API keys in .env, not in code

## 📊 Current Data

- **Stations Loaded**: 2 complete, 8 loading (10 total configured)
  - ✅ Hupsel (rural, eastern Netherlands)
  - ✅ Deelen (Veluwe, airport)
  - 🔄 De Bilt, Schiphol, Rotterdam, Vlissingen, Maastricht, Eelde, Den Helder, Twenthe (loading now)
- **Coverage**: 316,278 hours (2000-2025, 25+ years per station)
- **Parameters**: 23 weather measurements (temp, humidity, rainfall, wind, pressure, solar, visibility, etc.)
- **Storage**: ~292 MB across all layers (Bronze Raw: 206 MB, Refined: 42 MB, Silver: 44 MB)
- **Quality**: Automated scoring, outlier detection, data validation on all records

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <repository-url>
cd LocalWeatherDataProject

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
# Copy template
cp .env.example .env

# Edit .env and add your KNMI API keys
# Get keys from: https://developer.dataplatform.knmi.nl/
```

### 3. Download Data

```bash
# 🚀 v2 Multi-Station Batch Loading (RECOMMENDED - 93.5% fewer API calls!)
# Load all 10 configured stations (2000-2025, ~90-120 minutes)
python src/orchestrate_historical_v2.py --stations core_10 --start-year 2000 --end-year 2025 --batch-size 8 --chunk-months 2

# Or manual single-station pipeline (for custom date ranges)
python src/ingest_bronze_raw.py --station hupsel --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"
python src/transform_bronze_refined.py --station hupsel --year 2024
python src/transform_silver.py --station hupsel --year 2024
```

### 4. Query the Data

```bash
# Run demo queries
python src/query_demo.py
```

## 📁 Project Structure

```
LocalWeatherDataProject/
├── README.md              # This file
├── CLAUDE.md             # Guidance for Claude Code AI
├── PROJECT_STATUS.md     # Detailed project status
├── requirements.txt      # Python dependencies
├── .env.example         # API key template
├── .gitignore           # Git ignore rules
│
├── src/                 # Main source code
│   ├── config.py                       # Configuration
│   ├── ingest_bronze_raw.py            # Download from EDR API (v2 multi-station!)
│   ├── orchestrate_historical_v2.py    # 🚀 Multi-station batch loader (v2)
│   ├── transform_bronze_refined.py     # JSON → Parquet
│   ├── transform_silver.py             # Validate & clean
│   ├── query_demo.py                   # Demo queries (DuckDB/Polars/Pandas)
│   └── metadata_manager.py             # Metadata tracking
│
├── archive/
│   └── v1_single_station/              # Legacy code (pre-optimization)
│
├── metadata/            # Orchestration metadata
│   ├── stations_config.json         # 10 station registry
│   ├── load_metadata.json           # Load history tracking
│   └── pipeline_config.json         # Pipeline settings
│
├── logs/                # Orchestration logs
│
├── scripts/             # Utility scripts
│   ├── test_edr_api.py
│   ├── test_multi_station_api.py    # Multi-station API tester
│   └── explore_*.py
│
├── docs/                # Documentation
│   ├── API_OPTIMIZATION_OPPORTUNITIES.md  # v2 optimization analysis
│   ├── MULTI_STATION_OPTIMIZATION_SUMMARY.md  # Complete v2 guide
│   ├── API_RESEARCH_FINDINGS.md
│   ├── ARCHITECTURE_PLAN.md
│   └── EDR_VS_OPEN_DATA_COMPARISON.md
│
├── notebooks/           # Jupyter notebooks (future)
├── tests/              # Unit tests (future)
└── data/               # Data files (not in git)
    ├── bronze/
    │   ├── raw/        # Immutable JSON from API
    │   └── refined/    # Queryable Parquet
    ├── silver/         # Validated & cleaned
    └── gold/           # Aggregated (not yet built)
```

## 🏗️ Architecture

### Medallion Layers

**Bronze Raw** (Immutable Source of Truth)
- Format: JSON (exact EDR API responses)
- Purpose: Compliance, reprocessing, debugging
- Size: ~5.7 MB for 2024-2025

**Bronze Refined** (Schema-on-Read)
- Format: Parquet (columnar, compressed)
- Schema: Dynamic (preserves all source fields)
- Size: ~650 KB for 2024-2025

**Silver** (Validated & Cleaned)
- Format: Parquet with fixed schema
- Features: Quality scoring, outlier detection, deduplication
- Size: ~750 KB for 2024-2025

**Gold** (Not Yet Built)
- Purpose: Aggregated metrics, multi-station comparisons
- Future: Daily summaries, station comparisons, dashboards

### Data Flow

```
KNMI EDR API
    ↓ (Monthly chunks)
Bronze Raw (JSON)
    ↓ (Flatten structure)
Bronze Refined (Parquet, schema-on-read)
    ↓ (Validate, clean, score quality)
Silver (Parquet, fixed schema)
    ↓ (Aggregate, model)
Gold (Business-ready)
```

## 📖 Usage Examples

### Multi-Station Batch Loading (v2 - Recommended!)

```bash
# Load multiple stations efficiently (93.5% fewer API calls!)
python src/orchestrate_historical_v2.py \
  --stations core_10 \
  --start-year 2000 \
  --end-year 2025 \
  --batch-size 8 \
  --chunk-months 2

# Check load status
python -c "from src.metadata_manager import MetadataManager; MetadataManager().print_status_summary()"
```

### Single Station (manual pipeline)

```bash
# See available stations
python scripts/test_edr_api.py

# Download single station
python src/ingest_bronze_raw.py --station de_bilt --start-date "2024-01-01T00:00:00Z" --end-date "2024-12-31T23:59:59Z"
python src/transform_bronze_refined.py --station de_bilt --year 2024
python src/transform_silver.py --station de_bilt --year 2024
```

### Query with DuckDB

```python
import duckdb

con = duckdb.connect()

# Query all stations, all years
result = con.execute("""
    SELECT
        YEAR(timestamp) as year,
        AVG(temperature_celsius) as avg_temp,
        SUM(rainfall_mm) as total_rain
    FROM 'data/silver/**/*.parquet'
    GROUP BY year
    ORDER BY year
""").df()

print(result)
```

### Incremental Updates (Multi-Station!)

```bash
# Update ALL 10 stations with yesterday's data (v2 feature - one API call!)
python src/ingest_bronze_raw.py \
  --stations hupsel,deelen,de_bilt,schiphol,rotterdam,vlissingen,maastricht,eelde,den_helder,twenthe \
  --start-date "2025-11-17T00:00:00Z" \
  --end-date "2025-11-17T23:59:59Z"

# Then transform each (can be automated)
for station in hupsel deelen de_bilt schiphol rotterdam vlissingen maastricht eelde den_helder twenthe; do
  python src/transform_bronze_refined.py --station $station --year 2025
  python src/transform_silver.py --station $station --year 2025
done
```

## 🚀 v2 Multi-Station Optimization (NEW!)

**Key Achievement: 93.5% Reduction in API Calls**

### What Changed?

**Before (v1 - Single Station):**
- Load 8 stations for 25 years: **2,400 API calls**
- Each station queried separately, each month independently
- Limited scalability (10-15 stations per session max)

**After (v2 - Multi-Station Batching):**
- Load 8 stations for 25 years: **156 API calls** (93.5% fewer!)
- Batch multiple stations in one API call using comma-separated IDs
- Optimal chunk sizing (2-month chunks, 8 stations per batch)
- Can load 48-60 stations per session

### Performance Impact

| Metric | v1 Single-Station | v2 Multi-Station | Improvement |
|--------|-------------------|------------------|-------------|
| API calls (8 stations, 25 years) | 2,400 | 156 | **93.5% fewer** |
| Stations per session (1000 limit) | 10-15 | 48-60 | **4-6x more** |
| Scalability to 70+ stations | Multiple days | 2-3 sessions | **10x faster** |

### Technical Details

```python
# API supports comma-separated station IDs
location_param = ",".join(["station1", "station2", "station3"])
url = f"{EDR_BASE_URL}/collections/{COLLECTION}/locations/{location_param}"

# One call returns data for all stations in CoverageCollection format
# Automatically split and saved per station for backward compatibility
```

**Data point calculation:**
- API limit: 376,000 data points per request
- Our config: 8 stations × 1,440 hours (2 months) × 23 params = 264,960 points (70% of limit)
- Safe, efficient, and maximizes throughput!

**See full analysis:** `docs/MULTI_STATION_OPTIMIZATION_SUMMARY.md`

## 🔧 Configuration

Edit `src/config.py` to customize:

- **Stations**: Add more weather stations
- **Date Ranges**: Define custom time periods
- **Parameters**: Select specific weather variables
- **Paths**: Change data storage locations

## 📚 Documentation

- 🚀 **[Multi-Station Optimization Summary](docs/MULTI_STATION_OPTIMIZATION_SUMMARY.md)**: Complete v2 optimization guide
- 🚀 **[API Optimization Opportunities](docs/API_OPTIMIZATION_OPPORTUNITIES.md)**: Detailed v2 analysis
- **[Project Status](PROJECT_STATUS.md)**: Current status & comprehensive documentation
- **[CLAUDE.md](CLAUDE.md)**: Guidance for Claude Code AI assistant
- **[API Research](docs/API_RESEARCH_FINDINGS.md)**: KNMI API capabilities & limits
- **[Architecture Plan](docs/ARCHITECTURE_PLAN.md)**: Detailed architecture design
- **[EDR vs Open Data](docs/EDR_VS_OPEN_DATA_COMPARISON.md)**: API comparison

## 🤝 Contributing

This is a personal project, but feel free to fork and adapt for your own use!

## 📝 License

MIT License - feel free to use and modify

## 🙏 Acknowledgments

- **KNMI** (Royal Netherlands Meteorological Institute) for providing free weather data
- **EDR API** following OGC Environmental Data Retrieval standards
- Built with **DuckDB**, **Parquet**, and **Python**

## 📧 Support

For issues or questions:
1. Check [PROJECT_STATUS.md](PROJECT_STATUS.md) for detailed documentation
2. Review [docs/](docs/) for architecture details
3. See KNMI API docs: https://developer.dataplatform.knmi.nl/

---

## 🎯 Current Status

**Last Updated**: 2025-11-17
**Version**: v2 (Multi-Station Optimization)
**Status**:
- ✅ v2 Multi-station optimization complete (93.5% API reduction)
- ✅ Bronze & Silver layers production-ready
- ✅ 2 stations fully loaded (Hupsel, Deelen)
- 🔄 8 additional stations loading now
- ⏳ Gold layer pending (future)

**Data**:
- 316,278 hours across 2 stations (2000-2025)
- 10 stations configured and ready
- ~1.75 million hours when current load completes

**Performance**:
- **93.5% fewer API calls** vs v1 single-station approach
- Can load 48-60 stations per session (under 1000 API call limit)
- Entire KNMI network (70+ stations) feasible in 2-3 sessions

**Next Steps**:
1. Complete 8-station load (in progress)
2. Build automated daily updater
3. Expand to 20-30 more stations
4. Create Gold layer for aggregated analytics
