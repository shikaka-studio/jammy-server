from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.core.logging import get_logger
from app.services.websocket_manager import websocket_manager
from app.services.supabase_service import SupabaseService
from app.utils.formatters import format_queue_update

logger = get_logger("api.websocket")
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
            logger.warning(f"WebSocket connection rejected: room {code} not found")
            await websocket.close(code=1008, reason="Room not found")
            return

        room_id = room.data["id"]

        # Connect to WebSocket manager
        await websocket_manager.connect(websocket, room_id)

        # Get user details for broadcast
        user = await supabase_service.get_user_by_id(user_id)
        user_data = None
        display_name = "Unknown"
        if user.data:
            display_name = user.data.get("display_name", "Unknown")
            user_data = {
                "user_id": user_id,
                "display_name": display_name,
                "profile_image_url": user.data.get("profile_image_url")
            }

        room_name = room.data.get("name", code)
        logger.info(f"User {display_name} ({user_id}) connected to room {room_name} ({code}) - {websocket_manager.get_room_connection_count(room_id)} total")

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

        # Send current queue and playback state to the newly connected client
        try:
            session = await supabase_service.get_active_session(room_id)
            if session.data:
                session_id = session.data["id"]
                logger.debug(f"Sending initial state to user {user_id} for session {session_id}")

                # Send queue state
                queue = await supabase_service.get_session_queue(session_id)
                recently_played = await supabase_service.get_recently_played_songs(session_id)

                await websocket_manager.send_personal_message(
                    websocket,
                    {
                        "type": "queue_update",
                        "data": format_queue_update(
                            queue.data if queue.data else [],
                            recently_played.data if recently_played.data else []
                        )
                    }
                )

                # Send playback state
                from app.services.playback_manager import PlaybackManager
                playback_manager = PlaybackManager()
                playback_state = await playback_manager.get_playback_state(session_id)
                await websocket_manager.send_personal_message(
                    websocket,
                    {
                        "type": "playback_state",
                        "data": playback_state
                    }
                )
        except Exception as e:
            # No active session or queue - that's okay, just skip
            logger.debug(f"No active session/queue for room {code}: {e}")

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
            logger.info(f"User {display_name} ({user_id}) disconnected from room {room_name} ({code})")

    except Exception as e:
        logger.error(f"WebSocket error for user {display_name} ({user_id}) in room {room_name} ({code}): {e}", exc_info=True)
        try:
            await websocket.close(code=1011, reason=str(e))
        except:
            pass

    finally:
        # Clean up connection
        websocket_manager.disconnect(websocket, room_id)
        remaining = websocket_manager.get_room_connection_count(room_id)
        logger.debug(f"User {display_name} ({user_id}) cleaned up from room {room_name} ({code}) - {remaining} remaining")

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
