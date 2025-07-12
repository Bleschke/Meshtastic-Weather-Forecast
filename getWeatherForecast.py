import requests
import time
import os
import shlex
import re
from datetime import datetime

# --- SETTINGS ---
# --- SET YOUR LOCATION AND UNITS HERE ---
LATITUDE = xx.xxxx   # Enter coordinates for your location
LONGITUDE = -xxxx.xxxx
UNITS = 'imperial'   # 'imperial' or 'metric'
INCLUDE_FORECAST = True # Set to False to omit forecast output
FORECAST_EMOJI = True   # True for emoji-style forecast, False for text

def deg_to_compass(num):
    if num is None:
        return 'N/A'
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    arrows = ['⬆️','↗️','➡️','↘️','⬇️','↙️','⬅️','↖️','⬆️','⬆️','⬆️','⬆️','⬆️','⬆️','⬆️','⬆️']
    ix = int((num/22.5)+0.5)
    return dirs[ix % 16], arrows[ix % 16]

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
            wind_dir_cardinal, wind_dir_arrow = deg_to_compass(wind_dir) if wind_dir is not None else ('N/A', '')
            pressure_hpa = (p['barometricPressure']['value'] / 100) if p['barometricPressure']['value'] is not None else None
            pressure_inhg = pressure_hpa * 0.02953 if pressure_hpa is not None else None
            desc = p['textDescription']
            named_tuple = time.localtime()
            time_string = time.strftime("%m/%d/%Y, %H:%M:%S", named_tuple)
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
                    'wind_direction_arrow': wind_dir_arrow,
                    'pressure_hpa': pressure_hpa,
                    'pressure_inhg': pressure_inhg
                }
        except Exception:
            continue
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
        'wind_direction_arrow': '',
        'pressure_hpa': None,
        'pressure_inhg': None
    }

def get_forecast(forecast_url):
    forecast = requests.get(forecast_url, timeout=10).json()
    periods = forecast['properties']['periods']
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

def parse_forecast_to_emoji(label, forecast_text):
    if not forecast_text:
        return f"{label}: N/A"
    # Weather icon based on text
    icons = [
        ('sunny', '☀️'), ('mostly sunny', '🌤️'), ('clear', '🌙'),
        ('cloudy', '☁️'), ('mostly cloudy', '⛅'), ('partly sunny', '⛅'),
        ('partly cloudy', '⛅'), ('showers', '🌦️'), ('rain', '🌧️'),
        ('snow', '❄️'), ('thunder', '⛈️'), ('fog', '🌫️'), ('wind', '🍃')
    ]
    icon = ''
    for key, sym in icons:
        if key in forecast_text.lower():
            icon = sym
            break
    if not icon:
        icon = '🌈'

    # High, Low, Rain chance
    high = re.search(r'[Hh]igh(?: near)? (\d+)', forecast_text)
    low = re.search(r'[Ll]ow(?: around)? (\d+)', forecast_text)
    rain = re.search(r'(\d+)% chance of rain', forecast_text)
    rain_alt = re.search(r'Chance of precipitation is (\d+)%', forecast_text)
    if not high:
        high = re.search(r'[Hh]igh of (\d+)', forecast_text)
    if not low:
        low = re.search(r'[Ll]ow of (\d+)', forecast_text)

    high_val = high.group(1) if high else ''
    low_val = low.group(1) if low else ''
    rain_val = rain.group(1) if rain else (rain_alt.group(1) if rain_alt else '')

    # Wind extraction: Match many phrase variations
    wind = re.search(r'[Ww]ind[s]?[^a-zA-Z0-9]+([NSEW]+)?[^0-9]*(\d{1,3}) ?mph', forecast_text)
    wind_alt = re.search(r'[Ff]rom the ([NSEW]+)[^0-9]*(\d{1,3}) ?mph', forecast_text)
    wind_dir = wind_speed = ''
    if wind:
        wind_dir = wind.group(1) if wind.group(1) else ''
        wind_speed = wind.group(2)
    elif wind_alt:
        wind_dir = wind_alt.group(1)
        wind_speed = wind_alt.group(2)
    # Try to pick up any phrase like "at 10 mph"
    if not wind_speed:
        wind_speed_search = re.search(r'at (\d{1,3}) ?mph', forecast_text)
        if wind_speed_search:
            wind_speed = wind_speed_search.group(1)

    # Wind direction emoji map
    dir_emojis = {
        'N': '⬆️', 'NE': '↗️', 'E': '➡️', 'SE': '↘️',
        'S': '⬇️', 'SW': '↙️', 'W': '⬅️', 'NW': '↖️',
        'NNE': '⬆️', 'ENE': '↗️', 'ESE': '↘️', 'SSE': '↙️',
        'SSW': '⬇️', 'WSW': '⬅️', 'WNW': '↖️', 'NNW': '⬆️'
    }
    wind_arrow = dir_emojis.get(wind_dir, '')

    units_temp = "C" if UNITS == "metric" else "F"
    units_wind = "m/s" if UNITS == "metric" else "mph"

    emoji = f"{label}: {icon}"
    if high_val:
        emoji += f", ⬆️ {high_val} {units_temp}"
    if low_val:
        emoji += f", ⬇️ {low_val} {units_temp}"
    if rain_val:
        emoji += f", 💧{rain_val}%"
    if wind_speed:
        emoji += f", 🍃 {wind_arrow} {wind_speed} {units_wind}"

    return emoji

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
    # os.system(f"/usr/local/bin/meshtastic --ch-index 3 --sendtext {quoted_message}")
    print(f"Would send: {quoted_message}")  # For testing

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

    split_and_send_message(output1, send_meshtastic_message)

    if INCLUDE_FORECAST:
        forecast_lines = [f"Forecast:"]
        periods = [period1, period2]
        for label, text in periods:
            if label and text:
                if FORECAST_EMOJI:
                    forecast_lines.append(parse_forecast_to_emoji(label, text))
                else:
                    forecast_lines.append(f"{label}: {text}")
        forecast_block = "\n".join(forecast_lines)
        split_and_send_message(forecast_block, send_meshtastic_message)

if __name__ == '__main__':
    try:
        endpoints = get_weather_json(LATITUDE, LONGITUDE)
        current = get_current_conditions(endpoints['stations'])
        period1, period2, period3 = get_forecast(endpoints['forecast_url'])
        print_weather(current, period1, period2, period3)
    except Exception as e:
        print("Error:", e)

