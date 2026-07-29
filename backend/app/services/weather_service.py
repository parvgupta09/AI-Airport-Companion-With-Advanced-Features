import logging
import requests
from app.core.config import OPENWEATHER_API_KEY

logger = logging.getLogger(__name__)

class WeatherService:

    def __init__(self):
        self.api_key = OPENWEATHER_API_KEY
        self.enabled = bool(self.api_key)
        self.base_url = "https://api.openweathermap.org/data/2.5/weather"

    def get_weather_for_destination(self, destination: str) -> str:
        if not self.enabled:
            logger.info(f"Fetching simulated weather for {destination}")
            return "Sunny, 25 degrees Celsius with clear skies."

        try:
            params = {
                "q" : destination,
                "appid" : self.api_key,
                "units" : "metric"
            }

            response = requests.get(self.base_url, params=params, timeout = 5)
            response.raise_for_status()
            data = response.json()

            temp_celsius = round(data["main"]["temp"])
            condition = data["weather"][0]["description"].capitalize()

        except requests.exceptions.RequestException as e:
            logger.warning(f"Error fetching weather for {destination}: {str(e)}")
            return "Weather information currently unavailable"
        except KeyError as e:
            logger.error(f"Unexpected JSON fromat from weather API: {str(e)}")
            return "Weather information currently unavailable"

weather_service = WeatherService()