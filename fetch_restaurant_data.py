import os
import requests
import pandas as pd
import random
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Google Places API Key 
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# Constants
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # Base directory of the script
DATA_FOLDER = os.path.join(BASE_DIR, "data")
CACHE_FILE = os.path.join(DATA_FOLDER, "restaurant_and_wine_data.csv")
CACHE_EXPIRY_HOURS = 12  # Set cache expiry to 12 hours

# Debugging: Print paths for confirmation
print(f"Base directory of the script: {BASE_DIR}")
print(f"Path to data folder: {DATA_FOLDER}")
print(f"Path to cache file: {CACHE_FILE}")

# Ensure the data folder exists
if not os.path.exists(DATA_FOLDER):
    print(f"Creating the data folder at {DATA_FOLDER}")
    os.makedirs(DATA_FOLDER, exist_ok=True)  # Create the folder if it doesn't exist

def search_restaurants(city, limit=50):
    print(f"Searching for restaurants in {city}...")
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"restaurants in {city}",
        "key": GOOGLE_API_KEY
    }
    response = requests.get(url, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code} - {response.text}")
        return []

    results = response.json().get("results", [])
    print(f"Fetched {len(results)} results.")
    
    for place in results:
        print(f"Name: {place['name']}")
        print(f"Address: {place.get('formatted_address', 'N/A')}")
        print(f"Place ID: {place['place_id']}")
        print(f"Latitude: {place['geometry']['location']['lat']}")
        print(f"Longitude: {place['geometry']['location']['lng']}")
        print("---")
    
    return results[:limit]

def get_restaurant_details(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "name,formatted_address,geometry,opening_hours,photo",
        "key": GOOGLE_API_KEY
    }
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json().get("result", {})
        return {
            "name": data.get("name", "N/A"),
            "address": data.get("formatted_address", "N/A"),
            "location": data.get("geometry", {}).get("location", {}),
            "opening_hours": data.get("opening_hours", {}).get("weekday_text", []),
            "photos": data.get("photos", [])
        }
    else:
        print(f"Failed to fetch details for Place ID {place_id}: {response.status_code} - {response.text}")
    return None

def generate_wine_data():
    wine_types = ["Red", "White", "Sparkling", "Rosé"]
    quality_tiers = ["Premium", "Mid-tier", "Entry-level"]
    suppliers = ["Wine Co.", "Vineyard Delights", "Global Wines Ltd.", "Fine Wine Suppliers"]
    
    return {
        "Wine Type": random.choice(wine_types),
        "Supplier": random.choice(suppliers),
        "Quality Tier": random.choice(quality_tiers),
        "Quantity Available": random.randint(10, 100)
    }

def load_cached_data(city):
    """Load cached data for a specific city if it exists and is recent enough."""
    # Debug: Check if the cache file exists
    if not os.path.exists(CACHE_FILE):
        print(f"Cache file {CACHE_FILE} does not exist.")
        return pd.DataFrame()  # No cache available

    # Check if the CSV file contains the "Timestamp" column
    cached_data = pd.read_csv(CACHE_FILE)
    if "Timestamp" not in cached_data.columns:
        print("No 'Timestamp' column found in the cached data.")
        return pd.DataFrame()  # No valid cache if timestamp is missing
    
    # Parse 'Timestamp' column as datetime
    cached_data["Timestamp"] = pd.to_datetime(cached_data["Timestamp"], errors='coerce')
    
    # Filter data for the specific city and check timestamp
    city_data = cached_data[cached_data["City"] == city]
    
    if not city_data.empty:
        # Check if the data is recent enough (within CACHE_EXPIRY_HOURS)
        latest_entry = city_data["Timestamp"].max()
        if datetime.now() - latest_entry <= timedelta(hours=CACHE_EXPIRY_HOURS):
            print(f"Loaded cached data for {city} from {latest_entry.date()}.")
            return city_data
    
    print(f"No valid cached data found for {city}, fetching new data.")
    return pd.DataFrame()  # No valid cache for the city

def fetch_and_save_data(city, limit=50):
    # Step 1: Load cached data if available and recent
    cached_data = load_cached_data(city)
    if not cached_data.empty:
        print(f"Using cached data for {city}.")
        return cached_data

    # Step 2: Fetch new data if no cache is available
    restaurants = search_restaurants(city, limit=limit)
    data = []
    
    for restaurant in restaurants:
        place_id = restaurant["place_id"]
        details = get_restaurant_details(place_id)
        
        if details:
            wine_data = generate_wine_data()
            data.append({
                "City": city,
                "Timestamp": datetime.now(),  # Add timestamp when data is fetched
                "Restaurant Name": details["name"],
                "Address": details["address"],
                "Latitude": details["location"].get("lat"),
                "Longitude": details["location"].get("lng"),
                "Opening Hours": "\n".join(details["opening_hours"]),
                "Wine Type": wine_data["Wine Type"],
                "Supplier": wine_data["Supplier"],
                "Quality Tier": wine_data["Quality Tier"],
                "Quantity Available": wine_data["Quantity Available"]
            })
    
    # Step 3: Save to CSV if data was fetched
    if data:
        df = pd.DataFrame(data)
        # Ensure the data folder exists before saving
        if not os.path.exists(DATA_FOLDER):
            print(f"Creating the data folder at {DATA_FOLDER}")
            os.makedirs(DATA_FOLDER)

        # Create or overwrite the cache file
        try:
            df.to_csv(CACHE_FILE, index=False)
            print(f"Data for {city} saved to {CACHE_FILE}.")
        except Exception as e:
            print(f"Failed to save data to {CACHE_FILE}: {e}")
    else:
        print("No data fetched, so no new entries were added.")
    
    return pd.DataFrame(data)  # Return the new data for immediate use

# Example usage
if __name__ == "__main__":
    city = "San Francisco"  # Specify the city you want to search in
    fetch_and_save_data(city)
