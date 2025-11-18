# 01: API Limits Summary

This document summarizes the known operational limits of the KNMI EDR API, which are critical constraints for designing the data ingestion process.

## Key API Limits

There are three primary limits to consider:

1.  **Data Point Limit per Call:** `~376,000` data points
    *   **Source:** Confirmed via direct testing in `API_LIMIT_TESTING_OUTCOME.md`. The API returns a `413 Payload Too Large` error when a request exceeds this.
    *   **Calculation:** `total_datapoints = number_of_stations * number_of_hours * number_of_parameters`
    *   **Implication:** This is the most important constraint. Every API call must be chunked to keep the total requested data points safely below this limit. A 1-year request for a single station (`1 * 8760 * 23 ≈ 201k points`) is safe, but a 2-year request is not.

2.  **Request Rate Limit:** `200` requests per second
    *   **Source:** This is the advertised limit from the KNMI developer portal.
    *   **Implication:** This governs the theoretical maximum throughput. Our async ingestion design should aim to parallelize requests to leverage this, but practical limits may be lower. Testing revealed a practical limit of ~30 req/sec, suggesting other bottlenecks may exist.

3.  **Request Count Limit:** `1,000` requests per hour
    *   **Source:** Mentioned in project documentation (`CLAUDE.md`) based on the registered API key tier.
    *   **Implication:** This is a crucial constraint for large historical backfills. For example, a backfill requiring 2,400 API calls (like the v1 single-station approach) would take over two hours to complete without being throttled. The v2 multi-station optimization (requiring only 156 calls for the same workload) comfortably fits within this hourly limit, making it a far more viable strategy.
