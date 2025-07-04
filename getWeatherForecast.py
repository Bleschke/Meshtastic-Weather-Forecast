import requests
import time
import os
import shlex
from datetime import datetime

# --- SET YOUR LOCATION AND UNITS HERE ---
LATITUDE = xx.xxxx   # Enter coordinates for your location
LONGITUDE = -xx.xxxx
UNITS = 'imperial'   # 'imperial' or 'metric'

def deg_to_compass(num):
    if num is None:
        return 'N/A'
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    ix = int((num/22.5)+0.5)
    return dirs[ix % 16]

def get_weather_json(lat, lon):
    points_url = f'https://api.weather.gov/points/{lat},{lon}'
    points = requests.get(points_url, timeout=10).json()
    obs_url = points['properties']['observationStations']
    forecast_url = points['properties']['forecast']
    station_url = requests.get(obs_url, timeout=10).json()['observationStations'][0]
    return {
        'forecast_url': forecast_url,
        'station_url': station_url
    }

def get_current_conditions(station_url):
    obs = requests.get(f"{station_url}/observations/latest", timeout=10).json()
    p = obs['properties']
    temp_c = p['temperature']['value']
    temp_f = temp_c * 9/5 + 32 if temp_c is not None else None
    humidity = p['relativeHumidity']['value']
    wind_speed_mps = (p['windSpeed']['value'] / 3.6) if p['windSpeed']['value'] is not None else None
    wind_speed_mph = wind_speed_mps * 2.23694 if wind_speed_mps is not None else None
    wind_dir = p['windDirection']['value']
    wind_dir_cardinal = deg_to_compass(wind_dir) if wind_dir is not None else 'N/A'
    pressure_hpa = (p['barometricPressure']['value'] / 100) if p['barometricPressure']['value'] is not None else None
    pressure_inhg = pressure_hpa * 0.02953 if pressure_hpa is not None else None
    desc = p['textDescription']
    # get date and time
    named_tuple = time.localtime()
    time_string = time.strftime("%m/%d/%Y, %H:%M:%S", named_tuple)

    return {
        'datetime': time_string,
        'description': desc,
        'temperature_c': temp_c,
        'temperature_f': temp_f,
        'humidity': humidity,
        'wind_speed_mps': wind_speed_mps,
        'wind_speed_mph': wind_speed_mph,
        'wind_direction': wind_dir,
        'wind_direction_cardinal': wind_dir_cardinal,
        'pressure_hpa': pressure_hpa,
        'pressure_inhg': pressure_inhg
    }

def get_forecast(forecast_url):
    forecast = requests.get(forecast_url, timeout=10).json()
    periods = forecast['properties']['periods']
    # We'll find the index for "today" or "tonight", then get next period(s) as needed
    today_idx = tonight_idx = None
    for i, period in enumerate(periods):
        name = period['name'].lower()
        if ('today' in name or 'this afternoon' in name) and today_idx is None:
            today_idx = i
            break
        elif 'tonight' in name and tonight_idx is None:
            tonight_idx = i
            break
    # If it's before 5pm, show today+tonight; after 5pm, show tonight+next period (tomorrow)
    now = datetime.now()
    hour = now.hour
    if 0 <= hour < 17 and today_idx is not None:  # 12:00 AM to 4:59 PM
        today = periods[today_idx]['detailedForecast']
        today_label = periods[today_idx]['name']
        if today_idx + 1 < len(periods):
            tonight = periods[today_idx+1]['detailedForecast']
            tonight_label = periods[today_idx+1]['name']
        else:
            tonight = None
            tonight_label = 'Tonight'
        tomorrow = None
        tomorrow_label = None
    elif tonight_idx is not None:  # 5:00 PM to 11:59 PM
        tonight = periods[tonight_idx]['detailedForecast']
        tonight_label = periods[tonight_idx]['name']
        if tonight_idx + 1 < len(periods):
            tomorrow = periods[tonight_idx+1]['detailedForecast']
            tomorrow_label = periods[tonight_idx+1]['name']
        else:
            tomorrow = None
            tomorrow_label = 'Tomorrow'
        today = None
        today_label = None
    else:
        # fallback if periods are missing
        today = tonight = tomorrow = None
        today_label = tonight_label = tomorrow_label = None
    return (today_label, today), (tonight_label, tonight), (tomorrow_label, tomorrow)

def split_and_send_message(message, send_func, max_length=200, delay=1):
    words = message.split(' ')
    chunk = ""
    for word in words:
        test_len = len(chunk) + (1 if chunk else 0) + len(word)
        if test_len > max_length:
            send_func(chunk)
            time.sleep(delay)
            chunk = word
        else:
            if chunk:
                chunk += ' ' + word
            else:
                chunk = word
    if chunk:
        send_func(chunk)
        time.sleep(delay)

def send_meshtastic_message(message):
    quoted_message = shlex.quote(message)
    # Uncomment below to actually send via Meshtastic
    os.system(f"/usr/local/bin/meshtastic --ch-index 3 --sendtext {quoted_message}")
    #print(f"Would send: {quoted_message}")  # For testing

def print_weather(current, today_pair, tonight_pair, tomorrow_pair):
    def fmt(val, fstr):
        try:
            return fstr.format(val)
        except (TypeError, ValueError):
            return 'N/A'
    def safe(val):
        return val if val is not None else 'N/A'

    if UNITS == 'imperial':
        temp = f"{fmt(current.get('temperature_f'), '{:.1f}')}°F"
        wind = f"{fmt(current.get('wind_speed_mph'), '{:.1f}')} mph"
        pressure = f"{fmt(current.get('pressure_inhg'), '{:.2f}')} inHg"
    else:
        temp = f"{fmt(current.get('temperature_c'), '{:.1f}')}°C"
        wind = f"{fmt(current.get('wind_speed_mps'), '{:.1f}')} m/s"
        pressure = f"{fmt(current.get('pressure_hpa'), '{:.1f}')} hPa"

    output1 = (
        f"Current Weather:\n\n"
        f"Date/Time: {current['datetime']}\n"
        f"Description: {safe(current.get('description'))}\n"
        f"Temperature: {temp}\n"
        f"Humidity: {int(round(current['humidity'])) if current.get('humidity') is not None else 'N/A'}%\n"
        f"Wind: {wind} from {safe(current.get('wind_direction_cardinal'))} ({fmt(current.get('wind_direction'), '{:.0f}')}°)\n"
        f"Pressure: {pressure}\n\n"
    )

    # Decide which forecast blocks to show
    forecast_lines = ["Forecast:\n"]
    if today_pair[0] and today_pair[1]:  # label, forecast
        forecast_lines.append(f"{today_pair[0]}: {today_pair[1]}")
    if tonight_pair[0] and tonight_pair[1]:
        forecast_lines.append(f"{tonight_pair[0]}: {tonight_pair[1]}")
    if tomorrow_pair[0] and tomorrow_pair[1]:
        forecast_lines.append(f"{tomorrow_pair[0]}: {tomorrow_pair[1]}")
    forecast_block = "\n".join(forecast_lines)

    split_and_send_message(output1, send_meshtastic_message)
    split_and_send_message(forecast_block, send_meshtastic_message)

if __name__ == '__main__':
    try:
        endpoints = get_weather_json(LATITUDE, LONGITUDE)
        current = get_current_conditions(endpoints['station_url'])
        today_pair, tonight_pair, tomorrow_pair = get_forecast(endpoints['forecast_url'])
        print_weather(current, today_pair, tonight_pair, tomorrow_pair)
    except Exception as e:
        print("Error:", e)
