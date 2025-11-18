
# Local Weather Data Project Plan

This document outlines the plan for creating a local weather data platform to analyze historical weather patterns for Doetinchem, The Netherlands.

## 1. Project Goal

The primary goal of this project is to collect, store, and analyze historical weather data for the area around Doetinchem. The initial focus is on analyzing temperature, humidity, and rainfall patterns over the last two years. The platform will be designed to be extensible for future predictive modeling tasks.

## 2. Data Source

We will use the **"Hourly, validated and automated in-situ ground-based meteorological observations in the Netherlands"** dataset from the KNMI Data Platform.

- **Dataset Name:** `hourly-in-situ-meteorological-observations-validated`
- **Dataset Version:** `1.0`
- **Data Granularity:** Hourly
- **Data Quality:** Validated by KNMI experts.

This dataset is ideal as it provides high-quality, hourly data, which aligns perfectly with the project's requirements.

## 3. Station Selection

Based on our analysis, the weather station closest to Doetinchem available in this hourly dataset is **Deelen**.

- **Station Name:** DEELEN
- **Station ID:** `0-20000-0-06275`

All data will be filtered to use the observations from this station. (Note: The Hupsel station was not found in this hourly dataset.)

## 4. Data Ingestion & Processing

We will create a Python script (`download_data.py`) to perform the data ingestion and processing. This script will be the core of the project and will perform the following steps:

    - **Define Parameters:** The script will start by defining the key parameters: dataset name, version, station ID (`0-20000-0-06275`), and the date range (the months of October and November 2025).

2.  **Iterate and Download:** The script will loop through each day of the specified date range. For each day, it will:
    a. Construct the filename for the corresponding hourly NetCDF file. The file naming convention will be determined by inspecting the dataset's file listing.
    b. Call the KNMI Open Data API to get a temporary download URL for the file.
    c. Download the NetCDF file.

3.  **Extract and Process:** For each downloaded file, the script will:
    a. Open the NetCDF file using the `xarray` library.
    b. Select the data for the Deelen station using the station ID `0-20000-0-06275`.
    c. Extract the values for the required variables:
        - **Temperature:** `T` (air temperature)
        - **Humidity:** `U` (relative humidity)
        - **Rainfall:** `RH` (precipitation amount)
    d. Combine the extracted data with the timestamp.

4.  **Collect Data:** The script will append the processed data from each file into a single list or pandas DataFrame.

## 5. Data Storage

After processing all the files for the entire date range, the script will save the collected data into a single, clean CSV file named `weather_data_hupsel.csv`. This file will contain the following columns:

- `timestamp`
- `temperature_celsius`
- `humidity_percent`
- `rainfall_mm`

This CSV file will serve as our local data warehouse for the analysis phase.

## 6. Analysis

With the `weather_data_hupsel.csv` file created, we can perform the historical analysis. This can be done in a separate Python script or a Jupyter Notebook (`analysis.ipynb`). The analysis will involve:

- Loading the CSV file into a pandas DataFrame.
- Using libraries like `matplotlib` or `plotly` to create visualizations, such as:
  - Time series plots of temperature and humidity over the last two years.
  - Monthly or seasonal rainfall summaries.
  - Histograms and box plots to understand the distribution of the weather variables.

## 7. Proposed Project Structure

The project will be organized with the following file structure:

```
/Gemini-One
|-- local_weather_data_project_plan.md  (This file)
|-- download_data.py                    (Script to download and process the data)
|-- analysis.ipynb                      (Jupyter Notebook for data analysis)
|-- weather_data_hupsel.csv             (The final, clean dataset - will be generated)
|-- .gitignore                          (To exclude sensitive files and downloaded data)
```
