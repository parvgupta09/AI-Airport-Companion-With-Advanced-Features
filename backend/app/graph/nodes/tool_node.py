import logging
from langgraph.prebuilt import ToolNode

from app.tools.flight_tool import get_flight_status
from app.tools.qdrant_search_tool import search_airport_policies
from app.tools.wayfinding_tool import get_walking_directions, find_nearby_amenities
from app.tools.reminder_tool import schedule_passenger_reminder

logger = logging.getLogger(__name__)

ACTIVE_TOOLS = [
    get_flight_status,
    search_airport_policies,
    get_walking_directions,
    find_nearby_amenities,
    schedule_passenger_reminder
]

airport_tool_node = ToolNode(ACTIVE_TOOLS)