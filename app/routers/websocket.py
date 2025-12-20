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

        # Send current queue and playback state to the newly connected client
        try:
            session = await supabase_service.get_active_session(room_id)
            if session.data:
                session_id = session.data["id"]

                # Send queue state
                queue = await supabase_service.get_session_queue(session_id)
                recently_played = await supabase_service.get_recently_played_songs(session_id)

                await websocket_manager.send_personal_message(
                    websocket,
                    {
                        "type": "queue_update",
                        "data": {
                            "queue": [
                                {
                                    "id": s["id"],
                                    "title": s["song"]["title"],
                                    "artist": s["song"]["artist"],
                                    "album": s["song"].get("album"),
                                    "album_art_url": s["song"]["album_art_url"],
                                    "duration_ms": s["song"]["duration_ms"],
                                    "spotify_id": s["song"]["spotify_id"],
                                    "spotify_uri": s["song"]["spotify_uri"],
                                    "added_by": {
                                        "id": s["user"]["id"],
                                        "spotify_id": s["user"]["spotify_id"],
                                        "display_name": s["user"]["display_name"],
                                        "profile_image_url": s["user"]["profile_image_url"]
                                    } if s.get("user") else None
                                }
                                for s in queue.data
                            ] if queue.data else [],
                            "recently_played": [
                                {
                                    "id": s["id"],
                                    "title": s["song"]["title"],
                                    "artist": s["song"]["artist"],
                                    "album": s["song"].get("album"),
                                    "album_art_url": s["song"]["album_art_url"],
                                    "duration_ms": s["song"]["duration_ms"],
                                    "spotify_id": s["song"]["spotify_id"],
                                    "spotify_uri": s["song"]["spotify_uri"],
                                    "played_at": s.get("played_at"),
                                    "added_by": {
                                        "id": s["user"]["id"],
                                        "spotify_id": s["user"]["spotify_id"],
                                        "display_name": s["user"]["display_name"],
                                        "profile_image_url": s["user"]["profile_image_url"]
                                    } if s.get("user") else None
                                }
                                for s in recently_played.data
                            ] if recently_played.data else []
                        }
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
            print(f"[WebSocket] No active session/queue for room {code}: {e}")

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
