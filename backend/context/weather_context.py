"""
Weather Context Provider — Real weather data from Open-Meteo API.
Free, no API key required. Replaces hardcoded "Clear" values.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger("context.weather")

# WMO Weather interpretation codes → human-readable strings
WMO_CODES: Dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}


class WeatherContextProvider:
    """Provides real-time weather data from Open-Meteo (free, no key needed)."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    GEO_URL = "https://ipinfo.io/json"

    def __init__(self):
        self._cached_location: Optional[Dict[str, Any]] = None

    async def get_location(self) -> Dict[str, Any]:
        """Get approximate location from IP address."""
        if self._cached_location:
            return self._cached_location

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(self.GEO_URL)
                data = resp.json()
                loc_str = data.get("loc", "0,0")
                lat, lon = loc_str.split(",")
                self._cached_location = {
                    "city": data.get("city", "Unknown"),
                    "region": data.get("region", ""),
                    "country": data.get("country", ""),
                    "lat": float(lat),
                    "lon": float(lon),
                }
                return self._cached_location
        except Exception as e:
            logger.warning(f"Location lookup failed: {e}")
            return {"city": "Unknown", "region": "", "country": "", "lat": 0.0, "lon": 0.0}

    async def get_weather(self) -> Dict[str, Any]:
        """Get current weather conditions."""
        location = await self.get_location()

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(self.FORECAST_URL, params={
                    "latitude": location["lat"],
                    "longitude": location["lon"],
                    "current": "temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m,apparent_temperature",
                    "wind_speed_unit": "kmh",
                    "timezone": "auto",
                })
                data = resp.json()
                current = data.get("current", {})

            weather_code = current.get("weather_code", -1)
            condition = WMO_CODES.get(weather_code, f"Code {weather_code}")

            return {
                "location": f"{location['city']}, {location['country']}",
                "temperature_c": current.get("temperature_2m"),
                "feels_like_c": current.get("apparent_temperature"),
                "condition": condition,
                "humidity_percent": current.get("relative_humidity_2m"),
                "wind_kmh": current.get("wind_speed_10m"),
            }
        except Exception as e:
            logger.warning(f"Weather lookup failed: {e}")
            return {
                "location": location.get("city", "Unknown"),
                "temperature_c": None,
                "condition": "Unavailable",
                "error": str(e),
            }
