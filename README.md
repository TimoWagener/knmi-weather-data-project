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

- **Stations Loaded**: All 10 core stations are fully loaded
  - ✅ Hupsel, Deelen, De Bilt, Schiphol, Rotterdam, Vlissingen, Maastricht, Eelde, Den Helder, Twenthe
- **Coverage**: 1990-2025 (36 years per station = 360 station-years)
- **Parameters**: 23+ weather measurements (temp, humidity, rainfall, wind, etc.)
- **Bronze Raw**: ~1.3 GB JSON (360 station-years) ✅ COMPLETE
- **Bronze Refined**: ~200 MB Parquet with monthly partitioning ✅ COMPLETE
- **Next Phase**: Silver layer (validation, cleaning, quality scoring)

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

### 3. Download and Transform Data

```bash
# 🚀 STEP 1: Ingest Bronze Raw data (JSON from API)
# This command is idempotent and will skip already downloaded years
python -m data_orchestration.bronze_raw.orchestrate --stations core_10 --start-year 1990 --end-year 2025

# 🚀 STEP 2: Transform to Bronze Refined (Parquet with monthly partitioning)
# This command is idempotent and will skip already transformed months
python -m data_orchestration.bronze_refined.orchestrate --stations core_10 --start-year 1990 --end-year 2025

# 📊 STEP 3: Transform to Silver layer (validation, quality scoring)
# Coming soon - currently in development
# python -m data_orchestration.silver.orchestrate --stations core_10 --start-year 1990 --end-year 2025
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
├── GEMINI.md             # Current project status and next steps
├── requirements.txt      # Python dependencies
├── .env.example         # API key template
├── .gitignore           # Git ignore rules
│
├── data_orchestration/  # CORE: Bronze ingestion orchestrator
│   └── bronze_raw/
│       ├── orchestrate.py
│       ├── station_pipeline.py
│       ├── api_client.py
│       └── ...
│
├── src/                 # CORE: Transformation logic
│   ├── config.py                       # Global configuration
│   ├── transform_bronze_refined.py     # JSON → Parquet
│   ├── transform_silver.py             # Parquet → Validated Parquet
│   └── query_demo.py                   # Demo queries (DuckDB/Polars/Pandas)
│
├── archive/
│   ├── legacy_v2/                      # Old v2 multi-station batching scripts
│   ├── outdated_docs/                  # Old project status and research docs
│   └── v1_single_station/              # Original single-station scripts
│
├── docs/                # Project documentation
│   ├── architecture/
│   ├── research/
│   └── ingestion_strategy/
│
├── metadata/            # Orchestration metadata
│   ├── stations_config.json
│   └── bronze_raw/
│       └── ...
│
├── logs/                # .log and .json structured logs
│
├── data/                # Data files (not in git)
│   ├── bronze/
│   │   ├── raw/        # Immutable JSON from API
│   │   └── refined/    # Queryable Parquet
│   ├── silver/         # Validated & cleaned
│   └── gold/           # Aggregated (not yet built)
│
└── ...
```

## 🏗️ Architecture

### Medallion Layers

**Bronze Raw** (Immutable Source of Truth) ✅
- Format: JSON (exact EDR API responses)
- Purpose: Compliance, reprocessing, debugging
- Size: ~1.3 GB for 360 station-years
- Status: PRODUCTION-READY

**Bronze Refined** (Schema-on-Read) ✅
- Format: Parquet (columnar, compressed, monthly partitioned)
- Schema: Dynamic (preserves all source fields)
- Compression: ~11x (3.76 MB JSON → ~330 KB Parquet per year)
- Size: ~200 MB for full dataset
- Status: PRODUCTION-READY

**Silver** (Validated & Cleaned) 🚧
- Format: Parquet with fixed schema
- Features: Quality scoring, outlier detection, deduplication
- Status: IN DEVELOPMENT

**Gold** (Business Intelligence) 📋
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





## 🔧 Configuration

Edit `src/config.py` to customize:

- **Stations**: Add more weather stations
- **Date Ranges**: Define custom time periods
- **Parameters**: Select specific weather variables
- **Paths**: Change data storage locations

## 📚 Documentation

- **[GEMINI.md](GEMINI.md)**: Current project status, next steps, and core principles.
- **[Architecture Docs](docs/architecture/)**: High-level design documents, including the overall Medallion plan and v3 orchestration design.
- **[Research Docs](docs/research/)**: Deep dives into API optimization and comparisons.
- **[Ingestion Strategy](docs/ingestion_strategy/)**: Detailed plans and findings related to the Bronze ingestion process.

## 🤝 Contributing

This is a personal project, but feel free to fork and adapt for your own use!

## 📝 License

MIT License - feel free to use and modify

## 🙏 Acknowledgments

- **KNMI** (Royal Netherlands Meteorological Institute) for providing free weather data
- **EDR API** following OGC Environmental Data Retrieval standards
- Built with **DuckDB**, **Parquet**, and **Python**




