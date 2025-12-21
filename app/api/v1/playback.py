from fastapi import APIRouter, HTTPException, Depends
from app.core.logging import get_logger
from app.services.supabase_service import SupabaseService
from app.services.playback_manager import PlaybackManager
from app.dependencies import verify_room_host
from app.utils.formatters import format_playback_state
from app.schemas.playback import PlaybackStateResponse

logger = get_logger("api.playback")
router = APIRouter()
supabase_service = SupabaseService()
playback_manager = PlaybackManager()


# ==================== ROOM PLAYBACK STATE ====================

@router.get("/room/{code}/state", response_model=PlaybackStateResponse)
async def get_room_playback_state(code: str):
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
        "playback_started_at": str | null
    }
    """
    logger.debug(f"Fetching playback state for room: {code}")
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            logger.warning(f"Room not found: {code}")
            raise HTTPException(status_code=404, detail="Room not found")

        # Get active session
        try:
            session = await supabase_service.get_active_session(room.data["id"])
            session_id = session.data["id"]
            state = await playback_manager.get_playback_state(session_id)
            return state
        except Exception:
            # No active session, return empty state
            logger.debug(f"No active session for room {code}, returning empty state")
            return format_playback_state(
                is_playing=False,
                current_track=None,
                position_ms=0,
                playback_started_at=None
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch playback state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ==================== HOST CONTROLS ====================

@router.post("/room/{code}/play", response_model=PlaybackStateResponse)
async def play_room(
    code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Start playback in a room (host only).
    If paused, resumes. If stopped, starts from beginning of queue.
    """
    logger.info(f"Play command for room: {code}")
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
        logger.error(f"Failed to start playback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{code}/pause", response_model=PlaybackStateResponse)
async def pause_room(
    code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Pause playback in a room (host only).
    """
    room_name = room.get("name", code)
    logger.info(f"Pause command for room {room_name} ({code})")
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            logger.warning(f"No active session for room: {code}")
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.pause_playback(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to pause playback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{code}/resume", response_model=PlaybackStateResponse)
async def resume_room(
    code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Resume paused playback in a room (host only).
    """
    room_name = room.get("name", code)
    logger.info(f"Resume command for room {room_name} ({code})")
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            logger.warning(f"No active session for room: {code}")
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.resume_playback(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to resume playback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/room/{code}/skip", response_model=PlaybackStateResponse)
async def skip_room(
    code: str,
    room: dict = Depends(verify_room_host)
):
    """
    Skip to next song in queue (host only).
    """
    logger.info(f"Skip command for room: {code}")
    try:
        # Get active session
        session = await supabase_service.get_active_session(room["id"])
        if not session.data:
            logger.warning(f"No active session for room: {code}")
            raise HTTPException(status_code=404, detail="No active session")

        session_id = session.data["id"]
        state = await playback_manager.skip_to_next(session_id)
        return state
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to skip song: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
