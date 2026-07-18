import random
from datetime import datetime, timezone, timedelta

from app.database.postgres_models import (
    Flight,
    FlightStatus,
    TerminalCode,
    GateCode,
)

class FlightSimulator:

    @staticmethod
    def process_flight(flight: Flight) -> bool:
        modified = False
        now = datetime.now(timezone.utc)

        # Ignore if flight is already finished
        if flight.status in (
            FlightStatus.COMPLETED,
            FlightStatus.CANCELLED,
        ):
            return False

        # Ensure the time zones
        departure_time = (
            flight.departure_time_utc.replace(tzinfo=timezone.utc)
            if flight.departure_time_utc.tzinfo is None
            else flight.departure_time_utc
        )

        arrival_time = (
            flight.arrival_time_utc.replace(tzinfo=timezone.utc)
            if flight.arrival_time_utc.tzinfo is None
            else flight.arrival_time_utc
        )

        boarding_time = (
            flight.boarding_time_utc.replace(tzinfo=timezone.utc)
            if flight.boarding_time_utc.tzinfo is None
            else flight.boarding_time_utc
        )

        time_until_departure = departure_time - now

        rng = random.Random(f"{flight.pnr}_chaos_engine")

        gate_roll = rng.random()
        delay_roll = rng.random()
        cancellation_roll = rng.random()

        destined_for_gate_change = gate_roll < 0.15
        destined_for_delay = delay_roll < 0.10
        destined_for_cancellation = cancellation_roll < 0.005

        # Cancellation only before the boarding starts
        if (
            destined_for_cancellation
            and flight.status == FlightStatus.SCHEDULED
            and timedelta(hours=2) >= time_until_departure >= timedelta(hours=1)
        ):
            flight.status = FlightStatus.CANCELLED
            modified = True
            return modified

        # Gate change only between 2 hours 30 minutes and 45 minutes before departure.
        if (
            destined_for_gate_change
            and not flight.gate_changed
            and timedelta(hours=2, minutes=30)
            >= time_until_departure
            >= timedelta(minutes=45)
        ):

            if flight.terminal == TerminalCode.T1:
                available = [
                    GateCode.GATE_1,
                    GateCode.GATE_2,
                    GateCode.GATE_3,
                    GateCode.GATE_4,
                    GateCode.GATE_5,
                ]
            else:
                available = [
                    GateCode.GATE_6,
                    GateCode.GATE_7,
                    GateCode.GATE_8,
                    GateCode.GATE_9,
                    GateCode.GATE_10,
                ]

            available = [g for g in available if g != flight.gate]

            flight.gate = rng.choice(available)
            flight.gate_changed = True
            modified = True

        # Delay only between 3 hours and 2 hours before departure
        if (
            destined_for_delay
            and flight.delay_minutes == 0
            and timedelta(hours=3)
            >= time_until_departure
            >= timedelta(hours=2)
        ):

            delay = rng.choice([15, 30, 45, 60, 90])

            flight.delay_minutes = delay

            flight.departure_time_utc += timedelta(minutes=delay)
            flight.arrival_time_utc += timedelta(minutes=delay)
            flight.boarding_time_utc += timedelta(minutes=delay)

            departure_time += timedelta(minutes=delay)
            arrival_time += timedelta(minutes=delay)
            boarding_time += timedelta(minutes=delay)

            modified = True

        # Status checks in chrological order

        if now >= arrival_time + timedelta(minutes=90):
            if flight.status != FlightStatus.COMPLETED:
                flight.status = FlightStatus.COMPLETED
                modified = True

        elif now >= arrival_time:
            if flight.status != FlightStatus.LANDED:
                flight.status = FlightStatus.LANDED
                modified = True

        elif now >= departure_time:
            if flight.status != FlightStatus.DEPARTED:
                flight.status = FlightStatus.DEPARTED
                modified = True

        elif now >= boarding_time:
            if flight.status != FlightStatus.BOARDING:
                flight.status = FlightStatus.BOARDING
                flight.boarding_announced = True
                modified = True

        return modified


flight_simulator = FlightSimulator()