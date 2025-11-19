# Gemini Project: Phase 3 - Silver Layer Development

## Project Overview
This project is a Python-based data engineering pipeline designed to download, process, and store historical weather data from the Royal Netherlands Meteorological Institute (KNMI) API. The goal is to create a local dataset of hourly weather conditions. The project utilizes a medallion architecture (Bronze/Silver/Gold layers) with a strong focus on API optimization and efficient data processing of immutable historical data.

## Current Project Status

### Bronze Raw Layer (Source to JSON) - **PRODUCTION-READY ✅**
*   **Ingestion:** The pipeline to ingest data from the KNMI EDR API into the Bronze Raw layer (JSON files) is fully functional, highly optimized, and robust.
*   **Performance:** Parallel station loading with 10 concurrent workers. Successfully loaded 36 years (1990-2025) for 10 stations = 360 station-years.
*   **Metrics:** 0.27s per year average, 100% success rate, instant resume capability (0.1s for 26 years).
*   **Metadata Management:** Intelligent metadata tracking and skip logic, ensuring idempotency and efficient re-runs.
*   **Data Characteristics:** Immutable historical weather data - past data never changes, optimized for write-once read-many patterns.
*   **Location:** `data_orchestration/bronze_raw/orchestrate.py`
*   **Output:** `data/bronze/raw/edr_api/station_id=.../year=.../data.json` (~1.3 GB for 360 station-years)

### Bronze Refined Layer (JSON to Parquet) - **PRODUCTION-READY ✅**
*   **Transformation:** Hardened transformation from Bronze Raw (JSON) to Bronze Refined (Parquet) with schema-on-read approach.
*   **Performance:** Parallel station processing with 10 concurrent workers. Transformed 56 station-years → 662 monthly Parquet files in 11.5 seconds.
*   **Compression:** ~11x compression ratio (3.76 MB JSON → ~330 KB Parquet per year).
*   **Monthly Partitioning:** Each year split into 12 monthly Parquet files for efficient querying and partition pruning.
*   **Idempotency:** Automatic skip of already-transformed months for instant re-runs.
*   **Schema-on-Read:** No strict schema enforcement - preserves all source fields dynamically for future-proofing.
*   **Location:** `data_orchestration/bronze_refined/orchestrate.py`
*   **Output:** `data/bronze/refined/edr_api/station_id=.../year=.../month=.../data.parquet` (~200 MB for full dataset)

## Next Session Agenda - Silver Layer Development

### Priority 1: Bronze Refined to Silver Layer (Validation & Cleaning)
*   **Objective:** Once the Bronze Refined layer is standardized, the next step is to create the **Silver layer**. This layer will focus on data validation, cleaning, deduplication, and applying business rules. This is the stage where strict schema enforcement will typically be introduced.
*   **Current Script:** The existing script for this transformation is `src/transform_silver.py`.
*   **Focus:** We will define and implement industry standards for data quality, consistency, and transformation for the Silver layer, making the data ready for reporting and analysis.

### Priority 2: Test Querying on Bronze Refined Dataset
*   **Objective:** Perform test querying using DuckDB and Polars on the Bronze Refined layer to demonstrate query performance and validate data structure with the full 36 years of data for 10 stations.
*   **Focus:** Create example queries, benchmark performance, validate monthly partitioning efficiency.

### Priority 3: Transform Full Historical Dataset (1990-2025)
*   **Objective:** Run Bronze Refined transformation for complete historical dataset (360 station-years) to prepare for Silver layer development.
*   **Command:** `python -m data_orchestration.bronze_refined.orchestrate --stations core_10 --start-year 1990 --end-year 2025`

## Active Development Areas
*   `data_orchestration/bronze_refined/`: Bronze Refined orchestration (COMPLETED).
*   `src/transform_silver.py`: Silver layer transformation (NEXT PRIORITY).
*   `metadata/`: Configuration and metadata tracking.

## Key Data Characteristic: Immutability
This project deals with immutable historical weather data, meaning once recorded, past data points do not change. Our data pipeline design explicitly leverages this characteristic to optimize for write-once, read-many patterns, ensuring data integrity and simplified historical tracking.

---
*This document serves as the primary context anchor for the current project phase.*
