# app.py
import os
from flask import Flask, render_template, request
import pandas as pd
from datetime import datetime
from fetch_restaurant_data import fetch_and_save_data
from logistics_module import (
    get_all_flights, 
    find_best_flight, 
    fetch_flight_data_with_rate_limit, 
    get_weather_at_arrival, 
    get_detailed_traffic_data, 
    save_data_to_csv
)

app = Flask(__name__)

# Absolute path to the project base directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, 'data')

# Paths to data files
restaurant_data_path = os.path.join(DATA_FOLDER, 'restaurant_and_wine_data.csv')
wine_data_path = os.path.join(DATA_FOLDER, 'wine_restaurants.csv')


# Load wine data globally for filtering
wine_data = pd.read_csv(wine_data_path) if os.path.exists(wine_data_path) else pd.DataFrame()

# Helper function to calculate dashboard data
def get_dashboard_data():
    # Load data from CSV files
    if os.path.exists(restaurant_data_path):
        restaurant_data = pd.read_csv(restaurant_data_path)
    else:
        restaurant_data = pd.DataFrame()

    if os.path.exists(wine_data_path):
        wine_data = pd.read_csv(wine_data_path)
    else:
        wine_data = pd.DataFrame()

    # Total unique restaurants
    total_restaurants = restaurant_data['Restaurant Name'].nunique() if not restaurant_data.empty else 0

    # Total unique wines available
    total_wines = wine_data['Wine Name'].nunique() if not wine_data.empty else 0

    # Average wine price and tasting score
    avg_wine_price = round(wine_data['Wine Price'].mean(), 2) if not wine_data.empty else 0
    avg_tasting_score = round(wine_data['Tasting Score'].mean(), 2) if not wine_data.empty else 0

    # Popular wine types distribution
    wine_type_counts = wine_data['Wine Type'].value_counts(normalize=True) * 100 if not wine_data.empty else {}
    popular_wine_types = wine_type_counts.to_dict()

    # Top 5 wine suppliers based on number of wines available
    top_suppliers = (
        wine_data['Company Name'].value_counts().nlargest(5).to_dict() if not wine_data.empty else {}
    )

    # Placeholder data for auctions and logistics alerts
    upcoming_auctions = 8  # Static placeholder; update dynamically as needed
    logistics_alerts = [
        {"route": "LAX to Restaurant A", "status": "Delayed"},
        {"route": "SFO to Restaurant C", "status": "On Time"},
        {"route": "JFK to Restaurant D", "status": "Heavy Traffic"}
    ]

    return {
        "total_restaurants": total_restaurants,
        "total_wines": total_wines,
        "avg_wine_price": avg_wine_price,
        "avg_tasting_score": avg_tasting_score,
        "popular_wine_types": popular_wine_types,
        "top_suppliers": top_suppliers,
        "upcoming_auctions": upcoming_auctions,
        "logistics_alerts": logistics_alerts
    }

@app.route('/')
def index():
    dashboard_data = get_dashboard_data()
    return render_template('index.html', dashboard_data=dashboard_data)

@app.route('/restaurants')
def restaurants():
    city = request.args.get('city', 'San Francisco')
    
    # Fetch or use cached data
    fetch_and_save_data(city)
    
    # Read the cached restaurant and wine data
    restaurant_data_path = os.path.join(DATA_FOLDER, 'restaurant_and_wine_data.csv')
    
    # Check if the file exists before reading it
    if os.path.exists(restaurant_data_path):
        restaurants = pd.read_csv(restaurant_data_path)
    else:
        print(f"Error: The file {restaurant_data_path} does not exist.")
        restaurants = pd.DataFrame()  # Return an empty DataFrame if the file doesn't exist
    
    return render_template('restaurant_data.html', restaurants=restaurants.to_dict(orient='records'))


@app.route('/wines')
def wines():
    # Get filter parameters from the request
    wine_type = request.args.get('wine_type')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    supplier = request.args.get('supplier')
    min_score = request.args.get('min_score', type=float)
    max_score = request.args.get('max_score', type=float)

    # Read the wine data CSV file
    if os.path.exists(wine_data_path):
        wine_data = pd.read_csv(wine_data_path)
    else:
        print(f"Error: The file {wine_data_path} does not exist.")
        wine_data = pd.DataFrame()  # Return an empty DataFrame if the file doesn't exist

    if wine_data.empty:
        return render_template('wine_data.html', wines=[])

    # Filter the wine data based on query parameters
    if wine_type:
        wine_data = wine_data[wine_data['Wine Type'].str.contains(wine_type, case=False)]
    if supplier:
        wine_data = wine_data[wine_data['Company Name'].str.contains(supplier, case=False)]
    if min_price is not None:
        wine_data = wine_data[wine_data['Wine Price'] >= min_price]
    if max_price is not None:
        wine_data = wine_data[wine_data['Wine Price'] <= max_price]
    if min_score is not None:
        wine_data = wine_data[wine_data['Tasting Score'] >= min_score]
    if max_score is not None:
        wine_data = wine_data[wine_data['Tasting Score'] <= max_score]

    # Convert to dictionary for rendering
    wine_records = wine_data.to_dict(orient='records')

    return render_template('wine_data.html', wines=wine_records)

@app.route('/auction')
def auction():
    # Auction logic can go here, simplified as placeholder
    return render_template('auction.html')

@app.route('/logistics')
def logistics():
    # Fetch all available flights with rate limiting
    all_flights = fetch_flight_data_with_rate_limit()
    
    # Initialize default values for variables to avoid NameError
    best_flight = None
    arrival_weather = []
    traffic_details = []

    if all_flights:
        # Get the best flight details
        best_flight = find_best_flight(all_flights)
        
        if best_flight:
            # Extract arrival time for weather data
            arrival_time = best_flight["Arrival Time"]
            
            # Fetch the weather data for the arrival time
            arrival_weather = get_weather_at_arrival(arrival_time)
            
            # Format arrival time for display in the template
            arrival_time_formatted = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M:%S").strftime("%B %d, %Y, %H:%M %p")
            
            # Get traffic data from LAX to destination
            traffic_details = get_detailed_traffic_data()
            
            # Save the complete data to an Excel file
            save_data_to_csv(all_flights, best_flight, arrival_weather, traffic_details)

            # Render the logistics.html template with the data
            return render_template(
                'logistics.html',
                best_flight=best_flight,
                arrival_weather=arrival_weather,
                traffic_details=traffic_details,
                arrival_time_formatted=arrival_time_formatted
            )
        else:
            return render_template('logistics.html', error="No best flight found.")
    else:
        return render_template('logistics.html', error="Failed to fetch flight data.")

if __name__ == '__main__':
    app.run(debug=True)
