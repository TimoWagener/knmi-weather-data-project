# KNMI Weather Data Lakehouse

A modern data lakehouse for Dutch weather data using **medallion architecture** (Bronze/Silver/Gold layers).

Downloads hourly weather observations from the KNMI EDR API, processes through data quality layers, and provides efficient querying with DuckDB.

![Data Architecture](https://img.shields.io/badge/Architecture-Medallion-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## 🌟 Features

- ✅ **Medallion Architecture**: Bronze (raw) → Silver (validated) → Gold (aggregated)
- ✅ **Modern Stack**: DuckDB, Parquet, Python
- ✅ **Data Quality**: Automated validation, outlier detection, quality scoring
- ✅ **Efficient Storage**: Columnar Parquet with partitioning (~7 MB for 16K hours)
- ✅ **Fast Queries**: Sub-second queries on years of data
- ✅ **77 Stations**: Access to all KNMI weather stations across Netherlands
- ✅ **Secure**: API keys in .env, not in code

## 📊 Current Data

- **Station**: Hupsel (near Doetinchem)
- **Coverage**: 16,345 hours (2024-2025)
- **Parameters**: 21 weather measurements (temp, humidity, rainfall, wind, solar, etc.)
- **Quality**: 0.79-0.80 average score

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
# Full pipeline for Hupsel station (2024-2025)
python src/ingest_bronze_raw.py --station hupsel --date-range full
python src/transform_bronze_refined.py --station hupsel
python src/transform_silver.py --station hupsel
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
│   ├── config.py                    # Configuration
│   ├── ingest_bronze_raw.py        # Download from EDR API
│   ├── transform_bronze_refined.py # JSON → Parquet
│   ├── transform_silver.py         # Validate & clean
│   └── query_demo.py               # Demo queries
│
├── scripts/             # Utility scripts
│   ├── test_edr_api.py
│   └── explore_*.py
│
├── docs/                # Documentation
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

### Download a Different Station

```bash
# See available stations
python scripts/test_edr_api.py

# Download Deelen station
python src/ingest_bronze_raw.py --station deelen --date-range full
python src/transform_bronze_refined.py --station deelen
python src/transform_silver.py --station deelen
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

### Incremental Updates

```bash
# Update with latest 2025 data
python src/ingest_bronze_raw.py --station hupsel --date-range 2025
python src/transform_bronze_refined.py --station hupsel --year 2025
python src/transform_silver.py --station hupsel --year 2025
```

## 🔧 Configuration

Edit `src/config.py` to customize:

- **Stations**: Add more weather stations
- **Date Ranges**: Define custom time periods
- **Parameters**: Select specific weather variables
- **Paths**: Change data storage locations

## 📚 Documentation

- **[API Research](docs/API_RESEARCH_FINDINGS.md)**: KNMI API capabilities & limits
- **[Architecture Plan](docs/ARCHITECTURE_PLAN.md)**: Detailed architecture design
- **[EDR vs Open Data](docs/EDR_VS_OPEN_DATA_COMPARISON.md)**: API comparison
- **[Project Status](PROJECT_STATUS.md)**: Current status & next steps

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

**Last Updated**: 2025-11-12
**Status**: ✅ Bronze & Silver layers complete, Gold layer pending
**Data**: 16,345 hours for Hupsel station (2024-2025)
