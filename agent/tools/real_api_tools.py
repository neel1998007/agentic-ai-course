"""
Real API tools with caching, error handling, and rate limiting.
Production-grade external API integration.
"""

import logging
import requests
import time
from datetime import datetime, timedelta
from typing import Optional
import os

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────
# SIMPLE IN-MEMORY CACHE
# ─────────────────────────────────────────────────────

class SimpleCache:
    """
    In-memory cache with TTL (time-to-live).
    In production, use Redis or Memcached.
    For learning, this is enough.
    """
    def __init__(self):
        self._cache = {}
    
    def get(self, key: str) -> Optional[str]:
        """Get from cache if not expired."""
        if key in self._cache:
            value, expiry = self._cache[key]
            if datetime.now() < expiry:
                logger.debug(f"Cache HIT: {key}")
                return value
            else:
                logger.debug(f"Cache EXPIRED: {key}")
                del self._cache[key]
        logger.debug(f"Cache MISS: {key}")
        return None
    
    def set(self, key: str, value: str, ttl_seconds: int):
        """Set cache with expiry time."""
        expiry = datetime.now() + timedelta(seconds=ttl_seconds)
        self._cache[key] = (value, expiry)
        logger.debug(f"Cache SET: {key} (TTL: {ttl_seconds}s)")
    
    def clear(self):
        """Clear all cache."""
        self._cache.clear()
        logger.info("Cache cleared")


# Global cache instance
cache = SimpleCache()


# ─────────────────────────────────────────────────────
# API CALL WRAPPER WITH RETRY + RATE LIMIT HANDLING
# ─────────────────────────────────────────────────────

