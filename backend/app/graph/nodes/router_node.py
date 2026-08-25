import logging
from typing import Literal
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from app.core.config import GEMINI_API_KEY
from app.graph.state import AgentState
from app.graph.prompts.router_prompt import router_prompt_template

logger = logging.getLogger(__name__)

class RouteDecision(BaseModel):
    intent: Literal[
        "airport_assistance",
        "chit_chat",
        "out_of_scope",
        "inappropriate"
    ] = Field(description = "The classified intent of the user's message.")

def route_user_message(state: AgentState) -> str:
    """
    Evaluates the user's recent chat history to determine the intent of the user's latest message.
    Returns a string (the intent) which will be used by the graph's conditional edges to route the flow.
    """
    logger.info("Routing user message with recent context to determine intent...")

    recent_messages = state["messages"][-4:]
    logger.info("Routing user message with recent context to determine intent...")

    llm = ChatGoogleGenerativeAI(
        model = "gemini-3.1-flash-lite",
        google_api_key = GEMINI_API_KEY,
        temperature = 0.2,
    )

    router_llm = llm.with_structured_output(RouteDecision)
    chain = router_prompt_template | router_llm

    try:
        clean_messages = []
        for msg in state["messages"]:
            if msg.type == "human":
                clean_messages.append(msg)
            elif msg.type == "ai" and not getattr(msg, "tool_calls", None):
                clean_messages.append(msg)

        decision = chain.invoke({"messages" : recent_messages})
        
        logger.info(f"Message routed as : {decision.intent}")
        return decision.intent

    except Exception as e:
        logger.info(f"Routing API failed: {str(e)}")
        return "system_error"