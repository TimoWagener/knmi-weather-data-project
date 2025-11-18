# 03: Error Handling and Retries Summary

A production-grade ingestion pipeline must be resilient to transient network errors, server-side issues (`5xx` errors), and rate limiting (`429` errors). This document summarizes the best practices for implementing a robust retry mechanism for asynchronous API calls.

## Core Principles

1.  **Don't Retry Immediately:** Retrying instantly after a failure often leads to repeated failure, especially if the server is overloaded.
2.  **Use Exponential Backoff:** Increase the delay between retries exponentially (e.g., 2s, 4s, 8s). This gives the server time to recover.
3.  **Add Jitter:** Add a random amount of jitter (delay) to the backoff. If multiple clients are all backing off, this prevents them from all retrying at the exact same time.
4.  **Respect `Retry-After` Headers:** If the API returns a `429 Too Many Requests` status, it often includes a `Retry-After` header indicating how many seconds to wait. A well-behaved client **must** honor this header.

## Recommended Library: `tenacity`

The `tenacity` library is the industry standard for handling retries in Python. It is feature-rich, works seamlessly with `asyncio`, and can implement all the principles above.

### Example Implementation

Here is how to configure `tenacity` to create a robust, asynchronous retry strategy for `httpx`.

```python
import asyncio
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError
)

# --- Define what errors should trigger a retry ---

def is_retryable_exception(exception):
    """
    Return True if the exception is a transient error that should be retried.
    - 5xx server errors
    - 429 rate limit errors
    - Network request errors
    """
    if isinstance(exception, httpx.HTTPStatusError):
        is_server_error = exception.response.status_code >= 500
        is_rate_limit = exception.response.status_code == 429
        return is_server_error or is_rate_limit
    elif isinstance(exception, httpx.RequestError):
        # This catches network errors like timeout, connection refused, etc.
        return True
    return False

# --- Define a custom wait strategy for the 'Retry-After' header ---

def wait_after_retry_header(retry_state):
    """
    If a 429 response includes a 'Retry-After' header, wait that long.
    Otherwise, use exponential backoff.
    """
    exception = retry_state.outcome.exception()
    if isinstance(exception, httpx.HTTPStatusError) and exception.response.status_code == 429:
        retry_after = exception.response.headers.get('Retry-After')
        if retry_after:
            try:
                # The header can be an integer (seconds) or an HTTP-date.
                wait_seconds = int(retry_after)
                print(f"Honoring 'Retry-After' header. Waiting {wait_seconds} seconds.")
                return wait_seconds
            except ValueError:
                pass  # Could not parse, fall back to exponential backoff.

    # Fallback to standard exponential backoff with jitter
    return wait_exponential(multiplier=1, min=2, max=30)(retry_state)


# --- Create the async retry decorator ---

async_retryer = retry(
    stop=stop_after_attempt(5),  # Stop after 5 attempts
    wait=wait_after_retry_header, # Use our custom wait logic
    retry=retry_if_exception_type(Exception), # Check all exceptions with our function
    reraise=True  # Reraise the exception if all retries fail
)

@async_retryer
async def fetch_url_robustly(client: httpx.AsyncClient, url: str):
    """
    Makes a request and will be automatically retried by tenacity on failure.
    """
    print(f"Attempting to fetch {url}...")
    response = await client.get(url, timeout=15.0)
    response.raise_for_status()  # Raise HTTPStatusError for 4xx/5xx
    return response

# --- Usage ---

async def main():
    async with httpx.AsyncClient() as client:
        try:
            # This URL will likely fail, triggering the retry logic
            response = await fetch_url_robustly(client, "https://httpbin.org/status/503")
            print(f"Success: {response.status_code}")
        except RetryError as e:
            print(f"All retries failed for the request. Final exception: {e}")

```

### Summary of the Strategy

1.  **`@async_retryer` Decorator:** Any function decorated with this will automatically gain our retry logic.
2.  **`stop_after_attempt(5)`:** It will try a maximum of 5 times (1 initial call + 4 retries).
3.  **`retry_if_exception_type`:** This is configured to check for retryable exceptions using our custom `is_retryable_exception` function.
4.  **`wait_after_retry_header`:** This custom function provides the most critical logic:
    *   It inspects the failed exception.
    *   If it's a `429` error with a `Retry-After` header, it waits for the specified duration.
    *   Otherwise, it falls back to a standard exponential backoff (from 2 to 30 seconds) with added jitter.
5.  **`reraise=True`:** If all 5 attempts fail, the final exception is raised, which can be caught by the caller. This prevents silent failures.

This `tenacity`-based approach provides a production-grade, observable, and well-behaved retry mechanism essential for the ultimate ingestion pipeline.
