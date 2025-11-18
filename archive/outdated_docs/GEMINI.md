
# Gemini Project Overview: Local Weather Data Platform

## Project Overview

This project is a Python-based data engineering pipeline designed to download, process, and store historical weather data from the Royal Netherlands Meteorological Institute (KNMI) API. The goal is to create a local dataset of hourly weather conditions (temperature, humidity, and rainfall) for the area around Doetinchem, Netherlands, specifically from the Hupsel weather station (ID: `06283`).

The project uses the following main technologies:
- **Python** for scripting and data manipulation.
- **KNMI Open Data API** as the data source.
- **requests** for making API calls.
- **xarray** and **netCDF4** for reading the scientific NetCDF data format.
- **pandas** for data structuring and analysis.

The final output is a clean, analysis-ready CSV file named `weather_data_hupsel.csv`.

## Building and Running

To set up and run this project, follow these steps:

### 1. Install Dependencies

This project requires a few Python libraries. First, create a `requirements.txt` file with the following content:

```
requests
pandas
xarray
netCDF4
```

Then, install these dependencies using pip:

```bash
pip install -r requirements.txt
```

### 2. Run the Data Ingestion Script

The main script to download and process the data is `download_data.py`. It is currently configured to download data for **October and November 2025**. You can modify the `START_YEAR` and `END_YEAR` variables in the script to change the date range.

To execute the script, run the following command in your terminal:

```bash
python download_data.py
```

**Note:** This will be a long-running process as it downloads and processes a file for each hour in the specified date range.

### 3. Analyze the Data

Once the `download_data.py` script has finished, it will generate a `weather_data_hupsel.csv` file. As outlined in the project plan, you can then use a Jupyter Notebook (`analysis.ipynb`, to be created) to load and analyze this data with pandas, matplotlib, or other data analysis libraries.

## Development Conventions

- The project is organized into distinct Python scripts for different functionalities:
  - `download_data.py`: The main data ingestion pipeline.
  - `inspect_file.py`: A utility script for inspecting the structure of NetCDF data files.
  - `download_file.py`: A helper script for downloading individual files.
- The project plan is documented in `local_weather_data_project_plan.md`.
- The main data ingestion script includes progress indicators to provide feedback during its long-running execution.
