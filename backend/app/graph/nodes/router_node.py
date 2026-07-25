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
        "airport_assisance",
        "chit_chat",
        "out_of_scope",
        "inappropriate"
    ] = Field(description = "The classified intent of the user's message.")

def route_user_message(state: AgentState) -> str:
    """
    """

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
        decision = chain.invoke({"messages" : recent_messages})
        logger.info(f"Message routed as : {decision.intent}")
        return decision.intent

    except Exception as e:
        logger.info(f"Routing API failed: {str(e)}")
        return "system_error"