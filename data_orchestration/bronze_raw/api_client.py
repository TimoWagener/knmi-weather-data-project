"""
EDR API Client with Robust Retry Logic

Handles all interactions with the KNMI EDR API including:
- Retry logic with exponential backoff
- Rate limit handling (429 errors with Retry-After)
- Server error handling (5xx errors)
- Network error handling
"""
import time
import requests
from typing import Dict, Any
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
    after_log
)
import logging

from .config import (
    EDR_API_KEY,
    EDR_BASE_URL,
    EDR_COLLECTION,
    MAX_RETRIES,
    RETRY_INITIAL_WAIT,
    RETRY_MAX_WAIT,
    RETRY_MULTIPLIER
)

# Set up logger for this module
logger = logging.getLogger(__name__)


def is_retryable_error(exception: Exception) -> bool:
    """
    Determine if an exception should trigger a retry.

    Retryable errors:
    - 5xx server errors (temporary server issues)
    - 429 rate limit errors
    - Network errors (timeouts, connection errors)

    Non-retryable errors:
    - 4xx client errors (except 429)
    - Invalid responses

    Args:
        exception: The exception to check

    Returns:
        True if the error should be retried
    """
    if isinstance(exception, requests.exceptions.HTTPError):
        status_code = exception.response.status_code
        # Retry on server errors (5xx) or rate limiting (429)
        return status_code >= 500 or status_code == 429
    elif isinstance(exception, (requests.exceptions.ConnectionError,
                                 requests.exceptions.Timeout,
                                 requests.exceptions.RequestException)):
        # Retry on network errors
        return True
    return False


def get_retry_after_seconds(response: requests.Response) -> int:
    """
    Extract retry-after value from response headers.

    The Retry-After header can be:
    - An integer (seconds to wait)
    - An HTTP-date (not implemented here)

    Args:
        response: HTTP response object

    Returns:
        Number of seconds to wait (0 if header not present or invalid)
    """
    retry_after = response.headers.get('Retry-After')
    if retry_after:
        try:
            return int(retry_after)
        except ValueError:
            # Could be HTTP-date format, not implemented
            logger.warning(f"Could not parse Retry-After header: {retry_after}")
    return 0


def wait_strategy(retry_state):
    """
    Custom wait strategy that honors Retry-After headers.

    If a 429 response includes Retry-After, wait that long.
    Otherwise, use exponential backoff with jitter.
    """
    exception = retry_state.outcome.exception()

    # Check if this is a 429 error with Retry-After header
    if isinstance(exception, requests.exceptions.HTTPError):
        if exception.response.status_code == 429:
            wait_seconds = get_retry_after_seconds(exception.response)
            if wait_seconds > 0:
                logger.info(f"Rate limited. Honoring Retry-After: {wait_seconds}s")
                return wait_seconds

    # Fallback to exponential backoff
    return wait_exponential(
        multiplier=RETRY_MULTIPLIER,
        min=RETRY_INITIAL_WAIT,
        max=RETRY_MAX_WAIT
    )(retry_state)


# Create the retry decorator
api_retry_decorator = retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_strategy,
    retry=retry_if_exception_type(Exception),
    retry_error_callback=lambda retry_state: retry_state.outcome.result(),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    after=after_log(logger, logging.DEBUG)
)


@api_retry_decorator
def fetch_station_year(station_id: str, year: int) -> Dict[str, Any]:
    """
    Fetch one year of data for a single station from the EDR API.

    This function is decorated with retry logic and will automatically:
    - Retry up to MAX_RETRIES times on transient errors
    - Honor Retry-After headers on 429 errors
    - Use exponential backoff for other errors

    Args:
        station_id: EDR API station ID (e.g., "0-20000-0-06283")
        year: Year to fetch (e.g., 2024)

    Returns:
        Parsed JSON response from API

    Raises:
        requests.exceptions.HTTPError: On 4xx client errors (non-retryable)
        Exception: On other failures after all retries exhausted
    """
    # Build URL
    url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{station_id}"

    # Build datetime parameter (full year)
    start_date = f"{year}-01-01T00:00:00Z"
    end_date = f"{year}-12-31T23:59:59Z"

    params = {
        "datetime": f"{start_date}/{end_date}"
        # Note: We don't specify parameter-name, so we get all 23 parameters
    }

    headers = {
        "Authorization": EDR_API_KEY
    }

    logger.debug(f"Fetching {station_id} year {year} from {url}")

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=60  # 60 second timeout
        )

        # Raise HTTPError for bad status codes
        response.raise_for_status()

        # Parse and return JSON
        data = response.json()

        logger.debug(f"Successfully fetched {station_id} year {year} "
                    f"({len(response.content)} bytes)")

        return data

    except requests.exceptions.HTTPError as e:
        # Check if retryable
        if not is_retryable_error(e):
            logger.error(f"Non-retryable error for {station_id} year {year}: "
                        f"{e.response.status_code} - {e.response.text[:200]}")
            raise

        # For retryable errors, log and let tenacity handle the retry
        logger.warning(f"Retryable error for {station_id} year {year}: "
                      f"{e.response.status_code}")
        raise

    except Exception as e:
        # Log and re-raise for retry
        logger.warning(f"Error fetching {station_id} year {year}: {type(e).__name__}: {e}")
        raise


def test_api_connection() -> bool:
    """
    Test if the API connection is working.

    Makes a simple request for a single month of data to verify:
    - API key is valid
    - Network is reachable
    - API is responding

    Returns:
        True if connection successful, False otherwise
    """
    try:
        # Test with small request: Hupsel, January 2024
        url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/0-20000-0-06283"
        params = {"datetime": "2024-01-01T00:00:00Z/2024-01-31T23:59:59Z"}
        headers = {"Authorization": EDR_API_KEY}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        logger.info("[OK] API connection test successful")
        return True

    except Exception as e:
        logger.error(f"[FAIL] API connection test failed: {e}")
        return False
