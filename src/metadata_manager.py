"""
Metadata Manager for KNMI Weather Data Pipeline

Handles reading/writing metadata files for orchestration:
- stations_config.json: Station registry
- load_metadata.json: Load history tracking
- pipeline_config.json: Pipeline settings

Usage:
    from metadata_manager import MetadataManager

    mm = MetadataManager()
    stations = mm.get_active_stations()
    mm.update_load_status('hupsel', start='2024-01-01', end='2024-12-31')
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class MetadataManager:
    """Manages metadata files for the orchestration pipeline"""

    def __init__(self, metadata_dir: Optional[Path] = None):
        """Initialize metadata manager

        Args:
            metadata_dir: Path to metadata directory (defaults to project_root/metadata)
        """
        if metadata_dir is None:
            # Auto-detect project root (go up from src/)
            self.project_root = Path(__file__).parent.parent
            self.metadata_dir = self.project_root / "metadata"
        else:
            self.metadata_dir = Path(metadata_dir)

        self.stations_config_path = self.metadata_dir / "stations_config.json"
        self.load_metadata_path = self.metadata_dir / "load_metadata.json"
        self.pipeline_config_path = self.metadata_dir / "pipeline_config.json"

        # Ensure metadata directory exists
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    # ========== Stations Config Methods ==========

    def load_stations_config(self) -> Dict:
        """Load stations configuration"""
        with open(self.stations_config_path, 'r') as f:
            return json.load(f)

    def get_all_stations(self) -> Dict:
        """Get all configured stations"""
        config = self.load_stations_config()
        return config.get('stations', {})

    def get_active_stations(self) -> Dict:
        """Get only active stations"""
        all_stations = self.get_all_stations()
        return {k: v for k, v in all_stations.items() if v.get('active', False)}

    def get_station_group(self, group_name: str) -> List[str]:
        """Get list of station keys in a group

        Args:
            group_name: Name of station group (e.g., 'core_10', 'coastal')

        Returns:
            List of station keys
        """
        config = self.load_stations_config()
        return config.get('station_groups', {}).get(group_name, [])

    def get_station_info(self, station_key: str) -> Optional[Dict]:
        """Get detailed information for a specific station

        Args:
            station_key: Station identifier (e.g., 'hupsel')

        Returns:
            Station info dict or None if not found
        """
        all_stations = self.get_all_stations()
        return all_stations.get(station_key)

    # ========== Load Metadata Methods ==========

    def load_load_metadata(self) -> Dict:
        """Load load metadata (history tracking)"""
        with open(self.load_metadata_path, 'r') as f:
            return json.load(f)

    def save_load_metadata(self, metadata: Dict):
        """Save load metadata

        Args:
            metadata: Complete metadata dictionary to save
        """
        metadata['last_updated'] = datetime.now(timezone.utc).isoformat()
        with open(self.load_metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        logger.info(f"Saved load metadata to {self.load_metadata_path}")

    def get_station_status(self, station_key: str) -> Dict:
        """Get load status for a specific station

        Args:
            station_key: Station identifier

        Returns:
            Station status dict from load_metadata
        """
        metadata = self.load_load_metadata()
        return metadata.get('stations', {}).get(station_key, {})

    def get_next_load_date(self, station_key: str) -> Optional[str]:
        """Get the next date to load for a station

        Args:
            station_key: Station identifier

        Returns:
            ISO format date string or None
        """
        status = self.get_station_status(station_key)
        return status.get('next_update_from')

    def get_loaded_ranges(self, station_key: str) -> List[Dict]:
        """Get all loaded date ranges for a station

        Args:
            station_key: Station identifier

        Returns:
            List of loaded range dicts
        """
        status = self.get_station_status(station_key)
        return status.get('loaded_ranges', [])

    def update_load_status(
        self,
        station_key: str,
        start: str,
        end: str,
        records: int,
        layers: List[str],
        quality_metrics: Optional[Dict] = None
    ):
        """Update load metadata after successful load

        Args:
            station_key: Station identifier
            start: Start date (ISO format)
            end: End date (ISO format)
            records: Number of records loaded
            layers: List of layers processed (e.g., ['bronze_raw', 'silver'])
            quality_metrics: Optional quality metrics dict
        """
        metadata = self.load_load_metadata()

        # Ensure station exists in metadata
        if station_key not in metadata['stations']:
            metadata['stations'][station_key] = {
                'status': 'in_progress',
                'loaded_ranges': [],
                'gaps': [],
                'next_update_from': start,
                'historical_complete': False,
                'target_start_date': '2000-01-01T00:00:00Z'
            }

        # Add new loaded range
        new_range = {
            'start': start,
            'end': end,
            'loaded_at': datetime.now(timezone.utc).isoformat(),
            'records': records,
            'layers': layers
        }

        if quality_metrics:
            new_range['data_quality'] = quality_metrics

        metadata['stations'][station_key]['loaded_ranges'].append(new_range)

        # Update next load date (day after end)
        from datetime import datetime as dt, timedelta
        end_dt = dt.fromisoformat(end.replace('Z', '+00:00'))
        next_dt = end_dt + timedelta(hours=1)
        metadata['stations'][station_key]['next_update_from'] = next_dt.isoformat()

        # Update status
        metadata['stations'][station_key]['status'] = 'in_progress'

        # Update pipeline status
        metadata['pipeline_status']['total_records_loaded'] = sum(
            r['records']
            for s in metadata['stations'].values()
            for r in s.get('loaded_ranges', [])
        )

        active_stations = len([
            s for s in metadata['stations'].values()
            if s.get('loaded_ranges')
        ])
        metadata['pipeline_status']['total_stations_active'] = active_stations

        self.save_load_metadata(metadata)
        logger.info(f"Updated load status for {station_key}: {start} to {end} ({records} records)")

    def mark_station_complete(self, station_key: str):
        """Mark a station as having complete historical data

        Args:
            station_key: Station identifier
        """
        metadata = self.load_load_metadata()
        if station_key in metadata['stations']:
            metadata['stations'][station_key]['status'] = 'complete'
            metadata['stations'][station_key]['historical_complete'] = True
            self.save_load_metadata(metadata)
            logger.info(f"Marked station {station_key} as complete")

    # ========== Pipeline Config Methods ==========

    def load_pipeline_config(self) -> Dict:
        """Load pipeline configuration"""
        with open(self.pipeline_config_path, 'r') as f:
            return json.load(f)

    def get_config_value(self, *keys) -> Any:
        """Get a configuration value by nested keys

        Args:
            *keys: Nested keys (e.g., 'orchestration', 'parallelization', 'max_concurrent_requests')

        Returns:
            Configuration value
        """
        config = self.load_pipeline_config()
        value = config
        for key in keys:
            value = value.get(key, {})
        return value

    def get_max_concurrent_requests(self) -> int:
        """Get max concurrent requests setting"""
        return self.get_config_value('orchestration', 'parallelization', 'max_concurrent_requests')

    def get_max_concurrent_stations(self) -> int:
        """Get max concurrent stations setting"""
        return self.get_config_value('orchestration', 'parallelization', 'max_concurrent_stations')

    def get_chunk_size_months(self) -> int:
        """Get chunk size in months"""
        return self.get_config_value('orchestration', 'parallelization', 'chunk_size_months')

    def get_api_rate_limit(self, limit_type: str = 'requests_per_hour') -> int:
        """Get API rate limit

        Args:
            limit_type: 'requests_per_second' or 'requests_per_hour'

        Returns:
            Rate limit value
        """
        return self.get_config_value('api', 'rate_limits', limit_type)

    # ========== Utility Methods ==========

    def get_stations_needing_load(self, group_name: str = 'core_10') -> List[str]:
        """Get list of stations that need historical loading

        Args:
            group_name: Station group to check

        Returns:
            List of station keys that need loading
        """
        stations = self.get_station_group(group_name)
        metadata = self.load_load_metadata()

        needing_load = []
        for station_key in stations:
            status = metadata.get('stations', {}).get(station_key, {})
            if not status.get('historical_complete', False):
                needing_load.append(station_key)

        return needing_load

    def print_status_summary(self):
        """Print a summary of current load status"""
        metadata = self.load_load_metadata()
        config = self.load_stations_config()

        print("\n" + "="*80)
        print("KNMI WEATHER DATA PIPELINE - STATUS SUMMARY")
        print("="*80)

        # Pipeline status
        pipeline_status = metadata['pipeline_status']
        print(f"\nTotal Records: {pipeline_status['total_records_loaded']:,}")
        print(f"Active Stations: {pipeline_status['total_stations_active']}")
        print(f"Data Size: {pipeline_status['data_size_mb']:.1f} MB")

        # Station status
        print("\nStation Status:")
        print("-"*80)
        for station_key, status in metadata['stations'].items():
            station_info = config['stations'].get(station_key, {})
            name = station_info.get('name', station_key)
            status_str = status.get('status', 'unknown')
            ranges = status.get('loaded_ranges', [])
            total_records = sum(r.get('records', 0) for r in ranges)

            complete = "[X]" if status.get('historical_complete') else "[ ]"
            print(f"  {complete} {name:15s} | {status_str:12s} | {total_records:8,} records | {len(ranges)} ranges")

        print("="*80 + "\n")


# Example usage
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)

    # Create metadata manager
    mm = MetadataManager()

    # Print status
    mm.print_status_summary()

    # Get active stations
    print("Active stations:")
    for key, info in mm.get_active_stations().items():
        print(f"  - {key}: {info['name']} ({info['region']})")

    # Get stations in core_10 group
    print("\nCore 10 stations:")
    core_10 = mm.get_station_group('core_10')
    print(f"  {', '.join(core_10)}")

    # Get stations needing load
    print("\nStations needing historical load:")
    needing_load = mm.get_stations_needing_load('core_10')
    print(f"  {', '.join(needing_load)}")
