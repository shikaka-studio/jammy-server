from typing import Dict, List
from fastapi import WebSocket
from app.core.logging import get_logger
import json

logger = get_logger("WebSocketManager")


class WebSocketManager:
    """
    Manages WebSocket connections for real-time room updates.
    Handles connection lifecycle and broadcasting messages to room members.
    """

    def __init__(self):
        # room_id -> list of WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_id: str):
        """
        Accept and store a new WebSocket connection for a room.

        Args:
            websocket: WebSocket connection
            room_id: Room ID to join
        """
        await websocket.accept()

        if room_id not in self.active_connections:
            self.active_connections[room_id] = []

        self.active_connections[room_id].append(websocket)

    def disconnect(self, websocket: WebSocket, room_id: str):
        """
        Remove a WebSocket connection from a room.

        Args:
            websocket: WebSocket connection to remove
            room_id: Room ID to leave
        """
        if room_id in self.active_connections:
            if websocket in self.active_connections[room_id]:
                self.active_connections[room_id].remove(websocket)

            # Clean up empty room
            if not self.active_connections[room_id]:
                del self.active_connections[room_id]

    async def broadcast_to_room(self, room_id: str, message: dict):
        """
        Broadcast a message to all connected clients in a room.

        Args:
            room_id: Room ID to broadcast to
            message: Message dict to send (will be JSON serialized)
        """
        if room_id not in self.active_connections:
            return

        # Convert message to JSON
        json_message = json.dumps(message)

        # Send to all connections in the room
        disconnected = []
        for connection in self.active_connections[room_id]:
            try:
                await connection.send_text(json_message)
            except Exception as e:
                logger.warning(f"Failed to send {message.get('type')} to client in room {room_id}: {e}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection, room_id)

    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """
        Send a message to a specific WebSocket connection.

        Args:
            websocket: WebSocket connection
            message: Message dict to send (will be JSON serialized)
        """
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send {message.get('type')} message: {e}", exc_info=True)

    def get_room_connection_count(self, room_id: str) -> int:
        """
        Get number of active connections in a room.

        Args:
            room_id: Room ID

        Returns:
            Number of connections
        """
        if room_id not in self.active_connections:
            return 0
        return len(self.active_connections[room_id])


# Global WebSocket manager instance
websocket_manager = WebSocketManager()
