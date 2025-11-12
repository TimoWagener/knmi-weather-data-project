"""
Configuration for the weather data pipeline
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Get project root directory (parent of src/)
PROJECT_ROOT = Path(__file__).parent.parent.absolute()

# Load environment variables from parent of project root
load_dotenv(PROJECT_ROOT.parent / ".env")

# API Configuration
EDR_API_KEY = os.getenv("KNMI_EDR_API_KEY")
OPEN_DATA_API_KEY = os.getenv("KNMI_OPEN_DATA_API_KEY")

if not EDR_API_KEY:
    raise ValueError("KNMI_EDR_API_KEY not found in .env file")

# API Endpoints
EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"
EDR_COLLECTION = "hourly-in-situ-meteorological-observations-validated"

# Data paths (relative to project root)
BASE_DATA_DIR = PROJECT_ROOT / "data"
BRONZE_RAW_DIR = BASE_DATA_DIR / "bronze" / "raw"
BRONZE_REFINED_DIR = BASE_DATA_DIR / "bronze" / "refined"
SILVER_DIR = BASE_DATA_DIR / "silver"
GOLD_DIR = BASE_DATA_DIR / "gold"

# Station Configuration
STATIONS = {
    "hupsel": {
        "id": "0-20000-0-06283",
        "name": "Hupsel",
        "description": "Primary weather station near Doetinchem"
    },
    "deelen": {
        "id": "0-20000-0-06275",
        "name": "Deelen Airport",
        "description": "Alternative station near Doetinchem"
    }
}

# Date ranges
DATE_RANGES = {
    "full": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2025-12-31T23:59:59Z"
    },
    "2024": {
        "start": "2024-01-01T00:00:00Z",
        "end": "2024-12-31T23:59:59Z"
    },
    "2025": {
        "start": "2025-01-01T00:00:00Z",
        "end": "2025-12-31T23:59:59Z"
    }
}

# All available parameters from EDR API
# Leave empty to get all parameters, or specify subset
EDR_PARAMETERS = []  # Empty = get all available parameters

# Rate limiting
RATE_LIMIT_REQUESTS = 200  # per second
RATE_LIMIT_QUOTA = 1000    # per hour
