"""
Playback-related response schemas for API endpoints.
"""
from pydantic import BaseModel


# ==================== RESPONSE SCHEMAS ====================

class CurrentTrackResponse(BaseModel):
    """Response schema for current track info"""
    id: str
    title: str
    artist: str
    album: str | None = None
    album_art_url: str | None = None
    duration_ms: int
    spotify_id: str
    spotify_uri: str


class PlaybackStateResponse(BaseModel):
    """Response schema for playback state"""
    is_playing: bool
    current_track: CurrentTrackResponse | None = None
    position_ms: int
    playback_started_at: str | None = None
