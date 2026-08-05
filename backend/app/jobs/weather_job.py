# We use redis here to store the data of the 2hrs of weather data and sets the TTL as 2hrs so that we can get rid of stale data and get the new data into the redis
# We does not use websocket as we dont need the instantaneous weather change

import logging
import json
import httpx
from datetime import datetime, timezone
from sqlalchemy import text
from app.database.postgres_session import SessionLocal
from app.core.config import OPENWEATHER_API_KEY
from app.core.redis_client import get_redis

logger = logging.getLogger(__name__)

WEATHER_KEY_PREFIX = "weather"
WEATHER_TTL_SECONDS = 7200

async def fetch_airport_weather() -> dict[str, dict]:
    """
    It dynamically fetches the origin and destination cities from active flight, queries OpenWeatherMap, and caches the weather payload in Redis
    """

    if not OPENWEATHER_API_KEY:
        logger.warning("OPENWEATHER_API_KEY is missing in configuration. Skipping weather job.")
        return {}

    url = "https://api.openweather.org/data/2.5/weather"
    db = SessionLocal()
    redis_client = await get_redis()
    cached_summary: dict[str, dict] = {}

    try:
        cities_to_fetch: set[str] = set()

        destinations = db.execute(
            text("SELECT DISTINCT destination FROM flights WHERE status != 'COMPLETED'")
        ).scalars().all()

        sources = db.execute(
            text("SELECT DISTINCT source FROM flights WHERE status != 'COMPLETED'")
        ).scalars().all()

        for city in destinations + sources:
            if city and isinstance(city, str) and city.strip():
                cities_to_fetch.add(city.strip())

        if not cities_to_fetch:
            logger.info("No active flight cities found in DB. Skipping weather fetch.")
            return {}

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            for city in cities_to_fetch:
                params = {
                    "q" : city,
                    "appid" : OPENWEATHER_API_KEY,
                    "units" : "metric"
                }
                try:
                    res = await http_client.get(url, params = params)
                    if res.status_code == 200:
                        data = res.json()
                        payload  = {
                            "temp" : round(data["main"]["temp"], 1),
                            "humidity" : data["main"]["humidity"],
                            "condition": data["weather"][0]["description"].title(),
                            "updated_at" : datetime.now(timezone.utc).isoformat()
                        }

                        redis_key = f"{WEATHER_KEY_PREFIX}{city.lower()}"
                        await redis_client.set(
                            redis_key,
                            json.dumps(payload),
                            ex = WEATHER_TTL_SECONDS
                        )
                        cached_summary[city] = payload
                    else:
                        logger.warning(f"Weather API returned {res.status_code}")
                except Exception as req_err:
                    logger.warning(f"HTTP request failed for city {city} : {str(req_err)}")

        logger.info(f"Redis weather cache refreshed for {len(cached_summary)} cities: {list(cached_summary.keys())}")
        return cached_summary

    except Exception as e:
        logger.error(f"Failed to execute weather caching job: {str(e)}", exc_info=True)
        return cached_summary

    finally:
        db.close()