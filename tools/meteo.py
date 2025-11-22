import requests
import json
from datetime import datetime, timedelta
import math

# ---CONFIG----------------------------
# Primary location for all services
LOCATION = "75014 Paris" 
OWM_API_KEY = "ba0a8f93af3983f6983f80fa04b2bd34" # see https://home.openweathermap.org/api_keys

# --- Date and Formatting Logic ---

def get_target_dates(dates_input: list = None) -> list:
    """
    Determines the target dates: Today, Tomorrow, and the upcoming weekend.
    Returns a sorted list of datetime.date objects.
    """
    today = datetime.now().date()
    target_dates = []

    if not dates_input:
        # Default dates: Today, Tomorrow, and upcoming weekend (SAM/DIM)
        target_dates.append(today)
        target_dates.append(today + timedelta(days=1)) # Tomorrow

        # Calculate the next Saturday
        days_until_saturday = (5 - today.weekday() + 7) % 7
        next_saturday = today + timedelta(days=days_until_saturday)
        
        # Add Saturday and Sunday if they aren't already Today or Tomorrow
        if next_saturday not in target_dates:
            target_dates.append(next_saturday)
        
        next_sunday = next_saturday + timedelta(days=1)
        if next_sunday not in target_dates:
            target_dates.append(next_sunday)
            
    else:
        # Custom dates logic (simplified: assumes current year)
        for date_str in dates_input:
            try:
                day, month = map(int, date_str.split('.'))
                target_date = today.replace(month=month, day=day)
                if target_date < today: # Assume next year if in the past
                     target_date = target_date.replace(year=today.year + 1)
                target_dates.append(target_date)
            except ValueError:
                print(f"Warning: Could not parse date '{date_str}'. Skipping.")
    
    # Remove duplicates and sort by date
    return sorted(list(set(target_dates)))

def format_date_french(date_obj: datetime.date) -> str:
    """Formats the date as 'SAM 15 NOV' using manual French abbreviations."""
    day_abbr = ['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM']
    month_abbr = ['JAN', 'FÉV', 'MAR', 'AVR', 'MAI', 'JUIN', 'JUIL', 'AOÛ', 'SEP', 'OCT', 'NOV', 'DÉC']
    
    day_of_week = day_abbr[date_obj.weekday()]
    day_of_month = date_obj.day
    month = month_abbr[date_obj.month - 1]
    
    return f"{day_of_week} {day_of_month} {month}"

#===============Services for weather============

def get_wttr_in_forecast():
    """Tries to get forecast from wttr.in (Primary, No Key)."""
    uri = f"https://wttr.in/{LOCATION.replace(' ', '+')}?format=j1"
    print("Attempting Primary Service (wttr.in)...")
    try:
        response = requests.get(uri, timeout=10)
        response.raise_for_status()
        return response.json(), "wttr.in"
    except Exception as e:
        print(f"Primary Service (wttr.in) failed: {e}")
        return None, None

def get_openweathermap_forecast():
    """Tries to get forecast from OpenWeatherMap (Secondary, Key Required)."""
    if OWM_API_KEY == "YOUR_OPENWEATHERMAP_API_KEY":
        print("Skipping Secondary Service: OWM API key is not set.")
        return None, None
        
    # OpenWeatherMap requires coordinates. Using Paris's Lat/Lon as a reliable default.
    LAT, LON = 48.8566, 2.3522 
    uri = f"https://api.openweathermap.org/data/2.5/forecast?lat={LAT}&lon={LON}&units=metric&appid={OWM_API_KEY}"
    print("Attempting Secondary Service (OpenWeatherMap)...")
    try:
        response = requests.get(uri, timeout=10)
        response.raise_for_status()
        return response.json(), "OpenWeatherMap"
    except Exception as e:
        print(f"Secondary Service (OpenWeatherMap) failed: {e}")
        return None, None

#==========================================
# ///////////// RUN
#===========================================

def process_forecast(raw_data: dict, service_name: str, target_dates: list):    
    print("-" * 30)
    print(f"SUCCESS: Data obtained from **{service_name}**.")
    print("-" * 30)

    for target_date_obj in target_dates:
        
        day_date_str = format_date_french(target_date_obj).upper()
        
        # Initialize
        mean_temp, mean_precip = None, None

        if service_name == "wttr.in":
            # wttr.in processing (9h and 12h points)
            date_key = target_date_obj.strftime('%Y-%m-%d')
            day_forecast = next((f for f in raw_data.get('weather', []) if f['date'] == date_key), None)
            
            if day_forecast:
                TARGET_HOURS = [9, 12] 
                hourly_data = [h for h in day_forecast.get('hourly', []) if int(h['time'][:2]) in TARGET_HOURS]
                if hourly_data:
                    temps = [float(h['tempC']) for h in hourly_data]
                    precip_probs = [int(h['chanceofrain']) for h in hourly_data]
                    
                    mean_temp = math.ceil(sum(temps) / len(temps)) if temps else 0
                    mean_precip = math.ceil(sum(precip_probs) / len(precip_probs)) if precip_probs else 0
            
        elif service_name == "OpenWeatherMap":
            # OWM processing (3-hour steps between 9h and 14h)
            date_key = target_date_obj.strftime('%Y-%m-%d')
            
            # Filter OWM list for the target day and 9:00:00 to 14:00:00
            hourly_data = [
                entry for entry in raw_data.get('list', []) 
                if entry['dt_txt'].startswith(date_key) and 
                   "09:00:00" <= entry['dt_txt'].split(' ')[1] <= "14:00:00"
            ]
            
            if hourly_data:
                # OWM temp is 'main.temp', precip prob is 'pop' (0 to 1)
                temps = [entry['main']['temp'] for entry in hourly_data]
                # 'pop' is probability of precipitation (0 to 1), convert to percentage
                precip_probs = [entry.get('pop', 0) * 100 for entry in hourly_data] 
                
                mean_temp = math.ceil(sum(temps) / len(temps)) if temps else 0
                mean_precip = math.ceil(sum(precip_probs) / len(precip_probs)) if precip_probs else 0


        # --- Output ---
        print(f"{day_date_str}")
        if mean_temp is not None and mean_precip is not None:
            print(f"T = {mean_temp} °C (in °C between 9h-14h)")
            print(f"P = {mean_precip} % (in % Precip Prob between 9h-14h)")
        else:
            print(f"Data for this date not available in the {service_name} forecast.")
        print("-" * 30)

#=============================================
# --- Main Execution Loop with Failover ---
#=============================================

def main_weather_check(dates_input: list = None):
    target_dates = get_target_dates(dates_input)

    # 1. First Primary Service OpenWeatherMap
    raw_data, service_name = get_openweathermap_forecast()

    if raw_data is None:
        # 2. Try Secondary Service (wttr.in)
        print("\nPrimary failed. Falling back...")
        raw_data, service_name = get_wttr_in_forecast()

    if raw_data is None:
        print("\nFATAL ERROR: Both primary and secondary services failed to provide data.")
        return
    
    process_forecast(raw_data, service_name, target_dates)

if __name__ == "__main__":
    main_weather_check()
    
    # Example for custom dates:
    # main_weather_check(dates_input=["22.12"])