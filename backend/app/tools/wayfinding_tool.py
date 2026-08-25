import json
import os
import networkx as nx
import logging
from datetime import datetime, timezone
from langchain_core.tools import tool
from sqlalchemy.orm import Session
from app.database.postgres_session import SessionLocal
from app.database.postgres_models import RetailerOffer

logger = logging.getLogger(__name__)

MAP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "maps", "mega_airport_map.json"))


def load_airport_graph():

    graph = nx.Graph()
    try:
        with open(MAP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

            for node in data.get("nodes", []):
                graph.add_node(node["id"], **node)

            for edge in data.get("edges", []):
                graph.add_edge(edge["from"], edge["to"], weight = edge["dist"])

    except Exception as e:
        logger.error(f"Failed to load airport map: {str(e)}")

    return graph


airport_graph = load_airport_graph()


def resolve_node_id(location_query: str, terminal_code: str = None) -> str:
    """
    Translates a human readable name (e.g., 'Gate 1', 'Starbucks') into the exact node id
    If it's aready a valid ID, it returns it directly
    """

    clean_query = location_query.strip().lower()

    if clean_query in airport_graph.nodes:
        return clean_query

    potential_matches = []

    for node_id, data in airport_graph.nodes(data=True):
        node_name = data.get("name", "").strip().lower()

        if clean_query == node_name or clean_query in node_name:
            potential_matches.append((node_id, data))

    if not potential_matches:
        return None

    if terminal_code:
        for node_id, data in potential_matches:
            if data.get("terminal") == terminal_code.upper():
                return node_id

    return potential_matches[0][0]


@tool
def get_walking_directions(start_location: str, end_location: str, terminal: str = None) -> str:
    """
    Calculates the shortest walking path and estimated time between two specific airport loations.

    Args:
        start_location: Where the user is (e.g., 'Gate 4')
        end_location: Where they want to go (e.g., 'Starbucks')
        terminal: The terminal the user is currently in (e.g., 'T1', 'T2'). Helps differentiate the store with the same name.
    """

    start_node_id = resolve_node_id(start_location, terminal)

    if start_node_id and start_node_id in airport_graph.nodes:
        inferred_terminal = airport_graph.nodes[start_node_id].get("terminal")
    else:
        inferred_terminal = terminal

    end_node_id = resolve_node_id(end_location, inferred_terminal)

    if not start_node_id or not end_node_id:
        return f"I couldn't locate '{start_location}' or '{end_location}' on the map. Please specify a store name, gate, or terminal."

    try:
        raw_distance = nx.shortest_path_length(airport_graph, source=start_node_id, target=end_node_id, weight="weight")
        path = nx.shortest_path(airport_graph, source=start_node_id, target=end_node_id, weight="weight")

        actual_minutes = max(1, round(raw_distance/10))

        path_names = [airport_graph.nodes[n].get("name", n) for n in path]
        route_str = " -> ".join(path_names)

        return(
            f"Navigation from {path_names[0]} to {path_names[-1]}: \n"
            f"Estimated Walking Time : {actual_minutes} minutes. \n"
            f"Route: {route_str}"
        )

    except nx.NetworkXNoPath:
        return "There is no direct walking route between these 2 locations."


@tool
def find_nearby_amenities(current_location: str, category: str, terminal: str = None, limit: int = 4) -> str:
    """
    Finds the closest amenitites or retail options based on a category (e.g., 'dining', 'washroom', 'electronics', 'cafe').
    Use this to give the user 4-5 nearby options to choose from.

    Args:
        current_location: The user's current location name or ID (e.g., 'Gate 1', 'gate_t1_01').
        category: The category to search for (e.g., 'fast-food', 'cafe', 'washroom', 'dining')
        terminal: OPtional terminal code ('T1' or 'T2') to resolve location accurately.
        limit: Number of results to return (default is 4)
    """

    start_node_id = resolve_node_id(current_location, terminal)

    if not start_node_id or start_node_id not in airport_graph:
        return f"I cannot verify your current location '{current_location}' on the map."

    db: Session = SessionLocal()

    try:
        lengths = nx.single_source_dijkstra_path_length(airport_graph, start_node_id, weight = "weight")

        clean_category = category.strip().lower()
        all_matching_nodes = []

        for node_id, raw_dist in lengths.items():
            dist = max(1, round(raw_dist/10))
            node_data = airport_graph.nodes[node_id]

            node_type = str(node_data.get("type", "")).lower()
            node_cat = str(node_data.get("category", "")).lower()
            node_sub = str(node_data.get("subtype", "")).lower()

            if clean_category in (node_type, node_cat, node_sub):
                if raw_dist>0:
                    all_matching_nodes.append({
                        "name": node_data.get("name"),
                        "dist": dist,
                        "id": node_id
                    })

        if not all_matching_nodes:
            return "I couldn't find any options matching '{category}' near your location."

        all_node_ids = [node["id"] for node in all_matching_nodes]
        active_offers = db.query(RetailerOffer).filter(
            RetailerOffer.walking_node_id.in_(all_node_ids),
            RetailerOffer.active_until > datetime.now(timezone.utc)
        )

        offer_map = {offer.walking_node_id: offer.offer_text for offer in active_offers}

        promoted_locations = []
        regular_locations = []

        for node in all_matching_nodes:
            if node["id"] in offer_map:
                node["offer_text"] = offer_map[node["id"]]
                promoted_locations.append(node)
            else:
                regular_locations.append(node)

        promoted_locations.sort(key=lambda x:x["dist"])
        regular_locations.sort(key=lambda x:x["dist"])

        final_regular = regular_locations[:limit]

        response = f"Here are the options for '{category}' : \n"

        if promoted_locations:
            response += "----Promoted Offers----\n"
            for res in promoted_locations:
                response += f"- {res['name']}({res['dist']} mins walk) \n"

        if final_regular:
            response += "----Closest Distance----\n"
            for res in final_regular:
                response += f"- {res['name']}({res['dist']} mins walk) \n"

        return response

    except Exception as e:
        logger.error(f"Error finding nearby amenitites: {str(e)}")
        return "I am having trouble checking the map for nearby options right now."

    finally:
        db.close()