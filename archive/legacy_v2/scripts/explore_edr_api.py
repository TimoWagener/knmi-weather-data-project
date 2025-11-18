"""
Script to explore KNMI EDR API capabilities
"""
import os
import requests
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables (in parent directory)
load_dotenv("../.env")

# API Configuration
API_KEY = os.getenv("KNMI_EDR_API_KEY")
if not API_KEY:
    raise ValueError("KNMI_EDR_API_KEY not found in .env file. Please create a .env file with your API key.")
EDR_BASE_URL = "https://api.dataplatform.knmi.nl/edr/v1"
headers = {"Authorization": API_KEY}

print("="*80)
print("KNMI EDR API EXPLORATION")
print("="*80)

# 1. List all available collections
print("\n1. AVAILABLE EDR COLLECTIONS")
print("-"*80)
try:
    response = requests.get(f"{EDR_BASE_URL}/collections", headers=headers)
    response.raise_for_status()
    collections_data = response.json()

    if "collections" in collections_data:
        print(f"Found {len(collections_data['collections'])} collections:\n")
        for collection in collections_data['collections']:
            coll_id = collection.get('id', 'N/A')
            title = collection.get('title', 'N/A')
            print(f"  ID: {coll_id}")
            print(f"  Title: {title}")

            # Check for parameter names
            if 'parameter_names' in collection:
                params = collection['parameter_names']
                print(f"  Parameters: {', '.join(params.keys())[:100]}...")
            print()
    else:
        print("Unexpected response structure:")
        print(json.dumps(collections_data, indent=2)[:500])
except requests.exceptions.RequestException as e:
    print(f"Error fetching collections: {e}")

# 2. Get details of a specific collection (hourly observations)
print("\n2. HOURLY OBSERVATIONS COLLECTION DETAILS")
print("-"*80)
hourly_collection = "hourly-in-situ-meteorological-observations-validated"
try:
    response = requests.get(f"{EDR_BASE_URL}/collections/{hourly_collection}", headers=headers)
    response.raise_for_status()
    collection_info = response.json()

    print(f"Collection: {collection_info.get('title', 'N/A')}")
    print(f"Description: {collection_info.get('description', 'N/A')[:200]}...")

    # Available query types
    if 'data_queries' in collection_info:
        print(f"\nAvailable query types:")
        for query_type, query_info in collection_info['data_queries'].items():
            print(f"  - {query_type}: {query_info.get('link', {}).get('href', 'N/A')}")

    # Parameters
    if 'parameter_names' in collection_info:
        print(f"\nAvailable parameters:")
        for param_id, param_info in list(collection_info['parameter_names'].items())[:10]:
            print(f"  - {param_id}: {param_info.get('description', 'N/A')}")

    # Extent (time and spatial coverage)
    if 'extent' in collection_info:
        extent = collection_info['extent']
        if 'temporal' in extent:
            print(f"\nTemporal extent:")
            print(f"  {extent['temporal']}")
        if 'spatial' in extent:
            print(f"\nSpatial extent:")
            print(f"  {extent['spatial']}")

except requests.exceptions.RequestException as e:
    print(f"Error fetching collection details: {e}")

# 3. List available locations (stations)
print("\n3. AVAILABLE LOCATIONS/STATIONS")
print("-"*80)
try:
    response = requests.get(f"{EDR_BASE_URL}/collections/{hourly_collection}/locations", headers=headers)
    response.raise_for_status()
    locations_data = response.json()

    if 'features' in locations_data:
        print(f"Found {len(locations_data['features'])} stations:\n")
        for feature in locations_data['features'][:15]:  # Show first 15
            loc_id = feature.get('id', 'N/A')
            props = feature.get('properties', {})
            name = props.get('name', 'N/A')
            coords = feature.get('geometry', {}).get('coordinates', [])
            print(f"  ID: {loc_id} | Name: {name} | Coords: {coords}")
    else:
        print("Unexpected response structure")
        print(json.dumps(locations_data, indent=2)[:500])

except requests.exceptions.RequestException as e:
    print(f"Error fetching locations: {e}")

# 4. Test query for Deelen station
print("\n4. TEST QUERY: Deelen Station (Last 48 Hours)")
print("-"*80)
deelen_id = "0-20000-0-06275"
end_time = datetime.utcnow()
start_time = end_time - timedelta(hours=48)
datetime_range = f"{start_time.isoformat()}Z/{end_time.isoformat()}Z"

params = {
    "datetime": datetime_range,
    "parameter-name": "T,U,RH"  # Temperature, Humidity, Rainfall
}

try:
    url = f"{EDR_BASE_URL}/collections/{hourly_collection}/locations/{deelen_id}"
    print(f"URL: {url}")
    print(f"Params: {params}")

    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    print(f"\nResponse structure:")
    print(f"  Type: {data.get('type', 'N/A')}")

    if 'properties' in data:
        props = data['properties']
        if 'observedProperty' in props:
            print(f"  Parameters returned: {list(props['observedProperty'].keys())}")

    # Try to extract some actual data
    if 'features' in data:
        print(f"  Number of features: {len(data['features'])}")
        if len(data['features']) > 0:
            first_feature = data['features'][0]
            print(f"  First feature sample:")
            print(json.dumps(first_feature, indent=2)[:500])
    elif 'values' in data.get('properties', {}):
        values = data['properties']['values']
        print(f"  Number of values: {len(values)}")
        print(f"  First value sample:")
        print(json.dumps(values[0], indent=2) if values else "No values")

except requests.exceptions.RequestException as e:
    print(f"Error querying station data: {e}")
    if hasattr(e.response, 'text'):
        print(f"Response: {e.response.text[:500]}")

print("\n" + "="*80)
print("EXPLORATION COMPLETE")
print("="*80)
