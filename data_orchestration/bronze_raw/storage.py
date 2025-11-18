"""
Atomic Storage Handler

Implements the "write-and-rename" pattern for data integrity.
Ensures that only complete, valid files are ever present in the data lake.
"""
import os
import json
import uuid
from pathlib import Path
from typing import Dict, Any

def atomic_write_json(data: Dict[str, Any], final_path: Path) -> None:
    """
    Atomically write JSON data to a file using write-and-rename pattern.

    This ensures that the final destination path will only ever contain
    complete files. If the process crashes mid-write, the partial file
    will be in a temporary location and won't corrupt the data lake.

    Args:
        data: Dictionary to write as JSON
        final_path: Final destination path for the file

    Raises:
        Exception: If write fails, temp file is cleaned up automatically
    """
    # Convert to Path object if string
    final_path = Path(final_path)

    # Ensure parent directory exists
    final_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in same directory (must be same filesystem for atomic rename)
    # Using UUID ensures uniqueness if multiple processes writing to same directory
    temp_path = final_path.parent / f"{final_path.name}.{uuid.uuid4().hex[:8]}.tmp"

    try:
        # Write to temporary file
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        # Atomic rename - this is the critical operation
        # On POSIX systems, rename() is atomic
        # On Windows, os.replace() is atomic (Python 3.3+)
        os.replace(temp_path, final_path)

    except Exception as e:
        # Clean up temporary file if write failed
        if temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass  # Ignore cleanup errors
        raise  # Re-raise the original exception


def get_output_path(station_id: str, year: int, base_dir: Path = None) -> Path:
    """
    Generate the output path for a bronze raw data file.

    Pattern: data/bronze/raw/edr_api/station_id={id}/year={year}/data.json

    Args:
        station_id: EDR API station ID (e.g., "0-20000-0-06283")
        year: Year of data (e.g., 2024)
        base_dir: Base directory for bronze raw data (default: from config)

    Returns:
        Path object for the output file
    """
    if base_dir is None:
        from .config import BRONZE_RAW_DIR
        base_dir = BRONZE_RAW_DIR

    # Create partitioned path: station_id={id}/year={year}/data.json
    output_path = base_dir / f"station_id={station_id}" / f"year={year}" / "data.json"

    return output_path


def file_exists(station_id: str, year: int, base_dir: Path = None) -> bool:
    """
    Check if a bronze raw file already exists for a given station and year.

    Args:
        station_id: EDR API station ID
        year: Year of data
        base_dir: Base directory for bronze raw data (default: from config)

    Returns:
        True if file exists, False otherwise
    """
    path = get_output_path(station_id, year, base_dir)
    return path.exists()


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """
    Load a JSON file safely.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)
