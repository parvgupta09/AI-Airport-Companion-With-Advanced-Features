import logging
from langchain_core.messages import AIMessage
from app.graph.state import AgentState

logger = logging.getLogger(__name__)

def handle_out_of_scope(state: AgentState) -> dict:

    logger.info("Handling out of scope request...")
    message = (
        "I am automated airport companion and can only assist with flights, "
        "terminal navigation, and airport services. For anything outside of the airport, "
        "please visit the nearest Information HelpDesk and our staff will be happy to assist you."
        "If you would like walking directions to the nearest desk, just let me know your current location!"
    )
    return {"message": [AIMessage(content = message)]}


def handle_inappropriate(state: AgentState) -> dict:

    logger.info("Handling inappropriate request...")
    message = (
        "I cannot fulfill this request. If you require immediate or emergency assistance, "
        "please locate security or approach the nearest Information Helpdesk directly."
        "If you need walking directions to the helpdesk, please tell me where you are currently standing."
    )
    return {"message": [AIMessage(content=message)]}


def handle_system_error(state: AgentState) -> dict:

    logger.info("Handling system error fallback...")
    message = (
        "I am currently experiencing a temporary network delay. "
        "Please check the nearest digital flight information screen, or visit the "
        "Information HelpDesk so out ground staff can assit you immediately."
        "If you need directions to the helpdesk, just reply with your current gate or location."
    )
    return {"message": [AIMessage(content=message)]}