"""
Streamable HTTP MCP server for weather reports via Open-Meteo (no API key required).
Run with: python server.py [--host HOST] [--port PORT]
"""

import argparse
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _wmo_description(code: int) -> str:
    return WMO_CODES.get(code, f"Unknown (WMO {code})")


async def _fetch(params: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(OPEN_METEO_URL, params=params)
        resp.raise_for_status()
        return resp.json()


mcp = FastMCP("weather", stateless_http=True)


@mcp.tool()
async def get_current_weather(latitude: float, longitude: float) -> str:
    """
    Return current weather conditions for the given coordinates.

    Args:
        latitude: Decimal latitude (-90 to 90).
        longitude: Decimal longitude (-180 to 180).
    """
    data = await _fetch(
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "precipitation",
                    "weather_code",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "surface_pressure",
                ]
            ),
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
        }
    )

    cur = data["current"]
    units = data["current_units"]
    tz = data.get("timezone", "UTC")

    lines = [
        f"Location : {latitude:.4f}°, {longitude:.4f}° ({tz})",
        f"Time     : {cur['time']}",
        f"Condition: {_wmo_description(cur['weather_code'])}",
        f"Temp     : {cur['temperature_2m']} {units['temperature_2m']} (feels like {cur['apparent_temperature']} {units['apparent_temperature']})",
        f"Humidity : {cur['relative_humidity_2m']} {units['relative_humidity_2m']}",
        f"Precip   : {cur['precipitation']} {units['precipitation']}",
        f"Wind     : {cur['wind_speed_10m']} {units['wind_speed_10m']} @ {cur['wind_direction_10m']}{units['wind_direction_10m']}",
        f"Pressure : {cur['surface_pressure']} {units['surface_pressure']}",
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_forecast(latitude: float, longitude: float, days: int = 7) -> str:
    """
    Return an hourly weather forecast for the given coordinates.

    Args:
        latitude: Decimal latitude (-90 to 90).
        longitude: Decimal longitude (-180 to 180).
        days: Number of forecast days (1–16, default 7).
    """
    days = max(1, min(days, 16))

    data = await _fetch(
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                    "sunrise",
                    "sunset",
                ]
            ),
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "timezone": "auto",
            "forecast_days": days,
        }
    )

    daily = data["daily"]
    units = data["daily_units"]
    tz = data.get("timezone", "UTC")

    header = f"{'Date':<12} {'Condition':<25} {'Min':>7} {'Max':>7} {'Precip':>8} {'Wind Max':>10}"
    rows = [
        f"Forecast for {latitude:.4f}°, {longitude:.4f}° ({tz}) — next {days} day(s)",
        header,
        "-" * len(header),
    ]

    for i, date in enumerate(daily["time"]):
        condition = _wmo_description(daily["weather_code"][i])
        t_min = f"{daily['temperature_2m_min'][i]}{units['temperature_2m_min']}"
        t_max = f"{daily['temperature_2m_max'][i]}{units['temperature_2m_max']}"
        precip = f"{daily['precipitation_sum'][i]}{units['precipitation_sum']}"
        wind = f"{daily['wind_speed_10m_max'][i]}{units['wind_speed_10m_max']}"
        rows.append(f"{date:<12} {condition:<25} {t_min:>7} {t_max:>7} {precip:>8} {wind:>10}")

    return "\n".join(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Weather MCP server (streamable HTTP)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    mcp.settings.host = args.host
    mcp.settings.port = args.port
    mcp.run(transport="streamable-http")

