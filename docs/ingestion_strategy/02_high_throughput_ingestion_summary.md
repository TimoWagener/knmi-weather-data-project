# 02: High-Throughput Ingestion Summary

This document summarizes the best approach for making a high volume of concurrent API calls to maximize data ingestion speed, based on the research in `ASYNC_API_CALL_BEST_PRACTICES.md`.

## Core Principles for Fast Ingestion

The goal is to parallelize requests as much as possible without overwhelming the API server or our own client application. The optimal approach combines three core Python `asyncio` concepts.

1.  **Use a Persistent Client Session (`httpx.AsyncClient`)**
    *   **What it is:** A single, shared client object that manages a pool of underlying TCP connections.
    *   **Why it's critical:** Creating a new connection for every request is extremely slow due to the overhead of the TCP handshake. Reusing connections from a pool is dramatically faster and more efficient.
    *   **Implementation:** Create the `httpx.AsyncClient` within a single `async with` block that encompasses all API calls.

2.  **Control Concurrency with a Semaphore (`asyncio.Semaphore`)**
    *   **What it is:** A concurrency primitive that allows only a fixed number of coroutines to proceed at any given time.
    *   **Why it's critical:** It prevents the client from launching hundreds of requests at once, which would trigger rate limits or cause failures. It acts as a gate, ensuring that while we may have 200 tasks *ready* to run, only a controlled number (e.g., 15) are actively making network requests.
    *   **Implementation:** Initialize a semaphore (`sem = asyncio.Semaphore(15)`) and wrap the core API call logic within an `async with sem:` block.

3.  **Orchestrate with a Gather Operation (`asyncio.gather`)**
    *   **What it is:** A function that takes a list of awaitables (e.g., our API call tasks) and runs them concurrently.
    *   **Why it's critical:** It's the mechanism that starts all the tasks. When combined with a semaphore, `gather` effectively launches all tasks, but the semaphore ensures they execute in a controlled, parallel fashion.

## The "Worker" Pattern

The combination of these principles leads to the "Worker Pattern":

```python
import asyncio
import httpx

MAX_CONCURRENT_REQUESTS = 15

async def api_worker(client, semaphore, url):
    """A worker that fetches one URL, respecting the semaphore."""
    async with semaphore:
        # Only 15 workers can be in this block at a time.
        print(f"Fetching {url}...")
        try:
            await client.get(url)
            print(f"Success: {url}")
        except Exception as e:
            print(f"Error fetching {url}: {e}")

async def main():
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with httpx.AsyncClient() as client:
        # Create all tasks, but they won't all run at once.
        tasks = [api_worker(client, semaphore, url) for url in list_of_200_urls]
        await asyncio.gather(*tasks)
```

**Conclusion:** The fastest and safest way to ingest data is to use this semaphore-controlled worker pattern. It provides the highest possible throughput while respecting a hard concurrency limit, giving us a tunable knob (`MAX_CONCURRENT_REQUESTS`) to optimize performance against API limits.
