# 05: Structured Logging Summary

For automated data pipelines, logs are not just for humans to read in real-time; they are a critical source of data for monitoring, alerting, and debugging. **Structured logging** is the practice of writing logs in a machine-readable format like JSON, which makes them dramatically easier to parse, query, and visualize.

## The Problem: Unstructured Text Logs

A traditional text log is easy for a human to read but difficult for a machine to parse reliably.

**Unstructured Log:**
```
INFO:2025-11-18 10:30:15,123:root:API call to https://api.knmi.nl/ a success. Status: 200. Latency: 1.23s.
ERROR:2025-11-18 10:30:16,456:root:API call to https://api.knmi.nl/ failed. Status: 502.
```
To find all failed requests or calculate the average latency, you would need to write complex and brittle regular expressions.

## The Solution: JSON Logs

A structured JSON log contains the same information but as key-value pairs.

**Structured (JSON) Log:**
```json
{"timestamp": "2025-11-18 10:30:15.123", "level": "INFO", "name": "root", "message": "API call successful", "extra": {"url": "https://api.knmi.nl/", "status_code": 200, "latency_seconds": 1.23}}
{"timestamp": "2025-11-18 10:30:16.456", "level": "ERROR", "name": "root", "message": "API call failed", "extra": {"url": "https://api.knmi.nl/", "status_code": 502, "latency_seconds": 2.15}}
```
This format is trivial to ingest into logging platforms (like Datadog, Splunk, ELK Stack) or query with tools like `jq`. You can easily filter for `level == "ERROR"` or calculate `avg(extra.latency_seconds)`.

## Recommended Library: `python-json-logger`

While you can build a custom JSON formatter for Python's standard `logging` library, the `python-json-logger` library is a popular, well-maintained, and easy-to-use solution.

### Example Implementation

First, install the library: `pip install python-json-logger`

Then, configure your logger to use the JSON formatter.

```python
import logging
from pythonjsonlogger import jsonlogger
import sys

def get_json_logger(name: str, level=logging.INFO):
    """
    Returns a logger configured to output structured JSON logs.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Prevent log messages from being duplicated by the root logger
    logger.propagate = False

    # Use a stream handler to output to stdout
    handler = logging.StreamHandler(sys.stdout)

    # Define the format of the JSON logs
    # These are some standard fields that are useful to have.
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        rename_fields={
            'asctime': 'timestamp',
            'levelname': 'level'
        }
    )

    handler.setFormatter(formatter)
    
    # Avoid adding duplicate handlers
    if not logger.handlers:
        logger.addHandler(handler)
        
    return logger

# --- Usage ---

# Get a logger for our ingestion module
ingestion_logger = get_json_logger("bronze_ingestion")

def some_api_function():
    # Use the 'extra' dictionary to add custom, structured context
    extra_context = {
        "url": "https://api.knmi.nl/data",
        "request_id": "xyz-123",
        "attempt": 1
    }
    ingestion_logger.info(
        "Starting API call",
        extra=extra_context
    )

    try:
        # ... make API call ...
        latency = 1.23
        status_code = 200
        extra_context.update({
            "latency_seconds": latency,
            "status_code": status_code
        })
        ingestion_logger.info(
            "API call successful",
            extra=extra_context
        )
    except Exception as e:
        extra_context.update({"error": str(e)})
        ingestion_logger.error(
            "API call failed",
            extra=extra_context
        )

# some_api_function()
```

### Best Practices for Structured Logging

1.  **Log in JSON Format:** Use a library like `python-json-logger` to make this easy.
2.  **Use the `extra` Dictionary:** This is the standard way to add custom, structured fields to your log records without cluttering the main log message.
3.  **Standardize Your Fields:** Decide on a consistent set of field names (`latency_seconds`, `request_id`, `status_code`, etc.) and use them across your application.
4.  **Don't Embed Variables in the Message:**
    *   **Bad:** `logger.info(f"Request to {url} failed with status {code}")`
    *   **Good:** `logger.info("Request failed", extra={"url": url, "status_code": code})`
    The "good" approach allows you to easily group all "Request failed" messages, regardless of the URL or status code.
5.  **Output to `stdout`:** In modern applications (especially containerized ones), it's best practice to log to standard output (`stdout`). The container orchestration system (like Docker or Kubernetes) is then responsible for collecting these logs and forwarding them to a central logging platform.

By adopting structured logging, you transform your logs from simple text into a powerful, queryable dataset that is invaluable for operating and debugging your data pipeline.
