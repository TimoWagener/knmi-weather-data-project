"""
Configuration for Bronze Raw Ingestion

Simple configuration without external dependencies (no Pydantic).
Reuses existing project configuration where possible.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Get project root (3 levels up: bronze_raw -> data_orchestration -> project_root)
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()

# Load environment variables
load_dotenv(PROJECT_ROOT.parent / ".env")

# API Configuration
EDR_API_KEY = os.getenv("KNMI_EDR_API_KEY")
if not EDR_API_KEY:
    raise ValueError("KNMI_EDR_API_KEY not found in .env file")

EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"
EDR_COLLECTION = "hourly-in-situ-meteorological-observations-validated"

# API Limits (from testing)
API_RATE_LIMIT_PER_SEC = 200
API_QUOTA_PER_HOUR = 1000
MAX_DATA_POINTS_PER_REQUEST = 376000  # Hard limit from API

# Concurrency Settings (from testing - 10 workers is optimal)
MAX_CONCURRENT_STATIONS = 10  # Process 10 stations in parallel

# Data Point Calculation
# Each hour of data for a station = 23 parameters (from API testing)
PARAMETERS_PER_HOUR = 23

# Chunk Settings - 1 YEAR chunks (simple and clean!)
# 365 days × 24 hours × 23 parameters = 201,480 data points (~54% of limit)
CHUNK_SIZE_YEARS = 1
CHUNK_SAFETY_MARGIN = 0.9  # Use 90% of API limit for safety

# Paths
BASE_DATA_DIR = PROJECT_ROOT / "data"
BRONZE_RAW_DIR = BASE_DATA_DIR / "bronze" / "raw" / "edr_api"
LOGS_DIR = PROJECT_ROOT / "logs"
METADATA_DIR = PROJECT_ROOT / "metadata"

# Ensure directories exist
BRONZE_RAW_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Load station configuration from existing metadata
STATIONS_CONFIG_FILE = METADATA_DIR / "stations_config.json"

def load_stations():
    """Load station configuration from metadata"""
    if not STATIONS_CONFIG_FILE.exists():
        raise FileNotFoundError(f"Stations config not found: {STATIONS_CONFIG_FILE}")

    with open(STATIONS_CONFIG_FILE, 'r') as f:
        config = json.load(f)

    return config['stations']

# Station registry
STATIONS = load_stations()

# Get list of station keys for core 10
CORE_10_STATIONS = [
    'hupsel', 'deelen', 'de_bilt', 'schiphol', 'rotterdam',
    'vlissingen', 'maastricht', 'eelde', 'den_helder', 'twenthe'
]

def get_station_id(station_key: str) -> str:
    """Get EDR API ID for a station key"""
    if station_key not in STATIONS:
        raise ValueError(f"Unknown station: {station_key}")
    return STATIONS[station_key]['id']

def get_station_name(station_key: str) -> str:
    """Get display name for a station key"""
    if station_key not in STATIONS:
        raise ValueError(f"Unknown station: {station_key}")
    return STATIONS[station_key]['name']

def calculate_data_points(years: int, stations: int = 1) -> int:
    """
    Calculate expected data points for a request.

    Args:
        years: Number of years of data
        stations: Number of stations (default: 1)

    Returns:
        Estimated data points
    """
    hours_per_year = 365 * 24  # Approximate (ignores leap years)
    return hours_per_year * years * PARAMETERS_PER_HOUR * stations

# Retry Configuration
MAX_RETRIES = 5
RETRY_INITIAL_WAIT = 2  # seconds
RETRY_MAX_WAIT = 30  # seconds
RETRY_MULTIPLIER = 2  # exponential backoff multiplier

# Logging Configuration
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
