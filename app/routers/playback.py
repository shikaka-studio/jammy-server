from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from app.services.supabase_service import SupabaseService
from app.services.spotify_service import SpotifyService
from app.services.playback_manager import PlaybackManager
from app.dependencies import verify_room_host

router = APIRouter()
supabase_service = SupabaseService()
spotify_service = SpotifyService()
playback_manager = PlaybackManager()


# ==================== ROOM PLAYBACK STATE ====================

@router.get("/room/{room_code}/state")
async def get_room_playback_state(room_code: str):
    """
    Get current playback state for a room's active session.
    Anyone can call this - no authentication required for viewing state.

    Returns:
    {
        "is_playing": bool,
        "current_track": {
            "id": str,
            "name": str,
            "artists": str,
            "album_image_url": str,
            "duration_ms": int,
            "spotify_track_id": str
        } | null,
        "position_ms": int,
        "duration_ms": int,
        "playback_started_at": str | null
    }
    """
    try:
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        # Get active session
        try:
            session = await supabase_service.get_active_session(room.data["id"])
            session_id = session.data["id"]
            state = await playback_manager.get_playback_state(session_id)
            return state
        except Exception:
            # No active session, return empty state
            return {
                "is_playing": False,
                "current_track": None,
                "position_ms": 0,
                "duration_ms": 0,
                "playback_started_at": None
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HOST CONTROLS ====================

@router.post("/room/{room_code}/play")
async def play_room(
    room_code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Start playback in a room (host only).
    If paused, resumes. If stopped, starts from beginning of queue.
    """
    try:
        # Get or create active session
        try:
            session = await supabase_service.get_active_session(room["id"])
            session_id = session.data["id"]
        except Exception:
            # No active session, create one
            session_result = await supabase_service.create_session(room["id"])
            session_id = session_result.data[0]["id"]

        current_state = await playback_manager.get_playback_state(session_id)

        if not current_state["is_playing"] and current_state.get("position_ms", 0) > 0:
            state = await playback_manager.resume_playback(session_id)
        else:
            state = await playback_manager.start_playback(session_id)

        return state
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{room_code}/pause")
async def pause_room(
    room_code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Pause playback in a room (host only).
    """
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.pause_playback(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{room_code}/resume")
async def resume_room(
    room_code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Resume paused playback in a room (host only).
    """
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.resume_playback(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{room_code}/skip")
async def skip_room(
    room_code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Skip to next song in queue (host only).
    """
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.skip_to_next(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LEGACY ENDPOINTS (DEPRECATED) ====================
# These endpoints are kept for individual device testing
# They use Spotify Web API directly (not server-managed playback)

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


@router.get("/devices")
async def get_devices(authorization: str = Header(...)):
    """Get user's available Spotify devices (LEGACY)"""
    try:
        access_token = authorization.replace("Bearer ", "")
        devices = await spotify_service.get_available_devices(access_token)
        return devices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/transfer")
async def transfer_playback(request: TransferRequest, authorization: str = Header(...)):
    """Transfer playback to a different device (LEGACY)"""
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


@router.get("/state")
async def get_playback_state(authorization: str = Header(...)):
    """Get current playback state (LEGACY)"""
    try:
        access_token = authorization.replace("Bearer ", "")
        state = await spotify_service.get_playback_state(access_token)
        return {"playback_state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/currently-playing")
async def get_currently_playing(authorization: str = Header(...)):
    """Get currently playing track (LEGACY)"""
    try:
        access_token = authorization.replace("Bearer ", "")
        current = await spotify_service.get_currently_playing(access_token)
        return {"currently_playing": current}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/play")
async def play(request: PlayTrackRequest | None = None, authorization: str = Header(...)):
    """Start or resume playback (LEGACY)"""
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
    """Pause playback (LEGACY)"""
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
    """Skip to next track (LEGACY)"""
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
    """Skip to previous track (LEGACY)"""
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
    """Seek to position in currently playing track (LEGACY)"""
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
    """Set playback volume (LEGACY)"""
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
