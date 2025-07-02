import requests
import os
import time

# NOTE: I give credit to ChatGPT for creating the majority of this code.

# --- SET YOUR LOCATION HERE ---
LATITUDE = xx.xxxx   # Example: Look up the coordinates for your zip code and plug the values in here.
LONGITUDE = -xx.xxxx

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
    wind_speed_mps = (p['windSpeed']['value'] / 3.6) if p['windSpeed']['value'] is not None else None # windSpe                                                                                                                              ed is in km/h
    wind_speed_mph = wind_speed_mps * 2.23694 if wind_speed_mps is not None else None
    wind_dir = p['windDirection']['value']
    wind_dir_cardinal = deg_to_compass(wind_dir) if wind_dir is not None else 'N/A'
    pressure_hpa = (p['barometricPressure']['value'] / 100) if p['barometricPressure']['value'] is not None els                                                                                                                              e None
    pressure_inhg = pressure_hpa * 0.02953 if pressure_hpa is not None else None
    desc = p['textDescription']
    # get date and time
    named_tuple = time.localtime() # get struct_time
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
    today, tonight = None, None
    for period in periods:
        name = period['name'].lower()
        if 'today' in name and not today:
            today = period['detailedForecast']
        elif 'tonight' in name and not tonight:
            tonight = period['detailedForecast']
        elif 'this afternoon' in name and not today:
            today = period['detailedForecast']
        elif 'overnight' in name and not tonight:
            tonight = period['detailedForecast']
    return today, tonight

def print_weather(current, today, tonight):
    def fmt(val, fstr):
        try:
            return fstr.format(val)
        except (TypeError, ValueError):
            return 'N/A'

    output1 = (
        f"Current Weather:\n\n"
        f"Date/Time: {current['datetime']}\n"
        f"Conditions: {current['description']}\n"
        f"Temperature: "
        f"{current['temperature_c']:.1f}°C / {current['temperature_f']:.1f}°F\n"
        f"Humidity: "
        f"{int(round(current['humidity'])) if current['humidity'] is not None else 'N/A'}%\n"
        f"Wind: "
        f"{current['wind_speed_mps']:.1f} m/s / {current['wind_speed_mph']:.1f} mph from "
        f"{current['wind_direction_cardinal']} ({current['wind_direction']:.0f}°)\n"
        f"Pressure: "
        f"{current['pressure_hpa']:.1f} hPa / {current['pressure_inhg']:.2f} inHg\n\n"
    )
    output2 = (
        f"Forecast:\n\n"
        f"Today: {today if today else 'N/A'}\n"
        f"Tonight: {tonight if tonight else 'N/A'}"

    )
    #print(output1)
    #print(output2)
    send_content1 = " ' " + output1 + " ' "
    send_content2 = " ' " + output2 + " ' "
    os.system("/usr/local/bin/meshtastic --ch-index 3 --sendtext" + send_content1)
    os.system("/usr/local/bin/meshtastic --ch-index 3 --sendtext" + send_content2)


if __name__ == '__main__':
    try:
        endpoints = get_weather_json(LATITUDE, LONGITUDE)
        current = get_current_conditions(endpoints['station_url'])
        today, tonight = get_forecast(endpoints['forecast_url'])
        print_weather(current, today, tonight)
    except Exception as e:
        print("Error:", e)
