import os
import time
from datetime import date, timedelta, datetime
import requests
import xarray as xr
import pandas as pd
from dotenv import load_dotenv

# Load environment variables from .env file (in parent directory)
load_dotenv("../.env")

# --- Configuration ---
API_KEY = os.getenv("KNMI_OPEN_DATA_API_KEY")
if not API_KEY:
    raise ValueError("KNMI_OPEN_DATA_API_KEY not found in .env file. Please create a .env file with your API key.")
DATASET_NAME = "hourly-in-situ-meteorological-observations-validated"
DATASET_VERSION = "1.0"
STATION_ID = "0-20000-0-06275"  # Deelen
START_YEAR = 2025
END_YEAR = 2025
OUTPUT_CSV = "weather_data_hupsel.csv"
BASE_URL = "https://api.dataplatform.knmi.nl/open-data/v1"

# --- Functions ---

def get_download_url(session, filename):
    """Gets the temporary download URL for a file."""
    url = f"{BASE_URL}/datasets/{DATASET_NAME}/versions/{DATASET_VERSION}/files/{filename}/url"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json().get("temporaryDownloadUrl")
    except requests.exceptions.RequestException as e:
        print(f"Error getting download URL for {filename}: {e}")
        return None

def download_file(url, temp_filepath):
    """Downloads a file from a URL."""
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(temp_filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file from {url}: {e}")
        return False

def process_netcdf(filepath, station_id):
    """Opens a NetCDF file and extracts the relevant weather data for a specific station."""
    try:
        with xr.open_dataset(filepath, engine="netcdf4") as ds:
            # Select data for the specific station
            station_data = ds.sel(station=station_id)
            
            # Extract the data, handling potential missing values
            temp = station_data["T"].values.item(0) if "T" in station_data else None
            humidity = station_data["U"].values.item(0) if "U" in station_data else None
            # Rainfall: -1 means < 0.05mm, so we treat it as 0
            rainfall = station_data["RH"].values.item(0) if "RH" in station_data else None
            if rainfall == -1:
                rainfall = 0.0

            timestamp = pd.to_datetime(station_data["time"].values.item(0))

            return {
                "timestamp": timestamp,
                "temperature_celsius": temp,
                "humidity_percent": humidity,
                "rainfall_mm": rainfall,
            }
    except Exception as e:
        print(f"Error processing file {filepath}: {e}")
        return None

# --- Main Execution ---

def main():
    """Main function to download and process the weather data."""
    print("Starting weather data download and processing...")
    
    # Use a session for connection pooling
    session = requests.Session()
    session.headers.update({"Authorization": API_KEY})

    all_data = []
    total_files = 0
    processed_files = 0
    
    start_date = date(2025, 11, 11)
    end_date = date(2025, 11, 11)
    
    # Calculate total number of files for progress indication
    total_days = (end_date - start_date).days + 1
    total_files_to_process = total_days * 24

    print(f"Date range: {start_date} to {end_date}")
    print(f"Total files to process: {total_files_to_process}")
    
    # Create a temporary file path
    temp_filepath = "temp_weather_file.nc"

    for single_date in pd.date_range(start_date, end_date):
        for hour in range(24):
            current_dt = datetime(single_date.year, single_date.month, single_date.day, hour)
            filename = f"hourly-observations-validated-{current_dt.strftime('%Y%m%d')}-{current_dt.strftime('%H')}.nc"
            
            total_files += 1
            print(f"Processing file {total_files}/{total_files_to_process}: {filename}...")

            download_url = get_download_url(session, filename)
            if not download_url:
                continue

            if not download_file(download_url, temp_filepath):
                continue

            data = process_netcdf(temp_filepath, STATION_ID)
            if data:
                all_data.append(data)
                processed_files += 1
            
            # Clean up the temporary file
            if os.path.exists(temp_filepath):
                os.remove(temp_filepath)

            # Add a delay to respect API rate limits
            time.sleep(4)

    print(f"\nProcessing complete.")
    print(f"Successfully processed {processed_files} out of {total_files_to_process} files.")

    if not all_data:
        print("No data was collected. Exiting.")
        return

    # Convert to DataFrame and save to CSV
    print("Saving data to CSV...")
    df = pd.DataFrame(all_data)
    df.set_index("timestamp", inplace=True)
    df.sort_index(inplace=True)
    df.to_csv(OUTPUT_CSV)

    print(f"Data successfully saved to {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
