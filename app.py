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
auction_data_path = os.path.join(DATA_FOLDER, 'auction_data.csv')

# Load and preprocess auction data
auction_data = pd.read_csv(auction_data_path) if os.path.exists(auction_data_path) else pd.DataFrame()

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

    # Auction data processing
    if os.path.exists(auction_data_path):
        auction_data = pd.read_csv(auction_data_path)
    else:
        auction_data = pd.DataFrame()

    # General metrics
    total_restaurants = restaurant_data['Restaurant Name'].nunique() if not restaurant_data.empty else 0
    total_wines = wine_data['Wine Name'].nunique() if not wine_data.empty else 0

    # Auction metrics
    participating_restaurants = auction_data[auction_data['auction_restaurant_flag'] == 1]['Resturant_id'].nunique() if not auction_data.empty else 0
    participating_wines = auction_data[auction_data['auction_wine_flag'] == 1]['Wine_Name'].nunique() if not auction_data.empty else 0
    participating_companies = auction_data[auction_data['auction_company_flag'] == 1]['Company_Name'].nunique() if not auction_data.empty else 0

    # Price and demand distributions for auctions
    wine_price_distribution = auction_data['wine_price_category'].value_counts().to_dict() if not auction_data.empty else {}
    demand_distribution = auction_data['demand_flag'].value_counts().to_dict() if not auction_data.empty else {}

    # High demand wines
    high_demand_wines = auction_data[auction_data['demand_flag'] == 'high demand']['Wine_Name'].value_counts().head(5).to_dict() if not auction_data.empty else {}

    # Popular wine types and top suppliers with error handling for missing data
    wine_type_counts = wine_data['Wine Type'].value_counts(normalize=True) * 100 if not wine_data.empty else {}
    popular_wine_types = wine_type_counts.to_dict()
    
    # Ensure 'top_suppliers' is defined, even if there's no data
    top_suppliers = wine_data['Company Name'].value_counts().nlargest(5).to_dict() if not wine_data.empty else {}

    return {
        "total_restaurants": total_restaurants,
        "total_wines": total_wines,
        "participating_restaurants": participating_restaurants,
        "participating_wines": participating_wines,
        "participating_companies": participating_companies,
        "avg_wine_price": round(wine_data['Wine Price'].mean(), 2) if not wine_data.empty else 0,
        "avg_tasting_score": round(wine_data['Tasting Score'].mean(), 2) if not wine_data.empty else 0,
        "popular_wine_types": popular_wine_types,
        "top_suppliers": top_suppliers,
        "wine_price_distribution": wine_price_distribution,
        "demand_distribution": demand_distribution,
        "high_demand_wines": high_demand_wines
    }

# Helper function to return a default image URL based on the wine type
def get_wine_image(wine_type):
    wine_images = {
        "Red": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcSMHCcX8j8urf0uLcbriIjnv5NHoQHwYBU_-g&s",  # Replace with real image URLs
        "White": "https://www.coravin.com/cdn/shop/articles/types_of_white_wine.jpg?v=1725372804",
        "Sparkling": "https://ricowines.com/wp-content/uploads/2024/01/white-Sparkling-1.webp",
        "Rosé": "https://www.realsimple.com/thmb/t8ReENA47WfSPI4Z-VwitNYNWU0=/1500x0/filters:no_upscale():max_bytes(150000):strip_icc()/what-is-rose-GettyImages-1330692681-cf7d3da139524fcbaef63a3ab012821f.jpg",
        "Dessert": "https://images.squarespace-cdn.com/content/v1/54217456e4b0423f1490b26a/1568582733342-6OBSIK7JFMDTH7T6FEAI/Wine+Pairing-7.jpg?format=1500w"
    }
    
    # Default image if wine type not found
    return wine_images.get(wine_type, "https://cdn.cluboenologique.com/wp-content/uploads/2022/03/02113400/vilafonte-675x450.jpg")  # Fallback image

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
    if os.path.exists(restaurant_data_path):
        restaurants = pd.read_csv(restaurant_data_path)
    else:
        print(f"Error: The file {restaurant_data_path} does not exist.")
        restaurants = pd.DataFrame()
    
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

    if os.path.exists(wine_data_path):
        wine_data = pd.read_csv(wine_data_path)
    else:
        print(f"Error: The file {wine_data_path} does not exist.")
        wine_data = pd.DataFrame()

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

    # Add image URL based on wine type
    wine_data['Wine Image'] = wine_data['Wine Type'].apply(get_wine_image)

    wine_records = wine_data.to_dict(orient='records')
    return render_template('wine_data.html', wines=wine_records)

@app.route('/auction')
def auction():
    # Load the auction data to display on the auction page
    if os.path.exists(auction_data_path):
        auction_data = pd.read_csv(auction_data_path)
    else:
        auction_data = pd.DataFrame()

    # Calculate the top auction metrics
    high_demand_wines = auction_data[auction_data['demand_flag'] == 'high demand']['Wine_Name'].value_counts().head(5).to_dict()
    auction_participation = auction_data['auction_restaurant_flag'].value_counts().to_dict()

    return render_template('auction.html', high_demand_wines=high_demand_wines, auction_participation=auction_participation)

@app.route('/logistics')
def logistics():
    all_flights = fetch_flight_data_with_rate_limit()
    best_flight = None
    arrival_weather = []
    traffic_details = []

    if all_flights:
        best_flight = find_best_flight(all_flights)
        
        if best_flight:
            arrival_time = best_flight["Arrival Time"]
            arrival_weather = get_weather_at_arrival(arrival_time)
            arrival_time_formatted = datetime.strptime(arrival_time, "%Y-%m-%dT%H:%M:%S").strftime("%B %d, %Y, %H:%M %p")
            traffic_details = get_detailed_traffic_data()
            save_data_to_csv(all_flights, best_flight, arrival_weather, traffic_details)

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
    app.run(host='0.0.0.0', port=8080)
