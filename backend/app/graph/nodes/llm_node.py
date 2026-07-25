import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage
from app.core.config import GEMINI_API_KEY
from app.graph.state import AgentState
from app.graph.prompts.system_prompt import system_prompt_template

from app.graph.nodes.tool_node import ACTIVE_TOOLS

logger = logging.getLogger(__name__)

def call_model(state: AgentState) -> dict:
    """
    It is the main reasoning engine.In injects the passenger's current state into the system prompt,
    evaluates the conversation history, and decides whether to reply or call a tool.
    """

    logger.info("Invoking the main LLM model...")

    llm = ChatGoogleGenerativeAI(
        model = "gemini-3.1-flash-lite",
        google_api_key = GEMINI_API_KEY,
        temperature = 0.2
    )

    llm_with_tools = llm.bind_tools(ACTIVE_TOOLS)

    prompt = system_prompt_template.partial(
        user_name = state.get("user_name", "Passenger"),
        pnr = state.get("pnr", "Unknown"),
        flight_number = state.get("flight_number", "Unknown"),
        source = state.get("source", "Unknown"),
        destination = state.get("destination","Unknown"),
        terminal = state.get("terminal", "Unknown"),
        gate = state.get("gate", "Unknown"),
        current_location_id = state.get("current_location_id", "Unknown"),
        is_layover = str(state.get("is_layover", False)),
        layover_airport = state.get("layover_airport", "None")
    )

    chain = prompt | llm_with_tools

    try:
        response = chain.invoke({"messages": state["messages"]})
        return {"messages": [response]}

    except Exception as e:
        logger.error(f"LLM API failed: {str(e)}")

        return {"messages": [AIMessage(content=(
            "I am currently experiencing a network interruption and cannot process your request."
            "Please check the nearest flight information screen or visit the Information Helpdesk, "
            "so our ground staff can assist you immediately."
        ))]}