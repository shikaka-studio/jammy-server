from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class SessionSongBase(BaseModel):
    """Base session song model"""
    session_id: UUID
    song_id: UUID
    position: int = Field(..., ge=0, description="Position in the queue")
    added_by_user_id: UUID


class SessionSongCreate(SessionSongBase):
    """Model for adding a song to session queue"""
    pass


class SessionSongUpdate(BaseModel):
    """Model for updating session song fields"""
    position: int | None = Field(None, ge=0)
    played: bool | None = None
    played_at: datetime | None = None


class SessionSong(SessionSongBase):
    """Complete session song model from database"""
    id: UUID
    played: bool = False
    played_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class SessionSongWithDetails(SessionSong):
    """Session song model with song and user details"""
    song: dict | None = None  # Will contain Song data
    user: dict | None = None  # Will contain UserPublic data (added_by user)

    class Config:
        from_attributes = True


class QueueItem(BaseModel):
    """Simplified queue item for frontend"""
    id: UUID
    song_id: UUID
    spotify_id: str
    title: str
    artist: str
    album: str | None = None
    album_art_url: str | None = None
    duration_ms: int
    position: int
    played: bool
    added_by: dict | None = None  # UserPublic data

    class Config:
        from_attributes = True
