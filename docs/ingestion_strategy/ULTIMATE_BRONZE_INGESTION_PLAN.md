# The Ultimate Plan for Bronze Raw Ingestion

This document outlines the architecture and implementation plan for a production-grade, standalone Bronze Raw Ingestion service. This service will be responsible for one thing only: fetching data from the KNMI EDR API and landing it in the raw layer of the data lake with maximum robustness, observability, and integrity.

## 1. Guiding Principles

*   **Separation of Concerns:** The Bronze Raw service is completely separate from downstream transformations (`bronze refined`, `silver`). It does not modify the data; it only lands it.
*   **Idempotency:** Running the service multiple times for the same time range should produce the exact same result without duplication or errors.
*   **Data Integrity:** The service must guarantee that only complete, valid files are ever present in the data lake.
*   **Observability:** The service's behavior, performance, and errors must be transparent and queryable through structured logs.
*   **Resilience:** The service must be robust against transient network and API errors.

## 2. Proposed Architecture

The service will be a standalone Python application, designed to be run via a CLI and easily containerized (e.g., with Docker).

### Core Components:

1.  **Configuration Management (`config.py`):**
    *   Use `Pydantic`'s `BaseSettings` to load all configuration from environment variables and/or a `.env` file.
    *   This provides type validation, default values, and a single source of truth for settings like API keys, concurrency limits, log levels, and data paths.

2.  **Structured Logger (`logging_config.py`):**
    *   A centralized module that sets up a structured JSON logger, as detailed in `05_structured_logging_summary.md`.
    *   All other modules will import and use this configured logger.

3.  **API Client (`client.py`):**
    *   The core logic for making API calls.
    *   It will use `httpx.AsyncClient` for connection pooling.
    *   All public-facing functions (e.g., `fetch_chunk`) will be decorated with the `@async_retryer` from `03_error_handling_and_retries_summary.md` to provide robust, automatic retries.

4.  **File Handler (`storage.py`):**
    *   An abstraction for writing data to the lake.
    *   It will contain the `atomic_write_json` function as detailed in `04_atomic_writes_summary.md`.
    *   This ensures that every single file write performed by the service is atomic, preventing data corruption.

5.  **Orchestrator (`orchestrator.py`):**
    *   The main engine that drives the ingestion process.
    *   It reads the desired date range and station list.
    *   It calculates the optimal chunks (e.g., 2-month periods for 8 stations) to stay under the API data point limit.
    *   It uses the "worker pattern" with `asyncio.Semaphore` and `asyncio.gather` to process these chunks in parallel, as detailed in `02_high_throughput_ingestion_summary.md`.
    *   For each chunk, it calls the robust `fetch_chunk` method from the API client and writes the result using the atomic file handler.

6.  **CLI Interface (`main.py`):**
    *   A simple command-line interface using a library like `argparse` or `click`.
    *   It will allow a user to trigger the ingestion for a specific date range and set of stations.
    *   Example command: `python main.py --start-date 2024-01-01 --end-date 2024-12-31 --stations core_10`

## 3. Detailed Workflow (Historical Backfill)

1.  **Initialization:**
    *   User runs `python main.py --start-year 2000 --end-year 2025 --stations core_10`.
    *   Pydantic loads and validates configuration.
    *   The JSON logger is initialized.

2.  **Chunk Calculation:**
    *   The Orchestrator takes the date range and station list.
    *   It logs the total scope of work: `{"message": "Starting historical backfill", "extra": {"stations": 10, "years": 26}}`.
    *   It divides the work into optimal chunks (e.g., `(stations: [8], start: "2000-01-01", end: "2000-02-29")`, `(stations: [2], start: "2000-01-01", end: "2000-02-29")`, etc.).

3.  **Execution:**
    *   The Orchestrator creates a list of `api_worker` tasks, one for each chunk.
    *   It calls `asyncio.gather` to run them. The semaphore (e.g., set to 15) ensures controlled concurrency.

4.  **A Single Worker's Journey:**
    *   The worker acquires the semaphore.
    *   It calls the `fetch_chunk` function from the API client.
        *   The `tenacity` decorator handles the request. If it fails with a `503` error, it backs off exponentially and retries. If it gets a `429` with a `Retry-After` header, it waits for the specified time.
    *   Upon a successful API response, the worker receives the JSON data.
    *   It calls `atomic_write_json` from the storage module.
        *   The data is written to `.../data.json.xyz-123.tmp`.
        *   The write completes successfully.
        *   `os.rename` is called, and the file instantly appears at its final destination `.../data.json`.
    *   The worker logs its success with structured context: `{"message": "Chunk ingested successfully", "extra": {"chunk_details": ..., "latency": 4.5}}`.
    *   The worker releases the semaphore, allowing another waiting worker to start.

