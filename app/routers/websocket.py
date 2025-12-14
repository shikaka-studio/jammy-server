from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import websocket_manager
from app.services.supabase_service import SupabaseService

router = APIRouter()
supabase_service = SupabaseService()


@router.websocket("/ws/{room_code}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_code: str,
    user_id: str = Query(...)
):
    """
    WebSocket endpoint for real-time room updates.

    Clients connect to receive:
    - Playback state changes (play/pause/skip)
    - Queue updates (song added/removed)
    - Member updates (user joined/left)
    - Notifications

    Args:
        websocket: WebSocket connection
        room_code: Room code to join
        user_id: User ID (from query param)
    """
    # Verify room exists
    try:
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            await websocket.close(code=1008, reason="Room not found")
            return

        room_id = room.data["id"]

        # Connect to WebSocket manager
        await websocket_manager.connect(websocket, room_id)

        # Send welcome message
        await websocket_manager.send_personal_message(
            websocket,
            {
                "type": "connected",
                "data": {
                    "room_id": room_id,
                    "room_code": room_code,
                    "message": "Connected to room"
                }
            }
        )

        # Broadcast user joined notification
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "member_joined",
                "data": {
                    "user_id": user_id,
                    "connection_count": websocket_manager.get_room_connection_count(room_id)
                }
            }
        )

        # Keep connection alive and handle incoming messages
        try:
            while True:
                # Receive messages from client (for heartbeat/ping)
                data = await websocket.receive_text()

                # Handle client messages if needed
                # For now, just echo heartbeat
                if data == "ping":
                    await websocket_manager.send_personal_message(
                        websocket,
                        {"type": "pong", "data": {}}
                    )

        except WebSocketDisconnect:
            print(f"[WebSocket] Client disconnected from room {room_code}")

    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass

    finally:
        # Clean up connection
        websocket_manager.disconnect(websocket, room_id)

        # Broadcast user left notification
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "member_left",
                "data": {
                    "user_id": user_id,
                    "connection_count": websocket_manager.get_room_connection_count(room_id)
                }
            }
        )
