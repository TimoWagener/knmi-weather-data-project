# 04: Atomic Writes for Data Integrity Summary

In a data lakehouse, data integrity is paramount. A common source of corruption is a process that fails midway through writing a file, leaving a partial, unreadable file in the data lake. **Atomic writes** are the industry-standard pattern to prevent this.

## The Problem: Partial Writes

Consider an ingestion script that writes a large JSON or Parquet file directly to its final destination: `data/bronze/raw/station_id=123/data.json`.

If the script is terminated for any reason (crash, server reboot, `Ctrl+C`) while only 60% of the file has been written, that `data.json` file is now corrupt. Downstream processes that try to read it will fail, potentially halting the entire data pipeline.

## The Solution: The "Write-and-Rename" Pattern

The "write-and-rename" pattern guarantees that the final destination path will only ever contain complete files. The process is simple:

1.  **Write to a Temporary File:** Write the entire content to a temporary file in the *same filesystem/mount* as the final destination. The temporary file should have a different name (e.g., `data.json.tmp` or `data.json.{uuid}`).
2.  **Verify (Optional but Recommended):** After writing, you can optionally re-read the temporary file to verify its integrity.
3.  **Move (Rename) to Final Destination:** Once the write is complete and verified, perform a `rename` operation to move the temporary file to its final path.

**Why this works:** A `rename` operation within the same filesystem is an **atomic metadata operation**. It's not a slow file copy; it's an instantaneous change to the filesystem's pointers. The operating system guarantees that this operation will either complete successfully or not happen at all. It will never result in a partial file at the destination.

### Python Implementation

Here is a practical implementation of this pattern.

```python
import os
import json
import uuid
from pathlib import Path

def atomic_write_json(data: dict, final_path: str):
    """
    Atomically writes JSON data to a final path.
    """
    # Ensure the final directory exists
    final_path_obj = Path(final_path)
    final_dir = final_path_obj.parent
    final_dir.mkdir(parents=True, exist_ok=True)

    # 1. Define a temporary path in the same directory
    # Using a UUID ensures the temp file is unique and avoids conflicts
    # if multiple processes are writing to the same directory.
    temp_file_path = final_dir / f"{final_path_obj.name}.{uuid.uuid4()}.tmp"

    try:
        # 2. Write to the temporary file
        with open(temp_file_path, 'w') as f:
            json.dump(data, f)

        # 3. Rename the temporary file to the final path. This is the atomic operation.
        os.rename(temp_file_path, final_path_obj)
        print(f"Successfully wrote to {final_path_obj}")

    except Exception as e:
        print(f"An error occurred: {e}")
        # 4. Clean up the temporary file on failure
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        raise # Reraise the exception

# --- Usage ---
# final_destination = "data/bronze/raw/station=123/year=2024/month=10/data.json"
# my_data = {"key": "value"}
# atomic_write_json(my_data, final_destination)
```

### Considerations for Different Libraries

*   **Pandas & PyArrow (for Parquet):** Many modern data libraries have built-in support for this pattern or can be easily integrated with it. When using `pandas.DataFrame.to_parquet`, you can write to a temporary file path first and then perform the `os.rename`.
    ```python
    import pandas as pd

    # df = pd.DataFrame(...)
    # temp_path = "data.parquet.tmp"
    # final_path = "data.parquet"
    #
    # df.to_parquet(temp_path)
    # os.rename(temp_path, final_path)
    ```
*   **Cloud Storage (S3, GCS, etc.):** This pattern is even more critical in cloud storage. Most cloud storage libraries do not guarantee atomicity for standard uploads. The equivalent pattern is to upload the file to a temporary path in the bucket and then use the cloud provider's `copy` or `rename` API (which is typically atomic) to move it to its final destination. Libraries like `s3fs` often handle this for you if used correctly.

**Conclusion:** The "write-and-rename" pattern is a non-negotiable best practice for any data ingestion pipeline writing to a data lake. It is the simplest and most effective way to guarantee data integrity and prevent the pollution of the lake with corrupt, partial files.
