# Best Practices for High-Volume Asynchronous API Calls

When building applications that interact with external APIs, it's common to need to make a large number of requests concurrently. Doing this efficiently and safely requires careful management of concurrency and resources to avoid overwhelming the server or your own application, and to respect API rate limits.

This document outlines the best practices for making up to 200 (or more) concurrent API calls in Python using `asyncio` and `httpx`.

## 1. Use a Persistent Client Session

Creating a new connection for every single request is highly inefficient. It adds significant overhead due to the TCP handshake process. The best practice is to use a single client session (`httpx.AsyncClient` or `aiohttp.ClientSession`) for all requests made to the same host. The session manager handles connection pooling and reuse, dramatically improving performance.

**Bad:** Creating a new client for each request.
```python
# Inefficient - Don't do this!
async def fetch(url):
    async with httpx.AsyncClient() as client:
        return await client.get(url)
```

**Good:** Passing a shared client instance.
```python
# Efficient - Do this!
async def fetch(client, url):
    return await client.get(url)

async def main():
    async with httpx.AsyncClient() as client:
        tasks = [fetch(client, url) for url in urls]
        await asyncio.gather(*tasks)
```

## 2. Control Concurrency with `asyncio.Semaphore`

Launching hundreds of requests simultaneously without any control can lead to several problems:
-   **Hitting API Rate Limits:** Most APIs have a limit on concurrent connections or requests per second.
-   **Server Overload:** You could overwhelm the server, leading to failed requests (`5xx` errors).
-   **Client-Side Resource Exhaustion:** Your application might run out of file descriptors or memory.

An `asyncio.Semaphore` is the perfect tool to control concurrency. It's a counter that limits how many coroutines can enter a specific block of code at the same time. If the counter is at its limit, other coroutines will wait until a running one finishes and releases the semaphore.

This allows you to have hundreds of "pending" tasks, but only a controlled number (e.g., 15) of them making actual network requests at any given moment.

## 3. Putting It All Together: The Worker Pattern

Combining a persistent client with a semaphore gives us a robust pattern for managing high-volume requests.

Here is a complete, practical example of how to make 200 API calls with a concurrency limit of 15.

```python
import asyncio
import httpx
import time
from collections import deque

# --- Configuration ---
# List of 200 example URLs to fetch
URLS_TO_FETCH = [f"https://httpbin.org/delay/1" for _ in range(200)]

# Maximum number of concurrent requests allowed
MAX_CONCURRENT_REQUESTS = 15

def api_worker(
    client: httpx.AsyncClient,
    semaphore: asyncio.Semaphore,
    url: str,
    results_deque: deque
):
    """
    A worker that fetches a single URL.

    It acquires the semaphore before making the request to limit concurrency.
    """
    print(f"WAITING: {url}")
    async with semaphore:
        print(f"ACTIVE: {url} (Concurrent tasks: {MAX_CONCURRENT_REQUESTS - semaphore._value}/{MAX_CONCURRENT_REQUESTS})")
        try:
            response = await client.get(url, timeout=30.0)
            response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
            results_deque.append({"url": url, "status": response.status_code})
            print(f"SUCCESS: {url} -> {response.status_code}")
        except httpx.HTTPStatusError as e:
            results_deque.append({"url": url, "status": "ERROR", "detail": str(e)})
            print(f"ERROR: {url} -> {e.response.status_code}")
        except httpx.RequestError as e:
            results_deque.append({"url": url, "status": "ERROR", "detail": str(e)})
            print(f"ERROR: {url} -> Request Failed")

async def main():
    """
    Orchestrates the fetching of all URLs using the worker pattern.
    """
    # The semaphore will ensure that only MAX_CONCURRENT_REQUESTS are active at once.
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    # A thread-safe deque to store results as they come in
    results_deque = deque()

    start_time = time.time()

    # Use a single client session for all requests
    async with httpx.AsyncClient() as client:
        # Create a list of tasks (coroutines) to be executed
        tasks = [
            api_worker(client, semaphore, url, results_deque)
            for url in URLS_TO_FETCH
        ]
        
        # Run all tasks concurrently
        await asyncio.gather(*tasks)

    end_time = time.time()
    
    print("\n" + "="*50)
    print(f"Completed {len(URLS_TO_FETCH)} requests in {end_time - start_time:.2f} seconds.")
    print(f"Concurrency limit was set to {MAX_CONCURRENT_REQUESTS}.")
    print(f"Total results collected: {len(results_deque)}")
    print("="*50)


if __name__ == "__main__":
    asyncio.run(main())

```

### How the Example Works

1.  **`MAX_CONCURRENT_REQUESTS`**: This is our main control knob. We set it to 15.
2.  **`asyncio.Semaphore(15)`**: We create a semaphore that will only allow 15 "permits" to be acquired at once.
3.  **`api_worker`**: This function represents a single unit of work. Crucially, it starts with `async with semaphore:`, which attempts to acquire a permit. If all 15 are in use, the coroutine will pause here until one is released.
4.  **`main`**:
    *   It creates the semaphore and the shared `httpx.AsyncClient`.
    *   It creates a list of 200 `api_worker` tasks. At this point, no requests have been made.
    *   `asyncio.gather(*tasks)` starts running all 200 tasks concurrently. However, because of the semaphore, only the first 15 tasks will be able to acquire a permit and proceed to make a network request. The other 185 will be waiting at the `async with semaphore:` line.
    *   As soon as one of the first 15 tasks completes its request and exits the `with` block, it releases its permit, and one of the waiting tasks immediately acquires it and starts its own request.
    *   This process continues until all 200 tasks have completed.

## 4. Advanced: Error Handling and Retries

For production-grade applications, you should also implement a retry mechanism for failed requests, especially for transient network errors or rate-limit responses (HTTP 429).

Using a library like `tenacity` or `backoff` can simplify this. You can wrap your request logic in a decorator that automatically retries with exponential backoff.

**Example with `tenacity`:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3), 
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
async def fetch_with_retry(client, url):
    response = await client.get(url)
    response.raise_for_status()
    return response
```

## Summary of Best Practices

1.  **Use a Single `httpx.AsyncClient`**: Manage connections efficiently by using one client instance for all requests.
2.  **Control Concurrency with `asyncio.Semaphore`**: Strictly limit the number of in-flight requests to respect API limits and prevent system overload.
3.  **Use the Worker Pattern**: Create a worker task that encapsulates fetching a single resource, including semaphore logic.
4.  **Orchestrate with `asyncio.gather`**: Launch all your worker tasks and let the semaphore handle the queuing and execution flow.
5.  **Implement Retries**: Use libraries like `tenacity` to handle transient errors gracefully with exponential backoff.
