"""
Song-related request and response schemas for API endpoints.
"""
from pydantic import BaseModel, Field
from uuid import UUID


# ==================== REQUEST SCHEMAS ====================

class AddSongRequest(BaseModel):
    """Request schema for adding a song to session queue"""
    code: str = Field(..., description="Room code")
    spotify_track_id: str = Field(..., description="Spotify track ID")
    title: str = Field(..., min_length=1)
    artist: str = Field(..., min_length=1)
    album: str | None = None
    album_art_url: str | None = None
    spotify_uri: str = Field(..., description="Spotify URI (e.g., spotify:track:...)")
    duration_ms: int = Field(..., ge=0)
    user_spotify_id: str


# ==================== RESPONSE SCHEMAS ====================

class QueueItemResponse(BaseModel):
    """Response schema for queue item"""
    id: UUID
    song_id: UUID
    title: str
    artist: str
    album: str | None = None
    album_art_url: str | None = None
    duration_ms: int
    spotify_id: str
    spotify_uri: str
    added_by: dict | None = None


class AddSongResponse(BaseModel):
    """Response schema for adding a song"""
    session_song: dict
    message: str


class RemoveSongResponse(BaseModel):
    """Response schema for removing a song"""
    message: str