def call_api_with_retry(
    url: str,
    params: dict = None,
    max_retries: int = 3,
    timeout: int = 10
) -> Optional[dict]:
    """
    Calls external API with intelligent retry logic.
    
    Handles:
    - Network errors (timeout, connection refused)
    - Rate limiting (429)
    - Server errors (500, 503)
    - Returns None on unrecoverable errors
    """
    for attempt in range(max_retries):
        try:
            logger.debug(f"API call attempt {attempt + 1}: {url}")
            
            response = requests.get(
                url,
                params=params,
                timeout=timeout
            )
            
            # SUCCESS
            if response.status_code == 200:
                return response.json()
            
            # RATE LIMIT
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(
                    f"Rate limit hit. Waiting {retry_after}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(retry_after)
                continue
            
            # SERVER ERROR (retryable)
            elif response.status_code in [500, 502, 503, 504]:
                wait = 2 ** attempt  # exponential backoff
                logger.warning(
                    f"Server error {response.status_code}. "
                    f"Waiting {wait}s..."
                )
                time.sleep(wait)
                continue
            
            # CLIENT ERROR (don't retry)
            elif response.status_code in [400, 401, 403, 404]:
                logger.error(
                    f"Client error {response.status_code}: {response.text}"
                )
                return None
            
            # UNKNOWN ERROR
            else:
                logger.error(
                    f"Unexpected status {response.status_code}: {response.text}"
                )
                return None
        
        except requests.Timeout:
            wait = 2 ** attempt
            logger.warning(f"Request timeout. Waiting {wait}s...")
            time.sleep(wait)
        
        except requests.ConnectionError as e:
            wait = 2 ** attempt
            logger.warning(f"Connection error: {e}. Waiting {wait}s...")
            time.sleep(wait)
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None
    
    logger.error(f"All {max_retries} API retry attempts failed")
    return None


# ─────────────────────────────────────────────────────
# TOOL 1: CURRENCY CONVERTER
# ─────────────────────────────────────────────────────

CURRENCY_CONVERTER_SCHEMA = {
    "name": "convert_currency",
    "description": (
        "Converts an amount from one currency to another using live exchange rates. "
        "Supports major currencies including INR, USD, EUR, GBP, CAD, AUD. "
        "Use this for: currency conversion, price comparison across countries, "
        "calculating international costs."
    ),
    "parameters": {
        "conversion": {
            "type": "string",
            "description": (
                "Format: 'AMOUNT FROM_CURRENCY to TO_CURRENCY'. "
                "Examples: '1000 INR to USD', '50 USD to EUR', '5000 INR to CAD'. "
                "Currency codes must be 3 letters (ISO 4217 standard)."
            ),
            "required": True,
        }
    },
    "examples": [
        {"input": "1000 INR to USD", "output": "1000 INR = 12.00 USD"},
        {"input": "50 USD to EUR", "output": "50 USD = 46.50 EUR"},
    ]
}


def convert_currency(conversion: str) -> str:
    """
    Converts currency using live exchange rates from ExchangeRate-API.
    Free API, no auth needed, 1500 requests/month free tier.
    
    Input : "AMOUNT FROM to TO" (e.g., "1000 INR to USD")
    Output: Conversion result or error message
    """
    logger.info(f"convert_currency called: '{conversion}'")
    
    # Parse input
    try:
        parts = conversion.strip().split()
        if len(parts) != 4 or parts[2].lower() != "to":
            return (
                "Format error. Use: 'AMOUNT FROM to TO'. "
                "Example: '1000 INR to USD'"
            )
        
        amount_str, from_curr, _, to_curr = parts
        amount = float(amount_str)
        from_curr = from_curr.upper()
        to_curr = to_curr.upper()
        
    except ValueError:
        return "Invalid amount. Must be a number."
    except Exception as e:
        return f"Parse error: {e}"
    
    # Check cache first
    cache_key = f"rate_{from_curr}_{to_curr}"
    cached_rate = cache.get(cache_key)
    
    if cached_rate:
        rate = float(cached_rate)
        result = amount * rate
        logger.info(f"Used cached rate: 1 {from_curr} = {rate} {to_curr}")
    else:
        # Call live API
        url = f"https://api.exchangerate-api.com/v4/latest/{from_curr}"
        
        data = call_api_with_retry(url, timeout=5)
        
        if not data:
            return (
                f"Currency conversion failed. Could not fetch rates for {from_curr}. "
                "API might be down or rate limited."
            )
        
        # Validate response structure
        if "rates" not in data or to_curr not in data["rates"]:
            return (
                f"Currency '{to_curr}' not found in exchange rates. "
                f"Supported currencies: {list(data.get('rates', {}).keys())[:10]}..."
            )
        
        rate = data["rates"][to_curr]
        result = amount * rate
        
        # Cache the rate for 1 hour
        cache.set(cache_key, str(rate), ttl_seconds=3600)
        logger.info(f"Fetched fresh rate: 1 {from_curr} = {rate} {to_curr}")
    
    return (
        f"{amount:,.2f} {from_curr} = {result:,.2f} {to_curr} "
        f"(Rate: 1 {from_curr} = {rate:.4f} {to_curr})"
    )


# ─────────────────────────────────────────────────────
# TOOL 2: WEATHER LOOKUP
# ─────────────────────────────────────────────────────

WEATHER_SCHEMA = {
    "name": "get_weather",
    "description": (
        "Gets current weather for any city in India or worldwide. "
        "Returns temperature, conditions, humidity, and feels-like temperature. "
        "Use this for: weather queries, travel planning, climate questions."
    ),
    "parameters": {
        "city": {
            "type": "string",
            "description": (
                "City name. For Indian cities, just the name is enough "
                "(e.g., 'Mumbai', 'Delhi', 'Bangalore'). "
                "For international cities, include country "
                "(e.g., 'London,UK', 'New York,US')."
            ),
            "required": True,
        }
    },
    "examples": [
        {"input": "Mumbai", "output": "Mumbai: 32°C, Humid, Feels like 38°C"},
        {"input": "Delhi", "output": "Delhi: 28°C, Clear, Feels like 30°C"},
    ]
}


def get_weather(city: str) -> str:
    """
    Gets current weather using OpenWeatherMap API.
    Free tier: 1000 calls/day, 60 calls/min.
    
    Input : city name
    Output: weather description or error message
    """
    logger.info(f"get_weather called: '{city}'")
    
    # Get API key from environment
    api_key = os.environ.get("OPENWEATHER_API_KEY")
    if not api_key:
        return (
            "Weather API not configured. "
            "Add OPENWEATHER_API_KEY to your .env file. "
            "Get free key from: https://openweathermap.org/api"
        )
    
    city = city.strip()
    if not city:
        return "City name cannot be empty"
    
    # Check cache first (weather cached for 30 minutes)
    cache_key = f"weather_{city.lower()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    # Call live API
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "q": city,
        "appid": api_key,
        "units": "metric"  # Celsius
    }
    
    data = call_api_with_retry(url, params=params, timeout=5)
    
    if not data:
        return (
            f"Weather lookup failed for '{city}'. "
            "API might be down, rate limited, or city not found."
        )
    
    # Validate response structure
    try:
        temp = data["main"]["temp"]
        feels_like = data["main"]["feels_like"]
        humidity = data["main"]["humidity"]
        description = data["weather"][0]["description"].capitalize()
        city_name = data["name"]
        
        result = (
            f"{city_name}: {temp:.0f}°C, {description}. "
            f"Feels like {feels_like:.0f}°C. Humidity {humidity}%."
        )
        
        # Cache for 30 minutes
        cache.set(cache_key, result, ttl_seconds=1800)
        logger.info(f"Weather fetched and cached: {city_name}")
        
        return result
        
    except KeyError as e:
        logger.error(f"Unexpected API response structure: missing {e}")
        return (
            f"Weather data for '{city}' is incomplete. "
            "API response format may have changed."
        )
    except Exception as e:
        logger.error(f"Error parsing weather data: {e}")
        return f"Error processing weather data for '{city}'"