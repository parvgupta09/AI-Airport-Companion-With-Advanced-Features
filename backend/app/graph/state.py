from typing import Annotated, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    The shared state for the LangGraph Agent.
    This is autmatically saved and loaded by the PostgreSQL checkpointer.
    """

    messages: Annotated[list[BaseMessage], add_messages]

    user_id: str
    user_name: str

    pnr: str
    flight_number: str
    source: str
    destination: str

    terminal: Optional[str]
    gate: Optional[str]
    current_location_id: Optional[str]

    is_layover: bool
    layover_airport: Optional[str]