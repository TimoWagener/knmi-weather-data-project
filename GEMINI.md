# Gemini Project: Phase 2 - Bronze Refined Hardening & Silver Layer Planning

## Project Overview
This project is a Python-based data engineering pipeline designed to download, process, and store historical weather data from the Royal Netherlands Meteorological Institute (KNMI) API. The goal is to create a local dataset of hourly weather conditions. The project utilizes a medallion architecture (Bronze/Silver/Gold layers) with a strong focus on API optimization and efficient data processing of immutable historical data.

## Current Project Status
### Bronze Raw Layer (Source to JSON) - **PRODUCTION-READY**
*   **Ingestion:** The pipeline to ingest data from the KNMI EDR API into the Bronze Raw layer (JSON files) is fully functional, highly optimized, and robust.
*   **Performance:** It operates with parallel station loading, where each station/year combination is a single API call. It successfully loaded 36 years of data for 10 stations efficiently.
*   **Metadata Management:** Includes intelligent metadata tracking and skip logic, ensuring idempotency and efficient re-runs (only new data is fetched).
*   **Data Characteristics:** The data ingested into this layer is immutable historical weather data (e.g., "weather of yesterday will never be updated"). This characteristic is central to our data engineering strategy.
*   **Location:** `data_orchestration/bronze_raw/orchestrate.py`
*   **Output:** `data/bronze/raw/edr_api/station_id=.../year=.../data.json`

## Next Session Agenda - Hardening Phase

### Priority 1: Bronze Raw to Bronze Refined Hardening (JSON to Parquet)
*   **Objective:** Standardize the transformation from the **Bronze Raw (JSON)** layer to the **Bronze Refined (Parquet)** layer, adhering to industry best practices for "schema-on-read" data lakes. This process primarily involves flattening the raw JSON data and converting it to a query-optimized columnar Parquet format.
*   **Current Script:** The existing script for this transformation is `src/transform_bronze_refined.py`.
*   **Focus:** Ensure this transformation adheres strictly to the "schema-on-read" principle for Parquet files, which implies:
    *   **Format Standardization:** Converting raw JSON into the self-describing Parquet columnar format.
    *   **Basic Flattening:** Transforming nested JSON structures into a tabular format, making it more accessible for querying.
    *   **Type Inference & Coercion:** Allowing the Parquet reader to infer schema and data types, while ensuring basic type consistency from the JSON.
    *   **Partitioning Consistency:** Maintaining the existing Hive-style partitioning (`station_id=X/year=Y`) for efficient data access.
    *   **Idempotency:** The process should be safely re-runnable without data corruption or duplication.
    *   **No Strict Schema Enforcement:** At this stage, the schema is derived from the data itself upon read, providing flexibility for evolving source schemas, rather than being rigidly enforced during write.
*   **Output:** `data/bronze/refined/edr_api/station_id=.../year=.../*.parquet`

### Priority 2: Bronze Refined to Silver Layer (Validation & Cleaning)
*   **Objective:** Once the Bronze Refined layer is standardized, the next step is to create the **Silver layer**. This layer will focus on data validation, cleaning, deduplication, and applying business rules. This is the stage where strict schema enforcement will typically be introduced.
*   **Current Script:** The existing script for this transformation is `src/transform_silver.py`.
*   **Focus:** We will define and implement industry standards for data quality, consistency, and transformation for the Silver layer, making the data ready for reporting and analysis.

### Priority 3: Test Querying on Full Dataset
*   **Objective:** After the Bronze Refined and Silver layers are robust, we will perform extensive test querying using tools like DuckDB or Polars to demonstrate the efficiency and value of our medallion architecture with the full 36 years of data for 10 stations.

## Active Development Areas
*   `data_orchestration/`: Contains the core orchestration logic for the Bronze layer.
*   `src/`: Contains transformation scripts (`transform_bronze_refined.py`, `transform_silver.py`) that are the current focus for standardization and enhancement.
*   `metadata/`: Contains configuration and metadata tracking.

## Key Data Characteristic: Immutability
This project deals with immutable historical weather data, meaning once recorded, past data points do not change. Our data pipeline design explicitly leverages this characteristic to optimize for write-once, read-many patterns, ensuring data integrity and simplified historical tracking.

---
*This document serves as the primary context anchor for the current project phase.*