5.  **Completion:**
    *   Once `gather` completes, the orchestrator logs a final summary message: `{"message": "Backfill complete", "extra": {"total_chunks": 156, "failed_chunks": 0, "duration": 3600}}`.

## 4. How This Improves on the Current State

*   **Clear Separation:** This design creates a dedicated "Bronze Ingestion Service" out of the existing scripts. The `transform_bronze_refined.py` and `transform_silver.py` scripts become separate, downstream consumers of the data produced by this service.
*   **Enhanced Robustness:** By formally implementing `tenacity` for retries and atomic writes for all file operations, the pipeline becomes dramatically more resilient to failure and avoids data corruption.
*   **Superior Observability:** Structured JSON logging provides a queryable, data-rich view into the pipeline's operation, making debugging and monitoring far easier than parsing plain text logs.
*   **Configuration Safety:** Using Pydantic ensures that the service cannot start with invalid or missing configuration, preventing a common source of errors.

This plan provides a blueprint for evolving the existing code into a truly professional, best-practice data ingestion service for the Medallion architecture.

---

## Appendix A: Performance Tuning Guide

**Objective:** To empirically determine the optimal `MAX_CONCURRENT_REQUESTS` value for our specific environment to achieve maximum stable throughput. This value is the "sweet spot" where performance is highest before the rate of errors begins to increase.

**Methodology:**
A dedicated tuning script (e.g., `tuning/find_optimal_concurrency.py`) should be created. This script will systematically test different concurrency levels against a realistic workload.

1.  **Define a Realistic Workload:** The test should consist of a fixed number of realistic API calls. For example, 100-200 separate requests, each for a small, valid chunk of data (e.g., 1 station for 1 month). This simulates the real behavior of the orchestrator.

2.  **Iterate Through Concurrency Levels:** The script will loop through a predefined list of concurrency values to test.
    ```python
    CONCURRENCY_LEVELS_TO_TEST = [5, 10, 15, 20, 25, 30, 40, 50, 75, 100]
    ```

3.  **Execute and Measure:** For each concurrency level, the script will:
    *   Set the `asyncio.Semaphore` to that level.
    *   Run the full workload of 100-200 requests using the robust worker pattern.
    *   Record the following key metrics:
        *   **Total Time Taken:** The wall-clock time to complete the entire workload.
        *   **Successful Requests:** The number of requests that returned a `200 OK`.
        *   **Failed Requests:** The number of requests that failed even after all retries.
        *   **Actual Throughput:** Calculated as `(Successful Requests / Total Time Taken)`.

4.  **Output a Results Summary:** After testing all levels, the script will print a clear summary table to the console, allowing the engineer to make an informed decision.

**Example Output:**
```
==================================================================
  Concurrency Tuning Results (100 total requests)
==================================================================
  Concurrency | Time (s) | Success | Failures | Throughput (req/s)
------------------------------------------------------------------
            5 |    20.5s |     100 |        0 |               4.88
           10 |    10.8s |     100 |        0 |               9.26
           15 |     7.2s |     100 |        0 |              13.89
           20 |     6.5s |     100 |        0 |              15.38
           25 |     6.3s |     100 |        0 |              15.87  <-- Sweet Spot
           30 |     6.8s |      99 |        1 |              14.56
           40 |     8.5s |      95 |        5 |              11.18
           50 |    11.2s |      91 |        9 |               8.13
==================================================================
```

**Execution and Outcome:**
The engineer runs this script once during the initial setup of the ingestion service. Based on the output table, they can clearly see that performance peaks around a concurrency of **25**. Throughput starts to decrease and failures begin to appear at levels of 30 and above.

They can then confidently set `MAX_CONCURRENT_REQUESTS = 25` in the application's configuration, knowing it is the optimal data-driven value for their environment. This process should be repeated if the network environment changes or if API performance seems to degrade over time.

This tuning step elevates the plan from a "best practice" design to a **performance-tuned, production-ready** solution.
