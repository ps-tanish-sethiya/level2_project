"""
Live Weather MCP Tool leveraging ip-api.com and Open-Meteo REST APIs.
"""

import logging
import urllib.request
import json
from typing import Dict, Any

logger = logging.getLogger("devsentinel.tools.live_weather")


def get_weather_by_ip(ip_address: str = "auto") -> Dict[str, Any]:
    """
    Get current weather information by IP address using IP geolocation and Open-Meteo API.
    
    Args:
        ip_address: Target IP address or 'auto' for current machine IP location.
        
    Returns:
        Structured dict with city, region, country, temperature, windspeed, and weather condition.
    """
    try:
        clean_ip = str(ip_address).strip().lower()
        if clean_ip in ("auto", "me", "current", "", "self"):
            ip_url = "http://ip-api.com/json/"
        else:
            ip_url = f"http://ip-api.com/json/{clean_ip}"

        req = urllib.request.Request(ip_url, headers={"User-Agent": "DevSentinel/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo = json.loads(resp.read().decode("utf-8"))

        if geo.get("status") == "fail":
            return {"error": f"Failed to geolocate IP address '{ip_address}': {geo.get('message')}"}

        lat = geo.get("lat")
        lon = geo.get("lon")
        city = geo.get("city", "Unknown City")
        region = geo.get("regionName", "")
        country = geo.get("country", "")

        weather_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
        w_req = urllib.request.Request(weather_url, headers={"User-Agent": "DevSentinel/2.0"})
        with urllib.request.urlopen(w_req, timeout=5) as w_resp:
            w_data = json.loads(w_resp.read().decode("utf-8"))

        curr = w_data.get("current_weather", {})
        temp_c = curr.get("temperature")
        wind = curr.get("windspeed")
        w_code = curr.get("weathercode", 0)

        # Map Open-Meteo WMO weather codes to human text
        weather_descriptions = {
            0: "Clear sky ☀️",
            1: "Mainly clear 🌤️",
            2: "Partly cloudy ⛅",
            3: "Overcast ☁️",
            45: "Fog 🌫️",
            48: "Depositing rime fog 🌫️",
            51: "Light drizzle 🌧️",
            61: "Slight rain 🌧️",
            63: "Moderate rain 🌧️",
            65: "Heavy rain 🌧️",
            71: "Slight snow ❄️",
            95: "Thunderstorm 🌩️"
        }
        condition = weather_descriptions.get(w_code, "Cloudy/Clear 🌤️")

        return {
            "query_ip": ip_address,
            "ip": geo.get("query"),
            "location": f"{city}, {region}, {country}",
            "temperature_celsius": temp_c,
            "temperature_fahrenheit": round(temp_c * 9/5 + 32, 1) if temp_c is not None else None,
            "condition": condition,
            "windspeed_kmh": wind,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error fetching weather by IP: {e}")
        return {"error": f"Weather API error: {str(e)}"}
