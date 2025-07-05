import requests
import time
import os
import shlex
from datetime import datetime

# --- SET YOUR LOCATION AND UNITS HERE ---
LATITUDE = xx.xxxx   # Enter coordinates for your location
LONGITUDE = -xxxx.xxxx
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
    stations = requests.get(obs_url, timeout=10).json()['observationStations']
    return {
        'forecast_url': forecast_url,
        'stations': stations  # now a list
    }

def get_current_conditions(stations):
    # Try each station until one works with good data
    for station_url in stations:
        try:
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
            # If any key value is not None, assume this station is valid!
            if any(x is not None for x in [temp_c, humidity, wind_speed_mps, wind_dir, pressure_hpa]):
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
        except Exception:
            continue
    # fallback if all stations fail
    return {
        'datetime': time.strftime("%m/%d/%Y, %H:%M:%S", time.localtime()),
        'description': None,
        'temperature_c': None,
        'temperature_f': None,
        'humidity': None,
        'wind_speed_mps': None,
        'wind_speed_mph': None,
        'wind_direction': None,
        'wind_direction_cardinal': None,
        'pressure_hpa': None,
        'pressure_inhg': None
    }

def get_forecast(forecast_url):
    forecast = requests.get(forecast_url, timeout=10).json()
    periods = forecast['properties']['periods']

    # Always select the first three periods for flexibility
    label1, label2, label3 = None, None, None
    text1, text2, text3 = None, None, None

    if len(periods) > 0:
        label1 = periods[0]['name']
        text1 = periods[0]['detailedForecast']
    if len(periods) > 1:
        label2 = periods[1]['name']
        text2 = periods[1]['detailedForecast']
    if len(periods) > 2:
        label3 = periods[2]['name']
        text3 = periods[2]['detailedForecast']

    return (label1, text1), (label2, text2), (label3, text3)

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

def print_weather(current, period1, period2, period3):
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

    forecast_lines = [f"Forecast:\n"]
    if period1[0] and period1[1]:
        forecast_lines.append(f"{period1[0]}: {period1[1]}")
    if period2[0] and period2[1]:
        forecast_lines.append(f"{period2[0]}: {period2[1]}")
    # If you want a 3rd period, just uncomment the next line
    # if period3[0] and period3[1]:
    #     forecast_lines.append(f"{period3[0]}: {period3[1]}")
    forecast_block = "\n".join(forecast_lines)

    split_and_send_message(output1, send_meshtastic_message)
    split_and_send_message(forecast_block, send_meshtastic_message)

if __name__ == '__main__':
    try:
        endpoints = get_weather_json(LATITUDE, LONGITUDE)
        current = get_current_conditions(endpoints['stations'])
        period1, period2, period3 = get_forecast(endpoints['forecast_url'])
        print_weather(current, period1, period2, period3)
    except Exception as e:
        print("Error:", e)
