from __future__ import annotations
import json
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Tuple, Optional

from app.database.postgres_models import TerminalCode, GateCode, FlightStatus

BASE_DIR = Path(__file__).resolve().parents[2]
STATIC_DIR = BASE_DIR/"data"/"static"

def _load_json(path: Path) -> list:
    with open(path, "r", encoding = "utf-8") as file:
        return json.load(file)
    
AIRLINES_DATA = _load_json(STATIC_DIR/"airlines.json")
AIRPORTS_DATA = _load_json(STATIC_DIR/"airports.json")
AIRCRAFT_DATA = _load_json(STATIC_DIR/"aircraft.json")
AIRPORT_LOOKUP = {airport["code"]:airport for airport in AIRPORTS_DATA}

class FlightGenerator:

    @staticmethod
    def _create_rng(seed: str) -> random.Random:
        return random.Random(seed)
    
    def _get_airport(self, airport_code: str) -> dict:
        airport = AIRPORT_LOOKUP.get(airport_code.upper())
        if not airport:
            raise ValueError(f"Airport code {airport_code} not found in data.")
        return airport
    
    def is_international(self, source: str, destination: str) -> bool:
        src = self._get_airport(source)
        dest = self._get_airport(destination)
        return src["country"] != dest["country"]
    

    def _choose_airline(self, is_international: bool, rng:random.Random) -> dict:
        if is_international:
            candidates = [a for a in AIRLINES_DATA if a["type"] in ("international", "both")]
        else:
            candidates = [a for a in AIRLINES_DATA if a["type"] in ("domestic", "both")]
        return rng.choice(candidates)
    
    def _generate_flight_number(self, airline_code: str, rng: random.Random) -> str:
        return f"{airline_code}{rng.randint(100, 9999)}"
    
    def _choose_aircraft(self, is_international: bool, rng: random.Random) -> str:
        if is_international:
            aircaft = [p for p in AIRCRAFT_DATA if p["type"] == "Wide Body"]
        else:
            aircaft = [p for p in AIRCRAFT_DATA if p["type"] == "Narrow Body"]
        return rng.choice(aircaft)["model"]
    
    def _assign_terminal(self, is_international: bool) -> TerminalCode:
        return TerminalCode.T2 if is_international else TerminalCode.T1
    
    def _assign_gate(self, terminal:TerminalCode, rng: random.Random) -> GateCode:
        if terminal == TerminalCode.T1:
            gate_num = rng.randint(1,5)
        else:
            gate_num = rng.randint(6,10)
        return GateCode(f"Gate {gate_num}")
    
    def _assign_baggage_belt(self, terminal: TerminalCode, rng: random.Random) -> str:
        belt_num = rng.randint(1,3)
        return f"{terminal.name.lower()}_baggage_belt_{belt_num}"
    

    def _calculate_boarding_time(self, departure_time: datetime) -> datetime:
        return departure_time - timedelta(minutes=45)
    
    def _calculate_arrival_time(self, departure_time: datetime, is_international: bool, rng: random.Random)-> datetime:
        if is_international:
            duration = timedelta(hours = rng.randint(5, 10), minutes=rng.choice([0, 15, 30, 45]))
        else:
            duration = timedelta(hours = rng.randint(1,3), minutes=rng.choice([0,20,30,40, 50]))
        return departure_time + duration
    
    def _generate_layover(self, source: str, destination: str, rng: random.Random) -> Tuple[bool, Optional[str]]:
        has_layover = rng.random() < 0.25
        if not has_layover:
            return False, None
        possible_airports = [airport["code"] for airport in AIRPORTS_DATA if airport["code"] not in (source, destination)]
        if not possible_airports:
            return False, None
        return True, rng.choice(possible_airports)
    
    def generate_flight(self, *, pnr: str, source: str, destination: str, departure_time: datetime, allow_layover: bool = True, leg_number: int = 1) -> dict[str, Any]:
        rng = self._create_rng(pnr)
        is_international = self.is_international(source, destination)
        airline = self._choose_airline(is_international, rng)
        flight_number = self._generate_flight_number(airline["code"], rng)
        aircraft = self._choose_aircraft(is_international, rng)
        terminal = self._assign_terminal(is_international)
        gate = self._assign_gate(terminal, rng)
        baggage_belt = self._assign_baggage_belt(terminal, rng)
        boarding_time = self._calculate_boarding_time(departure_time)
        arrival_time = self._calculate_arrival_time(departure_time, is_international, rng)
        
        if allow_layover:
            has_layover, layover_airport = self._generate_layover(source, destination, rng)
        else:
            has_layover, layover_airport = False, None

        return {
            "pnr": pnr,
            "leg_number": leg_number,
            "source": source,
            "destination": destination,
            "flight_number": flight_number,
            "airline": airline["name"],
            "aircraft": aircraft,

            "terminal": terminal,
            "gate": gate,
            
            "departure_time_utc": departure_time,
            "arrival_time_utc": arrival_time,
            "boarding_time_utc": boarding_time,
            "baggage_belt": baggage_belt,

            "delay_minutes" : 0,
            "gate_changed" : False,
            "boarding_announced" : False,
            "status": FlightStatus.SCHEDULED,
            "has_layover": has_layover,
            "layover_airport": layover_airport,
            "is_international": is_international,
            "thread_id": None
        }
    
flight_generator = FlightGenerator()