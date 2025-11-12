"""
Test script for KNMI EDR API using environment variables
Run this after setting up your .env file
"""
import os
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta

# Load environment variables from .env file (in parent directory)
load_dotenv("../.env")

# Get API key from environment
EDR_API_KEY = os.getenv("KNMI_EDR_API_KEY")

if not EDR_API_KEY:
    print("ERROR: KNMI_EDR_API_KEY not found in .env file!")
    print("\nPlease create a .env file with your EDR API key:")
    print("  1. Copy .env.example to .env")
    print("  2. Add your EDR API key to .env")
    print("  3. Run this script again")
    exit(1)

# EDR API Configuration
EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"
headers = {"Authorization": EDR_API_KEY}

print("="*80)
print("KNMI EDR API TEST (Using .env)")
print("="*80)
print(f"API Key loaded: {EDR_API_KEY[:20]}...{EDR_API_KEY[-10:]}")
print()

# Test 1: List available collections
print("1. LISTING AVAILABLE EDR COLLECTIONS")
print("-"*80)
try:
    response = requests.get(f"{EDR_BASE_URL}/collections", headers=headers)
    response.raise_for_status()
    collections_data = response.json()

    if "collections" in collections_data:
        print(f"[OK] Success! Found {len(collections_data['collections'])} collections:\n")
        for collection in collections_data['collections']:
            coll_id = collection.get('id', 'N/A')
            title = collection.get('title', 'N/A')
            print(f"  • {coll_id}")
            print(f"    {title}")
            print()
    else:
        print("[WARN] Unexpected response format")

except requests.exceptions.HTTPError as e:
    if e.response.status_code == 403:
        print("[ERROR] Access denied (403)")
        print("   Your EDR API key may not be valid or activated")
    else:
        print(f"[ERROR] HTTP Error: {e}")
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Request failed: {e}")
    exit(1)

# Test 2: Get hourly observations collection details
print("\n2. HOURLY OBSERVATIONS COLLECTION DETAILS")
print("-"*80)
collection_id = "hourly-in-situ-meteorological-observations-validated"
try:
    response = requests.get(f"{EDR_BASE_URL}/collections/{collection_id}", headers=headers)
    response.raise_for_status()
    collection_info = response.json()

    print(f"[OK] Collection: {collection_info.get('title', 'N/A')}")

    # Available query types
    if 'data_queries' in collection_info:
        print(f"\n  Query types available:")
        for query_type in collection_info['data_queries'].keys():
            print(f"    • {query_type}")

    # Parameters available
    if 'parameter_names' in collection_info:
        params = collection_info['parameter_names']
        print(f"\n  Parameters available: {len(params)}")
        print(f"    Sample: {', '.join(list(params.keys())[:10])}")

except requests.exceptions.RequestException as e:
    print(f"[ERROR] Failed: {e}")
    exit(1)

# Test 3: List available stations
print("\n3. AVAILABLE WEATHER STATIONS")
print("-"*80)
try:
    response = requests.get(f"{EDR_BASE_URL}/collections/{collection_id}/locations", headers=headers)
    response.raise_for_status()
    locations_data = response.json()

    if 'features' in locations_data:
        print(f"[OK] Found {len(locations_data['features'])} weather stations:\n")
        for feature in locations_data['features']:
            loc_id = feature.get('id', 'N/A')
            props = feature.get('properties', {})
            name = props.get('name', 'N/A')
            coords = feature.get('geometry', {}).get('coordinates', [])
            print(f"  - {loc_id:20s} | {name:25s} | Lon: {coords[0]:.4f}, Lat: {coords[1]:.4f}")

except requests.exceptions.RequestException as e:
    print(f"[ERROR] Failed: {e}")
    exit(1)

# Test 4: Query specific station (Deelen) for recent data
print("\n4. TEST QUERY: Deelen Station (Last 24 Hours)")
print("-"*80)
deelen_id = "0-20000-0-06275"
end_time = datetime.utcnow()
start_time = end_time - timedelta(hours=24)
datetime_range = f"{start_time.isoformat()}Z/{end_time.isoformat()}Z"

params = {
    "datetime": datetime_range,
    "parameter-name": "T,U,RH"  # Temperature, Humidity, Rainfall
}

try:
    url = f"{EDR_BASE_URL}/collections/{collection_id}/locations/{deelen_id}"
    print(f"Query: {url}")
    print(f"Date range: {start_time.strftime('%Y-%m-%d %H:%M')} to {end_time.strftime('%Y-%m-%d %H:%M')}")
    print(f"Parameters: {params['parameter-name']}")

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    print(f"\n[OK] Query successful!")
    print(f"  Response type: {data.get('type', 'N/A')}")

    # Try to show some data structure
    if 'properties' in data and 'observedProperty' in data['properties']:
        params_returned = list(data['properties']['observedProperty'].keys())
        print(f"  Parameters in response: {params_returned}")

    # Save response for inspection
    with open('edr_test_response.json', 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n  Full response saved to: edr_test_response.json")

except requests.exceptions.HTTPError as e:
    print(f"[ERROR] HTTP Error: {e}")
    if hasattr(e.response, 'text'):
        print(f"   Response: {e.response.text[:200]}")
except requests.exceptions.RequestException as e:
    print(f"[ERROR] Failed: {e}")

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)

if os.path.exists('edr_test_response.json'):
    print("\n[SUCCESS] EDR API is working!")
    print("   Check edr_test_response.json to see the data structure")
    print("\nNext steps:")
    print("  1. Review the response format")
    print("  2. Decide on extraction strategy (EDR vs Open Data API)")
    print("  3. Build the data pipeline")
else:
    print("\n[WARN] Some tests failed. Check error messages above.")
