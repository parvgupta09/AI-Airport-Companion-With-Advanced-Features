TOOL_INSTRUCTION_PROMPT = """
--- TOOL USAGE GUIDELINES ---

1. 'get_flight_status':
   - Call when the passenger asks for real-time flight updates, delay durations, gate changes, or baggage claim belts.

2. 'search_airport_policies':
   - Call when the passenger asks about official rules, liquid limits, duty-free allowances, lost luggage procedures, Wi-Fi access, cancellation rebooking, layover transfers, security lockout or special assistance dispatch guidelines.

3. 'get_walking_directions':
   - Call when a passenger requests point-to-point walking navigation between two specific places in the terminal.

4. 'find_nearby_amenities':
   - Call when a passenger asks for nearby options (e.g., food, cafes, washrooms, ATMs).
   - Automatically prioritizes active retailer promotional discounts at the top.

5. 'schedule_passenger_reminder':
   - Call when the user explicitly requests an alert or alarm for a specific time interval.
"""