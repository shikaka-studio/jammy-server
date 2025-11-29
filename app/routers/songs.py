from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.services.supabase_service import SupabaseService
from app.services.spotify_service import SpotifyService

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
    """Add a song to the room queue"""
    try:
        # Get room
        room = await supabase_service.get_room_by_code(request.room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        # Get user
        user = await supabase_service.get_user_by_spotify_id(request.user_spotify_id)
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Add song to queue
        result = await supabase_service.add_song_to_queue(
            room_id=room.data["id"],
            spotify_track_id=request.spotify_track_id,
            added_by=user.data["id"],
            track_name=request.track_name,
            artist_name=request.artist_name,
            album_image_url=request.album_image_url,
            duration_ms=request.duration_ms
        )

        return {"song": result.data[0], "message": "Song added to queue"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue/{room_code}")
async def get_queue(room_code: str):
    """Get the song queue for a room"""
    try:
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        queue = await supabase_service.get_room_queue(room.data["id"])

        return {"queue": queue.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{song_id}")
async def remove_song(song_id: str):
    """Remove a song from the queue"""
    try:
        await supabase_service.remove_song_from_queue(song_id)
        return {"message": "Song removed from queue"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
