
from typing import Dict, List, Optional, Any


def format_song(song: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a song object for API responses.

    Args:
        song: Song dictionary from database

    Returns:
        Formatted song dictionary
    """
    return {
        "id": song["id"],
        "title": song["title"],
        "artist": song["artist"],
        "album": song.get("album"),
        "album_art_url": song["album_art_url"],
        "duration_ms": song["duration_ms"],
        "spotify_id": song["spotify_id"],
        "spotify_uri": song["spotify_uri"]
    }


def format_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a user object for API responses.

    Args:
        user: User dictionary from database

    Returns:
        Formatted user dictionary
    """
    return {
        "id": user["id"],
        "spotify_id": user["spotify_id"],
        "display_name": user["display_name"],
        "profile_image_url": user["profile_image_url"]
    }


def format_session_song(session_song: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a session song (queue item) for API responses.

    Args:
        session_song: Session song dictionary from database (includes song and user)

    Returns:
        Formatted session song dictionary
    """
    return {
        "id": session_song["id"],
        "title": session_song["song"]["title"],
        "artist": session_song["song"]["artist"],
        "album": session_song["song"].get("album"),
        "album_art_url": session_song["song"]["album_art_url"],
        "duration_ms": session_song["song"]["duration_ms"],
        "spotify_id": session_song["song"]["spotify_id"],
        "spotify_uri": session_song["song"]["spotify_uri"],
        "added_by": format_user(session_song["user"]) if session_song.get("user") else None
    }


def format_session_song_with_played_at(session_song: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format a session song with played_at timestamp (for recently played).

    Args:
        session_song: Session song dictionary from database (includes song, user, and played_at)

    Returns:
        Formatted session song dictionary with played_at field
    """
    formatted = format_session_song(session_song)
    formatted["played_at"] = session_song.get("played_at")
    return formatted


def format_queue_update(
    queue: List[Dict[str, Any]],
    recently_played: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Format a queue update message for WebSocket broadcast.

    Args:
        queue: List of session songs in queue
        recently_played: Optional list of recently played songs

    Returns:
        Formatted queue update data
    """
    return {
        "queue": [format_session_song(s) for s in queue],
        "recently_played": [
            format_session_song_with_played_at(s) for s in recently_played
        ] if recently_played else []
    }


def format_playback_state(
    is_playing: bool,
    current_track: Optional[Dict[str, Any]] = None,
    position_ms: int = 0,
    playback_started_at: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format playback state for API responses and WebSocket messages.

    Args:
        is_playing: Whether playback is active
        current_track: Currently playing song (if any)
        position_ms: Current position in milliseconds
        playback_started_at: ISO timestamp when playback started

    Returns:
        Formatted playback state dictionary
    """
    return {
        "is_playing": is_playing,
        "current_track": format_song(current_track) if current_track else None,
        "position_ms": position_ms,
        "playback_started_at": playback_started_at
    }
