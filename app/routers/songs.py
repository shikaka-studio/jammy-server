from fastapi import APIRouter, HTTPException
from app.services.supabase_service import SupabaseService
from app.services.websocket_manager import websocket_manager
from app.schemas.song import AddSongRequest

router = APIRouter()
supabase_service = SupabaseService()


@router.post("/add")
async def add_song_to_queue(request: AddSongRequest):
    """Add a song to the session queue"""
    try:
        # Get room
        room = await supabase_service.get_room_by_code(request.code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        room_id = room.data["id"]

        # Get user
        user = await supabase_service.get_user_by_spotify_id(request.user_spotify_id)
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        user_id = user.data["id"]

        # Get or create active session for the room
        try:
            session_result = await supabase_service.get_active_session(room_id)
            session_id = session_result.data["id"]
        except Exception:
            # No active session, create one
            session_result = await supabase_service.create_session(room_id)
            session_id = session_result.data[0]["id"]

        # Create or get song in song table
        song_result = await supabase_service.create_or_get_song(
            spotify_id=request.spotify_track_id,
            title=request.title,
            artist=request.artist,
            album=request.album,
            album_art_url=request.album_art_url,
            spotify_uri=request.spotify_uri,
            duration_ms=request.duration_ms
        )
        song_id = song_result.data[0]["id"]

        # Get next position for the queue
        position = await supabase_service.get_next_position_in_session(session_id)

        # Add song to session queue
        session_song_result = await supabase_service.add_song_to_session(
            session_id=session_id,
            song_id=song_id,
            added_by_user_id=user_id,
            position=position
        )

        # Auto-start playback if queue was empty
        from app.services.playback_manager import PlaybackManager
        playback_manager = PlaybackManager()
        await playback_manager.handle_song_added(session_id)

        # Broadcast queue update to all clients
        queue = await supabase_service.get_session_queue(session_id)
        await websocket_manager.broadcast_to_room(
            room_id,
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
                    ]
                }
            }
        )

        return session_song_result.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{code}")
async def get_queue(code: str):
    """Get the song queue for a room's active session"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        room_id = room.data["id"]

        # Get active session
        try:
            session = await supabase_service.get_active_session(room_id)
            session_id = session.data["id"]
        except Exception:
            # No active session, return empty queue
            return []

        # Get session queue
        queue = await supabase_service.get_session_queue(session_id)

        # Transform to frontend format
        queue_data = [
            {
                "id": s["id"],
                "song_id": s["song"]["id"],
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
        ]

        return queue_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{session_song_id}")
async def remove_song(session_song_id: str):
    """Remove a song from the session queue"""
    try:
        # Get session_song to find session and room before deletion
        session_song_result = await supabase_service.get_session_song_by_id(session_song_id)
        if session_song_result.data:
            session_song = session_song_result.data[0]
            session_id = session_song.get("session_id")

            # Get session to find room_id
            session = await supabase_service.get_session_by_id(session_id)
            room_id = session.data["room_id"]

            # Remove song from session
            await supabase_service.remove_session_song(session_song_id)

            # Broadcast queue update
            if room_id:
                queue = await supabase_service.get_session_queue(session_id)
                await websocket_manager.broadcast_to_room(
                    room_id,
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
                            ] if queue.data else []
                        }
                    }
                )

        return {"message": "Song removed from queue"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
