from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from app.services.supabase_service import SupabaseService
from app.services.spotify_service import SpotifyService

router = APIRouter()
supabase_service = SupabaseService()
spotify_service = SpotifyService()


class PlayTrackRequest(BaseModel):
    track_uri: str
    position_ms: int = 0
    device_id: str | None = None


class SeekRequest(BaseModel):
    position_ms: int
    device_id: str | None = None


class VolumeRequest(BaseModel):
    volume_percent: int
    device_id: str | None = None


class TransferRequest(BaseModel):
    device_id: str
    play: bool = False


# ==================== DEVICE ENDPOINTS ====================

@router.get("/devices")
async def get_devices(authorization: str = Header(...)):
    """Get user's available Spotify devices"""
    try:
        access_token = authorization.replace("Bearer ", "")
        devices = await spotify_service.get_available_devices(access_token)
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/transfer")
async def transfer_playback(request: TransferRequest, authorization: str = Header(...)):
    """Transfer playback to a different device"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.transfer_playback(
            access_token,
            request.device_id,
            request.play
        )
        if not success:
            raise HTTPException(status_code=400, detail="Failed to transfer playback")
        return {"message": "Playback transferred"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PLAYBACK STATE ====================

@router.get("/state")
async def get_playback_state(authorization: str = Header(...)):
    """Get current playback state"""
    try:
        access_token = authorization.replace("Bearer ", "")
        state = await spotify_service.get_playback_state(access_token)
        return {"playback_state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/currently-playing")
async def get_currently_playing(authorization: str = Header(...)):
    """Get currently playing track"""
    try:
        access_token = authorization.replace("Bearer ", "")
        current = await spotify_service.get_currently_playing(access_token)
        return {"currently_playing": current}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PLAYBACK CONTROLS ====================

@router.put("/play")
async def play(request: PlayTrackRequest | None = None, authorization: str = Header(...)):
    """Start or resume playback"""
    try:
        access_token = authorization.replace("Bearer ", "")

        if request and request.track_uri:
            success = await spotify_service.start_playback(
                access_token,
                track_uris=[request.track_uri],
                device_id=request.device_id,
                position_ms=request.position_ms
            )
        else:
            # Resume current playback
            success = await spotify_service.start_playback(
                access_token,
                device_id=request.device_id if request else None
            )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to start playback. Make sure Spotify is active on a device.")

        return {"message": "Playback started"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/pause")
async def pause(authorization: str = Header(...), device_id: str | None = None):
    """Pause playback"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.pause_playback(access_token, device_id)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to pause playback")

        return {"message": "Playback paused"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/next")
async def skip_next(authorization: str = Header(...), device_id: str | None = None):
    """Skip to next track"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.skip_to_next(access_token, device_id)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to skip track")

        return {"message": "Skipped to next track"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/previous")
async def skip_previous(authorization: str = Header(...), device_id: str | None = None):
    """Skip to previous track"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.skip_to_previous(access_token, device_id)

        if not success:
            raise HTTPException(status_code=400, detail="Failed to skip track")

        return {"message": "Skipped to previous track"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/seek")
async def seek(request: SeekRequest, authorization: str = Header(...)):
    """Seek to position in currently playing track"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.seek_to_position(
            access_token,
            request.position_ms,
            request.device_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to seek")

        return {"message": f"Seeked to {request.position_ms}ms"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/volume")
async def set_volume(request: VolumeRequest, authorization: str = Header(...)):
    """Set playback volume"""
    try:
        access_token = authorization.replace("Bearer ", "")
        success = await spotify_service.set_volume(
            access_token,
            request.volume_percent,
            request.device_id
        )

        if not success:
            raise HTTPException(status_code=400, detail="Failed to set volume")

        return {"message": f"Volume set to {request.volume_percent}%"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ROOM SYNC ====================

@router.post("/room/{room_code}/play-next")
async def play_next_in_queue(room_code: str, authorization: str = Header(...)):
    """
    Play the next song in the room queue for all members.
    This syncs playback across all users in the room.
    """
    try:
        access_token = authorization.replace("Bearer ", "")

        # Get room
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        # Get queue
        queue = await supabase_service.get_room_queue(room.data["id"])
        if not queue.data:
            raise HTTPException(status_code=404, detail="Queue is empty")

        next_song = queue.data[0]
        track_uri = f"spotify:track:{next_song['spotify_track_id']}"

        # Get all room members
        members = await supabase_service.get_room_members(room.data["id"])

        # Start playback for all members
        errors = []
        for member in members.data:
            user_data = member.get("users")
            if user_data and user_data.get("access_token"):
                try:
                    await spotify_service.start_playback(
                        user_data["access_token"],
                        track_uris=[track_uri]
                    )
                except Exception as e:
                    errors.append(f"User {user_data.get('display_name', 'Unknown')}: {str(e)}")

        # Mark song as played
        await supabase_service.mark_song_played(next_song["id"])

        return {
            "message": "Playing next song",
            "now_playing": next_song,
            "errors": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{room_code}/sync")
async def sync_room_playback(room_code: str, authorization: str = Header(...)):
    """
    Sync all room members to the host's current playback position.
    """
    try:
        access_token = authorization.replace("Bearer ", "")

        # Get room
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        # Get host's current playback
        host = await supabase_service.get_user_by_id(room.data["host_id"])
        if not host.data:
            raise HTTPException(status_code=404, detail="Host not found")

        host_playback = await spotify_service.get_playback_state(host.data["access_token"])
        if not host_playback or not host_playback.get("item"):
            raise HTTPException(status_code=400, detail="Host is not playing anything")

        track_uri = host_playback["item"]["uri"]
        position_ms = host_playback["progress_ms"]
        is_playing = host_playback["is_playing"]

        # Get all room members (except host)
        members = await supabase_service.get_room_members(room.data["id"])

        errors = []
        for member in members.data:
            user_data = member.get("users")
            if user_data and user_data["id"] != room.data["host_id"] and user_data.get("access_token"):
                try:
                    # Start same track at same position
                    await spotify_service.start_playback(
                        user_data["access_token"],
                        track_uris=[track_uri],
                        position_ms=position_ms
                    )
                    # If host is paused, pause member too
                    if not is_playing:
                        await spotify_service.pause_playback(user_data["access_token"])
                except Exception as e:
                    errors.append(f"User {user_data.get('display_name', 'Unknown')}: {str(e)}")

        return {
            "message": "Room synced",
            "track": host_playback["item"]["name"],
            "position_ms": position_ms,
            "is_playing": is_playing,
            "errors": errors if errors else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
