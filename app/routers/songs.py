from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.services.supabase_service import SupabaseService
from app.services.spotify_service import SpotifyService
from app.services.websocket_manager import websocket_manager
import httpx

router = APIRouter()
supabase_service = SupabaseService()
spotify_service = SpotifyService()


class AddSongRequest(BaseModel):
    room_code: str
    spotify_track_id: str
    track_name: str
    artist_name: str
    album_image_url: str | None = None
    duration_ms: int | None = None
    user_spotify_id: str


@router.get("/search")
async def search_songs(query: str, limit: int = 20, authorization: str = Header(...)):
    """
    Search for songs on Spotify.
    Requires Authorization header with Spotify access token.
    """
    try:
        # Extract token from "Bearer <token>" format
        access_token = authorization.replace("Bearer ", "")
        results = await spotify_service.search_tracks(access_token, query, limit)

        # Transform response to simpler format for frontend
        tracks = []
        for item in results.get("tracks", {}).get("items", []):
            tracks.append({
                "id": item["id"],
                "name": item["name"],
                "artists": [artist["name"] for artist in item["artists"]],
                "album": {
                    "name": item["album"]["name"],
                    "image_url": item["album"]["images"][0]["url"] if item["album"]["images"] else None
                },
                "duration_ms": item["duration_ms"],
                "uri": item["uri"],
                "preview_url": item.get("preview_url")
            })

        return {"tracks": tracks}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Spotify API error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track/{track_id}")
async def get_track(track_id: str, authorization: str = Header(...)):
    """Get track details by Spotify ID"""
    try:
        access_token = authorization.replace("Bearer ", "")
        track = await spotify_service.get_track(access_token, track_id)

        return {
            "id": track["id"],
            "name": track["name"],
            "artists": [artist["name"] for artist in track["artists"]],
            "album": {
                "name": track["album"]["name"],
                "image_url": track["album"]["images"][0]["url"] if track["album"]["images"] else None
            },
            "duration_ms": track["duration_ms"],
            "uri": track["uri"],
            "preview_url": track.get("preview_url")
        }
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail="Spotify API error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_song_to_queue(request: AddSongRequest):
    """Add a song to the session queue"""
    try:
        # Get room
        room = await supabase_service.get_room_by_code(request.room_code)
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
            spotify_track_id=request.spotify_track_id,
            track_name=request.track_name,
            artist_name=request.artist_name,
            album_image_url=request.album_image_url,
            duration_ms=request.duration_ms
        )
        song_id = song_result.data[0]["id"]

        # Get next position for the queue
        position = await supabase_service.get_next_position_in_session(session_id)

        # Add song to session queue
        session_song_result = await supabase_service.add_song_to_session(
            session_id=session_id,
            song_id=song_id,
            added_by=user_id,
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
                            "song_id": s["song"]["id"],
                            "name": s["song"]["track_name"],
                            "artists": s["song"]["artist_name"],
                            "album_image_url": s["song"]["album_image_url"],
                            "duration_ms": s["song"]["duration_ms"],
                            "spotify_track_id": s["song"]["spotify_track_id"]
                        }
                        for s in queue.data
                    ]
                }
            }
        )

        return {
            "session_song": session_song_result.data[0],
            "message": "Song added to queue"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{room_code}")
async def get_queue(room_code: str):
    """Get the song queue for a room's active session"""
    try:
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        room_id = room.data["id"]

        # Get active session
        try:
            session = await supabase_service.get_active_session(room_id)
            session_id = session.data["id"]
        except Exception:
            # No active session, return empty queue
            return {"queue": []}

        # Get session queue
        queue = await supabase_service.get_session_queue(session_id)

        # Transform to frontend format
        queue_data = [
            {
                "id": s["id"],
                "song_id": s["song"]["id"],
                "name": s["song"]["track_name"],
                "artists": s["song"]["artist_name"],
                "album_image_url": s["song"]["album_image_url"],
                "duration_ms": s["song"]["duration_ms"],
                "spotify_track_id": s["song"]["spotify_track_id"],
                "added_by": {
                    "display_name": s["user"]["display_name"],
                    "profile_image_url": s["user"]["profile_image_url"]
                } if s.get("user") else None
            }
            for s in queue.data
        ]

        return {"queue": queue_data}
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
                                    "song_id": s["song"]["id"],
                                    "name": s["song"]["track_name"],
                                    "artists": s["song"]["artist_name"],
                                    "album_image_url": s["song"]["album_image_url"],
                                    "duration_ms": s["song"]["duration_ms"],
                                    "spotify_track_id": s["song"]["spotify_track_id"]
                                }
                                for s in queue.data
                            ] if queue.data else []
                        }
                    }
                )

        return {"message": "Song removed from queue"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
