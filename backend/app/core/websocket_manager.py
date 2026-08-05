import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages the active passenger websocket connection and pushes the live notifications.
    """
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        """
        Accepts and registers an incoming request connection for a given user.
        """
        await websocket.accept()
        self.active_connections[str(user_id)] = websocket
        logger.info(f"WebSocket connected for User ID : {user_id}")

    def disconnect(self, user_id: str) -> None:
        """
        Removes a disconnected user from the active registery
        """
        user_str = str(user_id)
        if user_str in self.active_connections:
            del self.active_connections[user_str]
            logger.info(f"WebSocket disconnected for User ID : {user_id}")

    async def send_personal_message(self, user_id: str, payload: dict) -> bool:
        """
        Pushes a Json notification payload directly down the user's active WebSocket connection.
        Returns True if delivered and False if user is offline.
        """
        user_str = str(user_id)
        websocket = self.active_connections.get(user_str)
        if websocket:
            try:
                await websocket.send_json(payload)
                return True
            except Exception as e:
                logger.error(f"Failed tp push the WebSocket message to User {user_id}: {str(e)}")
                self.disconnect(user_str)
                return False
        return False

manager = ConnectionManager()