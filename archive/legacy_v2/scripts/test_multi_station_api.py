"""
Test Multi-Station EDR API Query

Tests the EDR API's ability to query multiple stations in a single request
and analyzes the response structure.

Usage:
    python scripts/test_multi_station_api.py
"""

import sys
from pathlib import Path
import json
import requests
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import EDR_API_KEY, EDR_BASE_URL, EDR_COLLECTION, STATIONS

def test_multi_station_query():
    """Test querying multiple stations in a single API call"""

    print("="*80)
    print("TESTING MULTI-STATION API QUERY")
    print("="*80)

    # Test with 2 existing stations for 1 month
    test_stations = ["hupsel", "deelen"]
    station_ids = [STATIONS[s]["id"] for s in test_stations]

    # Short test period: January 2024 (1 month)
    start_date = "2024-01-01T00:00:00Z"
    end_date = "2024-01-31T23:59:59Z"

    print(f"\nTest Configuration:")
    print(f"  Stations: {', '.join(test_stations)}")
    print(f"  IDs: {', '.join(station_ids)}")
    print(f"  Period: {start_date} to {end_date}")
    print(f"  Expected data points: ~2 stations × 744 hours × 23 params = ~34,224 points")

    # Construct multi-station query
    location_param = ",".join(station_ids)
    datetime_range = f"{start_date}/{end_date}"

    params = {
        "datetime": datetime_range
    }

    url = f"{EDR_BASE_URL}/collections/{EDR_COLLECTION}/locations/{location_param}"

    print(f"\nAPI Request:")
    print(f"  URL: {url}")
    print(f"  Params: {params}")

    headers = {"Authorization": EDR_API_KEY}

    # Make request
    print(f"\nSending request...")
    try:
        response = requests.get(url, params=params, headers=headers, timeout=60)
        response.raise_for_status()

        print(f"  [OK] Response received!")
        print(f"  Status: {response.status_code}")
        print(f"  Size: {len(response.content):,} bytes")
        print(f"  Content-Type: {response.headers.get('Content-Type')}")

        # Parse JSON
        data = response.json()

        # Save response for analysis
        output_file = Path("scripts/test_multi_station_response.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\n  [OK] Saved response to: {output_file}")

        # Analyze structure
        print(f"\n{'='*80}")
        print("RESPONSE STRUCTURE ANALYSIS")
        print("="*80)

        print(f"\nTop-level keys:")
        for key in data.keys():
            print(f"  - {key}")

        # Check if it's a Coverage or FeatureCollection
        if "type" in data:
            print(f"\nType: {data['type']}")

        # Look for domain (coordinates)
        if "domain" in data:
            print(f"\nDomain structure:")
            domain = data["domain"]
            for key in domain.keys():
                print(f"  - {key}")

            if "axes" in domain:
                print(f"\nAxes:")
                for axis_name, axis_data in domain["axes"].items():
                    print(f"  - {axis_name}: {type(axis_data).__name__}")
                    if isinstance(axis_data, dict) and "values" in axis_data:
                        values = axis_data["values"]
                        if isinstance(values, list):
                            print(f"    Values: {len(values)} items")
                            if len(values) > 0:
                                print(f"    First: {values[0]}")
                                print(f"    Last: {values[-1]}")

        # Look for parameters
        if "parameters" in data:
            print(f"\nParameters:")
            params = data["parameters"]
            for param_name in params.keys():
                print(f"  - {param_name}")

        # Look for ranges (actual data values)
        if "ranges" in data:
            print(f"\nRanges (data):")
            ranges = data["ranges"]
            for range_name, range_data in ranges.items():
                print(f"  - {range_name}")
                if isinstance(range_data, dict):
                    for key in range_data.keys():
                        print(f"    - {key}")

                    if "values" in range_data:
                        values = range_data["values"]
                        if isinstance(values, list):
                            print(f"      Total values: {len(values)}")
                            # Sample first few non-null values
                            sample = [v for v in values[:100] if v is not None][:5]
                            print(f"      Sample: {sample}")

        # Check for composite structure (multiple stations)
        if "coverages" in data:
            print(f"\n[INFO] Response contains 'coverages' - This is a CoverageCollection!")
            print(f"  Number of coverages: {len(data['coverages'])}")
            for i, coverage in enumerate(data["coverages"]):
                print(f"\n  Coverage {i+1}:")
                if "domain" in coverage:
                    if "axes" in coverage["domain"]:
                        if "composite" in coverage["domain"]["axes"]:
                            composite = coverage["domain"]["axes"]["composite"]
                            if "values" in composite:
                                print(f"    Stations: {composite['values']}")

        # Look for how stations are identified
        print(f"\n{'='*80}")
        print("STATION IDENTIFICATION")
        print("="*80)

        # Check if domain has composite axis (multi-station indicator)
        if "domain" in data and "axes" in data["domain"]:
            if "composite" in data["domain"]["axes"]:
                print(f"\n[OK] Found 'composite' axis (multi-station dimension)")
                composite = data["domain"]["axes"]["composite"]
                print(f"  Data type: {composite.get('dataType')}")
                if "values" in composite:
                    station_values = composite["values"]
                    print(f"  Stations in response: {len(station_values)}")
                    for i, station in enumerate(station_values):
                        print(f"    {i+1}. {station}")
            else:
                print(f"\n[WARNING] No 'composite' axis found - may be single-station format")

        print(f"\n{'='*80}")
        print("TEST SUMMARY")
        print("="*80)
        print(f"[SUCCESS] Multi-station query successful!")
        print(f"[SUCCESS] Response size: {len(response.content):,} bytes")
        print(f"[SUCCESS] Response saved for detailed analysis")
        print(f"\nNext steps:")
        print(f"  1. Examine test_multi_station_response.json")
        print(f"  2. Identify how to split data by station")
        print(f"  3. Implement parsing logic in ingest_bronze_raw.py")

        return data

    except requests.exceptions.HTTPError as e:
        print(f"\n[ERROR] HTTP Error: {e.response.status_code}")
        print(f"  Response: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    test_multi_station_query()
