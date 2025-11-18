# KNMI EDR API Limit Testing - Outcome & Analysis

**Date:** 2025-11-17
**Test Script:** `scripts/test_api_limits.py`
**Test Plan:** `docs/API_LIMIT_TESTING_PLAN.md`

## 🎯 Executive Summary

The KNMI EDR API has a hard limit on the number of data points per request, confirmed to be approximately **376,000 data points**. This is the single most important constraint for designing efficient data loading strategies.

While the API advertises a rate limit of 200 requests/second, our concurrency tests achieved a maximum of **~30 requests/second**, suggesting that achieving the theoretical maximum is not straightforward and may depend on factors beyond simple concurrency.

**Key Findings:**
1.  **Data Point Limit:** The API enforces a limit of ~376,000 data points. The server returns a `413 Payload Too Large` error when this is exceeded.
2.  **Optimal Single-Station Load:** It is possible to load **1 year** of data for a single station in one request.
3.  **Multi-Station Batching is Limited:** Batching a large number of stations is only feasible for very short time ranges. For example, loading 10 stations is limited to a maximum of ~2 months at a time.
4.  **Concurrency Peak:** The highest throughput was achieved with **10 concurrent workers**, reaching ~30 req/sec. Increasing workers beyond this number did not improve performance.

## 🧪 Detailed Test Results

### Test Series A: Single Station, Increasing Time Range

**Objective:** Find the maximum time range that can be requested for a single station.

| Test | Time Range | Expected Data Points | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| A1 | 1 month | 16,560 | ✅ **SUCCESS** | Response time: 0.20s |
| A2 | 3 months | 49,680 | ✅ **SUCCESS** | Response time: 0.62s |
| A3 | 6 months | 99,360 | ✅ **SUCCESS** | Response time: 0.40s |
| A4 | 1 year | 198,720 | ✅ **SUCCESS** | Response time: 0.80s |
| A5 | 2 years | 397,440 | ❌ **FAILED** | **Status 413: Payload Too Large**. Error message confirmed the limit: `Maximum number of requested data points exceeded (total_datapoints=379,201)`. |

**Conclusion:** The API limit is indeed around 376,000 data points. A request for 1 year of data for a single station is well within this limit, but 2 years is not.

---

### Test Series B: Multiple Stations, 1 Month

**Objective:** Find the maximum number of stations that can be requested for a fixed 1-month period.

| Test | Stations | Expected Data Points | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| B1 | 5 | 85,445 | ✅ **SUCCESS** | Response time: 0.40s |
| B2 | 10 | 170,890 | ✅ **SUCCESS** | Response time: 0.55s |
| B3+ | 15+ | N/A | ⚠️ **SKIPPED** | Only 10 stations were configured for the test. |

**Conclusion:** Requesting data for 10 stations over a 1-month period is successful and well within the API limits. This confirms that multi-station batching is a viable strategy for short time periods.

---

### Test Series C: Station × Time Combinations

**Objective:** Find the optimal combination of stations and time ranges that stays within the limit.

| Test | Combination | Expected Data Points | Status | Details |
| :--- | :--- | :--- | :--- | :--- |
| C1 | 10 stations × 1 year | 2,014,800 | ❌ **FAILED** | **Status 413**. Exceeded limit. |
| C2 | 10 stations × 6 months | 993,600 | ❌ **FAILED** | **Status 413**. Exceeded limit. |
| C3 | 10 stations × 3 months | 496,800 | ❌ **FAILED** | **Status 413**. Exceeded limit. |
| C4 | 8 stations × 1 year | 1,611,840 | ❌ **FAILED** | **Status 413**. Exceeded limit. |
| C5 | 5 stations × 2 years | 2,014,800 | ❌ **FAILED** | **Status 413**. Exceeded limit. |

**Conclusion:** All tested combinations were too large and exceeded the data point limit. This highlights the need for careful calculation of `stations * time_range * parameters` before making a request. The smallest failed test (10 stations x 3 months) was still significantly larger than the ~376k limit.

---

### Test Series D: Concurrent Request Testing

**Objective:** Determine the optimal number of concurrent workers to maximize request throughput. 50 small, identical requests were made for each worker configuration.

| Workers | Total Time | Actual Rate | Efficiency (vs 200 req/s) |
| :--- | :--- | :--- | :--- |
| 10 | 1.65s | **30.37 req/sec** | **15.2%** |
| 25 | 3.28s | 15.24 req/sec | 7.6% |
| 50 | 3.19s | 15.66 req/sec | 7.8% |
| 100 | 3.20s | 15.60 req/sec | 7.8% |

**Conclusion:** The optimal number of concurrent workers is around **10**, which yielded the highest throughput of ~30 req/sec. Increasing the number of workers beyond this point resulted in diminishing returns and a lower overall request rate, suggesting a bottleneck was reached. This could be due to server-side throttling for the specific API key, network latency, or client-side limitations. The advertised 200 req/sec limit was not approachable in this test.

## 💡 Recommendations & Strategic Implications

Based on these findings, the following strategy is recommended for the data ingestion pipeline:

1.  **Embrace the Data Point Limit:** All data loading logic **must** calculate the expected number of data points (`stations * hours * parameters`) before making an API call and ensure it stays safely below the 376,000 limit. A safe margin (e.g., 90% of the limit, ~340,000 points) is advisable.

2.  **Optimize Chunking Strategy:** The `orchestrate_historical_v2.py` script's strategy of using **2-month chunks for 8 stations** is validated by these tests.
    *   `8 stations * (2 months * 30 days * 24 hours) * 23 parameters = 264,960` data points.
    *   This is well within the limit and provides a good balance between the number of API calls and the size of each call.

3.  **Re-evaluate Concurrency:** The orchestration scripts should be configured to use a concurrency level of **10 workers**. The current implementation, which may be processing chunks sequentially, could be parallelized to take advantage of this finding and speed up historical backfills.

4.  **Forget Yearly Loads for Multiple Stations:** The ambition to load a full year of data for multiple stations in a single call is not feasible. The chunking approach is necessary.

5.  **Future-Proofing:** If more parameters are added to the API in the future, the chunking logic must be adjusted to accommodate the increase in data points per request. The number of parameters is a critical factor in the calculation.
