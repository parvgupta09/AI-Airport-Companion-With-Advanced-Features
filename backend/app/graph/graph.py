import logging
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import tools_condition
from langgraph.checkpoint.memory import MemorySaver

from app.graph.state import AgentState

from app.graph.nodes.router_node import route_user_message

from app.graph.nodes.llm_node import call_model
from app.graph.nodes.tool_node import airport_tool_node

from app.graph.nodes.static_nodes import(
    handle_inappropriate,
    handle_out_of_scope,
    handle_system_error
)

logger = logging.getLogger(__name__)

def build_graph():
    """

    """

    logger.info("Building the main LangGraph workflow...")

    workflow = StateGraph(AgentState)

    workflow.add_note("llm_node", call_model)
    workflow.add_node("tools", airport_tool_node)

    workflow.add_node("out_of_scope_node", handle_out_of_scope)
    workflow.add_node("inappropriate_node", handle_inappropriate)
    workflow.add_node("system_error_node", handle_system_error)

    workflow.add_conditional_edges(
        START,
        route_user_message,
        {
            "airport_assistance" : "llm_node",
            "chit_chat" : "llm_node",
            "out_of_scope": "out_of_scope_node",
            "inappropriate" : "inappropriate_node",
            "system_error" : "system_error_node"
        }
    )

    workflow.add_conditional_edges(
        "llm_node",
        tools_condition,
        {
            "tools": "tools",   # If gemini asks for the tools, send it to the tools_node
            END: END            # If gemini just writes text, and the cycle and reply to the user
        }
    )

    workflow.add_edge("tools", "llm_node")

    workflow.add_edge("out_of_scope", END)
    workflow.add_edge("inappropriate_node", END)
    workflow.add_edge("system_error_node", END)

    memory = MemorySaver()
    app_graph = workflow.compile(checkpointer = memory)

    return app_graph

airport_graph = build_graph()