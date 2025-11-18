
import xarray as xr

# Open the NetCDF file
ds = xr.open_dataset('sample_hourly.nc', engine='netcdf4')

# Get the station names and IDs
station_ids = ds['station'].values
station_names = ds['stationname'].values

# Print the mapping of station IDs to station names
print("Available weather stations in hourly dataset:")
for station_id, station_name in zip(station_ids, station_names):
    print(f"  ID: {station_id}, Name: {station_name.item().strip()}")
