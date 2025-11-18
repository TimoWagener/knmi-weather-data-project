"""
Script to explore KNMI Open Data API capabilities
Testing file listing, filtering, and pagination
"""
import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables (in parent directory)
load_dotenv("../.env")

# API Configuration
API_KEY = os.getenv("KNMI_OPEN_DATA_API_KEY")
if not API_KEY:
    raise ValueError("KNMI_OPEN_DATA_API_KEY not found in .env file. Please create a .env file with your API key.")
BASE_URL = "https://api.dataplatform.knmi.nl/open-data/v1"
DATASET_NAME = "hourly-in-situ-meteorological-observations-validated"
DATASET_VERSION = "1.0"
headers = {"Authorization": API_KEY}

print("="*80)
print("KNMI OPEN DATA API EXPLORATION")
print("="*80)

# 1. Test file listing with different parameters
print("\n1. FILE LISTING CAPABILITIES")
print("-"*80)

# Basic listing
print("\nA) Basic listing (first 10 files, default sort):")
try:
    url = f"{BASE_URL}/datasets/{DATASET_NAME}/versions/{DATASET_VERSION}/files"
    params = {"maxKeys": 10}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    print(f"  Response keys: {data.keys()}")
    print(f"  isTruncated: {data.get('isTruncated', 'N/A')}")
    print(f"  Number of files returned: {len(data.get('files', []))}")

    if data.get('files'):
        print(f"\n  First 3 filenames:")
        for f in data['files'][:3]:
            print(f"    - {f.get('filename')} (size: {f.get('size')} bytes, modified: {f.get('lastModified')})")

except requests.exceptions.RequestException as e:
    print(f"  Error: {e}")

# Test sorting by lastModified descending (to get latest files first)
print("\nB) Sorted by lastModified (descending) to get latest files:")
try:
    params = {"maxKeys": 10, "orderBy": "lastModified", "sorting": "desc"}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    print(f"  Number of files returned: {len(data.get('files', []))}")
    if data.get('files'):
        print(f"\n  Latest 5 files:")
        for f in data['files'][:5]:
            print(f"    - {f.get('filename')} (modified: {f.get('lastModified')})")

except requests.exceptions.RequestException as e:
    print(f"  Error: {e}")

# Test using begin parameter for pagination/filtering
print("\nC) Using 'begin' parameter to start from specific filename:")
try:
    # Start from a specific date (2025-11-01)
    start_filename = "hourly-observations-validated-20251101-00.nc"
    params = {"maxKeys": 10, "begin": start_filename, "orderBy": "filename", "sorting": "asc"}
    response = requests.get(url, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()

    print(f"  Number of files returned: {len(data.get('files', []))}")
    if data.get('files'):
        print(f"\n  Files starting from {start_filename}:")
        for f in data['files'][:5]:
            print(f"    - {f.get('filename')}")

    if 'nextPageToken' in data:
        print(f"\n  Next page token available: {data['nextPageToken'][:50]}...")

except requests.exceptions.RequestException as e:
    print(f"  Error: {e}")

# 2. Test pagination to get large date ranges
print("\n2. PAGINATION TEST")
print("-"*80)
print("Fetching 100 files to test pagination...")
try:
    all_files = []
    next_token = None
    page_count = 0
    max_pages = 5  # Limit to 5 pages for testing

    params = {
        "maxKeys": 100,
        "orderBy": "filename",
        "sorting": "asc",
        "begin": "hourly-observations-validated-20250101-00.nc"
    }

    while page_count < max_pages:
        if next_token:
            params["startAfterFilename"] = next_token

        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()

        files = data.get('files', [])
        all_files.extend(files)
        page_count += 1

        print(f"  Page {page_count}: {len(files)} files")

        if not data.get('isTruncated', False):
            break

        # Get next page token
        if 'nextPageToken' in data:
            next_token = data['nextPageToken']
        elif files:
            next_token = files[-1]['filename']
        else:
            break

    print(f"\n  Total files fetched: {len(all_files)}")
    if all_files:
        print(f"  Date range: {all_files[0]['filename']} to {all_files[-1]['filename']}")

except requests.exceptions.RequestException as e:
    print(f"  Error: {e}")

# 3. Calculate API efficiency for full 2024-2025
print("\n3. API EFFICIENCY CALCULATION FOR 2024-2025")
print("-"*80)

# 2024: 366 days (leap year) * 24 hours = 8784 files
# 2025: 365 days * 24 hours = 8760 files
# Total: 17544 files

files_2024 = 366 * 24
files_2025 = 365 * 24
total_files = files_2024 + files_2025

print(f"Files needed for 2024: {files_2024}")
print(f"Files needed for 2025: {files_2025}")
print(f"Total files to download: {total_files}")

# With registered API key limits
rate_limit_per_sec = 200
quota_per_hour = 1000

# File listing
max_files_per_request = 100
list_requests_needed = (total_files // max_files_per_request) + 1
print(f"\nFile listing requests needed: {list_requests_needed} (at maxKeys=100)")
print(f"  Time at max rate: {list_requests_needed / rate_limit_per_sec:.2f} seconds")

# Download URL requests (one per file)
print(f"\nDownload URL requests needed: {total_files}")
print(f"  Time at max rate: {total_files / rate_limit_per_sec:.2f} seconds ({total_files / rate_limit_per_sec / 60:.2f} minutes)")
print(f"  Total API requests: {list_requests_needed + total_files}")
print(f"  Hours needed (at 1000 req/hour): {(list_requests_needed + total_files) / quota_per_hour:.2f} hours")

# With current 4-second delay
print(f"\nWith current 4-second delay between downloads:")
print(f"  Time needed: {total_files * 4 / 3600:.2f} hours ({total_files * 4 / 3600 / 24:.2f} days)")

# Optimal approach
print(f"\nOptimal approach (no artificial delay):")
print(f"  Download time limited by quota: {(list_requests_needed + total_files) / quota_per_hour:.2f} hours")
print(f"  Can use concurrent downloads (recommended: 10 threads)")

print("\n" + "="*80)
print("EXPLORATION COMPLETE")
print("="*80)
