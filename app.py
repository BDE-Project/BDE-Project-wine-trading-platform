# app.py
import os
from flask import Flask, render_template, jsonify, request
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

# Load wine and restaurant data
wine_data = pd.read_csv(os.path.join(DATA_FOLDER, 'wine_restaurants.csv'))


def format_date(value):
    if isinstance(value, str):
        try:
            # Try converting the string to a datetime object and format it
            return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S").strftime("%B %d, %Y")
        except ValueError:
            return value  # If conversion fails, return the original value
    return value  # If it's not a string, return as is

# Register the custom format_date filter
app.jinja_env.filters['format_date'] = format_date

@app.route('/')
def index():
    return render_template('index.html')

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

    # Filter the wine data based on query parameters
    filtered_wines = wine_data

    if wine_type:
        filtered_wines = filtered_wines[filtered_wines['Wine Type'].str.contains(wine_type, case=False)]
    if supplier:
        filtered_wines = filtered_wines[filtered_wines['Company Name'].str.contains(supplier, case=False)]
    if min_price is not None:
        filtered_wines = filtered_wines[filtered_wines['Wine Price'] >= min_price]
    if max_price is not None:
        filtered_wines = filtered_wines[filtered_wines['Wine Price'] <= max_price]
    if min_score is not None:
        filtered_wines = filtered_wines[filtered_wines['Tasting Score'] >= min_score]
    if max_score is not None:
        filtered_wines = filtered_wines[filtered_wines['Tasting Score'] <= max_score]

    # Convert to dictionary for rendering
    wine_records = filtered_wines.to_dict(orient='records')

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
