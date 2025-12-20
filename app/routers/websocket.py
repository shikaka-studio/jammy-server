from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.websocket_manager import websocket_manager
from app.services.supabase_service import SupabaseService

router = APIRouter()
supabase_service = SupabaseService()


@router.websocket("/ws/{code}")
async def websocket_endpoint(
    websocket: WebSocket,
    code: str,
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
        code: Room code to join
        user_id: User ID (from query param)
    """
    # Verify room exists
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            await websocket.close(code=1008, reason="Room not found")
            return

        room_id = room.data["id"]

        # Connect to WebSocket manager
        await websocket_manager.connect(websocket, room_id)

        # Get user details for broadcast
        user = await supabase_service.get_user_by_id(user_id)
        user_data = None
        if user.data:
            user_data = {
                "user_id": user_id,
                "display_name": user.data.get("display_name", "Unknown"),
                "profile_image_url": user.data.get("profile_image_url")
            }

        # Send welcome message
        await websocket_manager.send_personal_message(
            websocket,
            {
                "type": "connected",
                "data": {
                    "room_id": room_id,
                    "code": code,
                    "message": "Connected to room",
                    "user": user_data
                }
            }
        )

        # Broadcast user joined notification
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "member_joined",
                "data": {
                    **user_data,
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
            print(f"[WebSocket] Client disconnected from room {code}")

    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass

    finally:
        # Clean up connection
        websocket_manager.disconnect(websocket, room_id)

        # Broadcast user left notification (only if we have user data)
        if user_data:
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "member_left",
                    "data": {
                        **user_data,
                        "connection_count": websocket_manager.get_room_connection_count(room_id)
                    }
                }
            )
