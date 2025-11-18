"""
Simple Metadata Tracker for Bronze Raw Layer

Tracks which years have been loaded for each station.
One JSON file per station for easy visibility and debugging.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import get_station_id, get_station_name, PROJECT_ROOT


METADATA_DIR = PROJECT_ROOT / "metadata" / "bronze_raw"
METADATA_DIR.mkdir(parents=True, exist_ok=True)


class StationMetadata:
    """
    Simple metadata tracker for a single station.

    Tracks which years have been successfully loaded.
    Stored as one JSON file per station.
    """

    def __init__(self, station_key: str):
        """
        Initialize metadata for a station.

        Args:
            station_key: Station identifier (e.g., "hupsel")
        """
        self.station_key = station_key
        self.station_id = get_station_id(station_key)
        self.station_name = get_station_name(station_key)
        self.metadata_file = METADATA_DIR / f"{station_key}.json"

        # Load existing metadata or initialize empty
        self._load()

    def _load(self) -> None:
        """Load metadata from file or initialize if doesn't exist"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                data = json.load(f)
                self.years_loaded = data.get('years_loaded', [])

                # Handle both old format (list of ints) and new format (list of dicts)
                if self.years_loaded and isinstance(self.years_loaded[0], int):
                    # Convert old format to new format
                    self.years_loaded = [{"year": year} for year in self.years_loaded]
        else:
            self.years_loaded = []

    def _save(self) -> None:
        """Save metadata to file"""
        # Sort years for readability (if simple list, convert to dict format)
        if self.years_loaded and isinstance(self.years_loaded[0], int):
            # Old format - convert to enhanced format
            self.years_loaded = [{"year": year} for year in sorted(self.years_loaded)]

        # Sort by year
        self.years_loaded.sort(key=lambda x: x.get('year', 0) if isinstance(x, dict) else x)

        # Calculate summary statistics
        total_size_mb = sum(y.get('size_mb', 0) for y in self.years_loaded if isinstance(y, dict))
        years_list = [y.get('year') if isinstance(y, dict) else y for y in self.years_loaded]

        data = {
            "station_key": self.station_key,
            "station_id": self.station_id,
            "station_name": self.station_name,
            "years_loaded": self.years_loaded,
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_years": len(self.years_loaded),
                "total_size_mb": round(total_size_mb, 2),
                "year_range": {
                    "start": min(years_list) if years_list else None,
                    "end": max(years_list) if years_list else None
                }
            }
        }

        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=2)

    def is_year_loaded(self, year: int) -> bool:
        """
        Check if a year is already loaded.

        Args:
            year: Year to check

        Returns:
            True if year is loaded, False otherwise
        """
        # Handle both old and new format
        for item in self.years_loaded:
            if isinstance(item, dict):
                if item.get('year') == year:
                    return True
            elif item == year:
                return True
        return False

    def mark_year_loaded(self, year: int, file_path: str = None, size_mb: float = None) -> None:
        """
        Mark a year as successfully loaded with metadata.

        Args:
            year: Year that was loaded
            file_path: Path to the data file
            size_mb: Size of the file in megabytes
        """
        # Check if already exists
        if self.is_year_loaded(year):
            return

        # Create metadata entry
        entry = {
            "year": year,
            "loaded_at": datetime.utcnow().isoformat() + "Z"
        }

        if file_path:
            entry["file_path"] = str(file_path)

        if size_mb is not None:
            entry["size_mb"] = round(size_mb, 2)

        self.years_loaded.append(entry)
        self._save()

    def mark_years_loaded(self, years: List[int], file_paths: Dict[int, str] = None, sizes_mb: Dict[int, float] = None) -> None:
        """
        Mark multiple years as loaded.

        Args:
            years: List of years that were loaded
            file_paths: Optional dict mapping year to file path
            sizes_mb: Optional dict mapping year to file size in MB
        """
        for year in years:
            if not self.is_year_loaded(year):
                file_path = file_paths.get(year) if file_paths else None
                size_mb = sizes_mb.get(year) if sizes_mb else None
                self.mark_year_loaded(year, file_path, size_mb)
        self._save()

    def get_missing_years(self, start_year: int, end_year: int) -> List[int]:
        """
        Get list of years that are NOT loaded in a range.

        Args:
            start_year: Start of range
            end_year: End of range (inclusive)

        Returns:
            List of years that need to be loaded
        """
        all_years = set(range(start_year, end_year + 1))

        # Extract year numbers from metadata
        loaded_years = set()
        for item in self.years_loaded:
            if isinstance(item, dict):
                loaded_years.add(item.get('year'))
            else:
                loaded_years.add(item)

        missing = list(all_years - loaded_years)
        missing.sort()
        return missing

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of loaded data.

        Returns:
            Dictionary with summary information
        """
        # Extract years and calculate totals
        years_list = []
        total_size_mb = 0

        for item in self.years_loaded:
            if isinstance(item, dict):
                years_list.append(item.get('year'))
                total_size_mb += item.get('size_mb', 0)
            else:
                years_list.append(item)

        return {
            "station_key": self.station_key,
            "station_name": self.station_name,
            "total_years": len(self.years_loaded),
            "total_size_mb": round(total_size_mb, 2),
            "years_loaded": sorted(years_list),
            "year_range": {
                "start": min(years_list) if years_list else None,
                "end": max(years_list) if years_list else None
            }
        }


def get_all_station_summaries() -> Dict[str, Dict[str, Any]]:
    """
    Get summaries for all stations that have metadata.

    Returns:
        Dictionary mapping station_key to summary
    """
    summaries = {}

    for metadata_file in METADATA_DIR.glob("*.json"):
        station_key = metadata_file.stem
        metadata = StationMetadata(station_key)
        summaries[station_key] = metadata.get_summary()

    return summaries


def print_status_summary() -> None:
    """Print a nice summary of all station metadata"""
    summaries = get_all_station_summaries()

    if not summaries:
        print("No metadata found yet.")
        return

    print("=" * 80)
    print("BRONZE RAW - STATION METADATA SUMMARY")
    print("=" * 80)

    total_years_all = 0
    total_size_all = 0

    for station_key, summary in sorted(summaries.items()):
        year_range = summary['year_range']
        start = year_range['start'] if year_range['start'] else 'N/A'
        end = year_range['end'] if year_range['end'] else 'N/A'

        total_years_all += summary['total_years']
        total_size_all += summary['total_size_mb']

        print(f"\n{summary['station_name']:20} ({station_key})")
        print(f"  Years loaded: {summary['total_years']}")
        print(f"  Range: {start} - {end}")
        print(f"  Total size: {summary['total_size_mb']:.2f} MB")

        if summary['total_years'] <= 10:
            # Show individual years if not too many
            print(f"  Years: {summary['years_loaded']}")

    print("\n" + "=" * 80)
    print(f"TOTAL: {len(summaries)} stations, {total_years_all} years, {total_size_all:.2f} MB")
    print("=" * 80)
