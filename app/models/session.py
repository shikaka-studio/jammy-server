from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class SessionBase(BaseModel):
    """Base session model with common fields"""
    room_id: UUID
    is_active: bool = True


class SessionCreate(SessionBase):
    """Model for creating a new session"""
    pass


class SessionUpdate(BaseModel):
    """Model for updating session fields"""
    is_active: bool | None = None
    current_song_id: UUID | None = None
    current_song_start: datetime | None = None  # NULL = paused, timestamp = playing
    paused_position_ms: int | None = Field(None, ge=0)


class SessionPlaybackUpdate(BaseModel):
    """Model for updating session playback state"""
    current_song_id: UUID | None = None
    current_song_start: datetime | None = None
    paused_position_ms: int = Field(default=0, ge=0)


class Session(SessionBase):
    """Complete session model from database"""
    id: UUID
    current_song_id: UUID | None = None
    current_song_start: datetime | None = None
    paused_position_ms: int = 0
    created_at: datetime
    updated_at: datetime
    ended_at: datetime | None = None

    class Config:
        from_attributes = True


class SessionWithSong(Session):
    """Session model with current song information"""
    current_song: dict | None = None  # Will contain Song data

    class Config:
        from_attributes = True
