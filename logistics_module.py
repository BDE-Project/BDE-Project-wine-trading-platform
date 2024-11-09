import time
import requests
from functools import lru_cache
import pandas as pd
import os
from amadeus import Client, ResponseError
from dotenv import load_dotenv

# Initialize Amadeus client
amadeus = Client(client_id= os.getenv('AMADEUS_CLIENT_ID'), client_secret=os.getenv('AMADEUS_CLIENT_SECRET'))
OPENWEATHERMAP_API_KEY = os.getenv('OPENWEATHERMAP_API_KEY')
TOMTOM_API_KEY = os.getenv('TOMTOM_API_KEY')

@lru_cache(maxsize=1)  # Cache the results for this function
def get_all_flights():
    try:
        response = amadeus.shopping.flight_offers_search.get(
            originLocationCode="CPT",
            destinationLocationCode="LAX",
            departureDate="2024-12-01",
            adults=1,
            currencyCode="ZAR"
        )
        flights = response.data
        return flights
    except Exception as e:
        print(f"An error occurred while fetching flights: {e}")
        return []

def find_best_flight(flights):
    try:
        best_flight = min(flights, key=lambda x: float(x['price']['total']))
        first_segment = best_flight['itineraries'][0]['segments'][0]
        last_segment = best_flight['itineraries'][0]['segments'][-1]
        return {
            "Flight Price": best_flight['price']['total'],
            "Flight Duration": best_flight['itineraries'][0]['duration'],
            "Departure Time": first_segment['departure']['at'],
            "Arrival Time": last_segment['arrival']['at'],
            "Airline": first_segment['carrierCode'],
            "Stops": len(best_flight['itineraries'][0]['segments']) - 1,
            "Cabin Class": best_flight.get('travelerPricings', [{}])[0].get('fareDetailsBySegment', [{}])[0].get('cabin', "N/A"),
            "Origin": "CPT",
            "Destination": "LAX"
        }
    except Exception as e:
        print(f"An error occurred while selecting the best flight: {e}")
        return None

# Function with rate-limiting for fetching flight data every 1.5 hours
def fetch_flight_data_with_rate_limit():
    flights = get_all_flights()  # Fetch flights, using the cached data if available
    
    # Sleep for 1.5 hours (5400 seconds) to prevent excessive API calls
    #time.sleep(5400)  # Rate-limiting interval
    time.sleep(2)  # Rate-limiting interval
  
    return flights

@lru_cache(maxsize=1)  # Cache the results for this function
def get_weather_at_arrival(arrival_time):
    url = f"https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "q": "Los Angeles,US",
        "appid": OPENWEATHERMAP_API_KEY,
        "units": "metric"
    }
    response = requests.get(url, params=params)
    weather_data = response.json().get("list", [])

    arrival_timestamp = int(time.mktime(time.strptime(arrival_time, "%Y-%m-%dT%H:%M:%S")))

    closest_forecast = None
    closest_time_diff = float('inf')

    for forecast in weather_data:
        forecast_timestamp = forecast['dt']
        time_diff = abs(forecast_timestamp - arrival_timestamp)
        if time_diff < closest_time_diff:
            closest_time_diff = time_diff
            closest_forecast = forecast

    if closest_forecast:
        return [{
            "Time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(closest_forecast['dt'])),
            "Temperature (C)": closest_forecast['main']['temp'],
            "Max Temperature (C)": closest_forecast['main']['temp_max'],
            "Min Temperature (C)": closest_forecast['main']['temp_min'],
            "Humidity (%)": closest_forecast['main']['humidity'],
            "Weather": closest_forecast['weather'][0]['description'],
            "Wind Speed (m/s)": closest_forecast['wind']['speed'],
            "Wind Direction": closest_forecast['wind'].get('deg', 'N/A'),
            "Cloudiness (%)": closest_forecast['clouds']['all']
        }]
    else:
        return [{"Time": arrival_time, "Weather": "No data"}]

@lru_cache(maxsize=1)  # Cache the results for this function
def get_detailed_traffic_data():
    origin_lat, origin_lon = 33.9416, -118.4085  # LAX coordinates
    dest_lat, dest_lon = 34.5889, -120.0382  # Example wine farm coordinates
    url = f"https://api.tomtom.com/routing/1/calculateRoute/{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"

    params = {'key': TOMTOM_API_KEY, 'traffic': 'true', 'routeType': 'fastest'}
    response = requests.get(url, params=params)

    route_info = response.json().get('routes', [])
    if not route_info:
        print("No route information found.")
        return []

    sections = route_info[0].get('sections', [])

    traffic_details = []
    for section in sections:
        traffic_detail = {
            "Start Point": f"{section.get('startPoint', {}).get('latitude', 'N/A')},{section.get('startPoint', {}).get('longitude', 'N/A')}",
            "End Point": f"{section.get('endPoint', {}).get('latitude', 'N/A')},{section.get('endPoint', {}).get('longitude', 'N/A')}",
            "Distance (meters)": section.get('summary', {}).get('lengthInMeters', 0),
            "Travel Time (seconds)": section.get('summary', {}).get('travelTimeInSeconds', 0),
            "Traffic Delay (seconds)": section.get('summary', {}).get('trafficDelayInSeconds', 0),
            "Average Speed (m/s)": section.get('summary', {}).get('speedInMetersPerSecond', 'N/A'),
            "Traffic Level": section.get('trafficLevel', 'N/A')
        }
        traffic_details.append(traffic_detail)

    return traffic_details


def save_data_to_csv(all_flights, best_flight, arrival_weather, traffic_details, file_name="logistics_analysis_detailed.csv"):
    # Define the path to the 'data' directory within the project
    project_dir = os.getcwd()  # Get the current working directory (your project folder)
    data_dir = os.path.join(project_dir, "data")
    
    # Ensure the 'data' directory exists
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    
    # Set the file path to save the CSV file in the 'data' directory
    file_path_csv = os.path.join(data_dir, file_name)

    # Prepare the DataFrames
    df_flights = pd.DataFrame([{
        "Price": flight['price']['total'],
        "Duration": flight['itineraries'][0]['duration'],
        "Departure Time": flight['itineraries'][0]['segments'][0]['departure']['at'],
        "Arrival Time": flight['itineraries'][0]['segments'][-1]['arrival']['at'],
        "Airline": flight['itineraries'][0]['segments'][0]['carrierCode'],
        "Stops": len(flight['itineraries'][0]['segments']) - 1,
        "Cabin Class": flight.get('travelerPricings', [{}])[0].get('fareDetailsBySegment', [{}])[0].get('cabin', "N/A")
    } for flight in all_flights])

    df_best_flight = pd.DataFrame([best_flight])
    df_weather = pd.DataFrame(arrival_weather)
    df_traffic = pd.DataFrame(traffic_details)

    # Combine all dataframes into one (optional - if you want all data combined in one CSV)
    all_data_combined = pd.concat([df_flights, df_best_flight, df_weather, df_traffic], ignore_index=True)

    # Save combined data to a CSV file
    all_data_combined.to_csv(file_path_csv, index=False)

    print(f"Data saved to {file_path_csv} (CSV)")

