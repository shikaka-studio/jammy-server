from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class SongBase(BaseModel):
    """Base song model with common fields"""
    spotify_id: str = Field(..., description="Spotify track ID")
    title: str = Field(..., min_length=1, max_length=500)
    artist: str = Field(..., min_length=1, max_length=500)
    album: str | None = Field(None, max_length=500)
    duration_ms: int = Field(..., ge=0)
    album_art_url: str | None = None
    spotify_uri: str = Field(..., description="Spotify URI (e.g., spotify:track:...)")


class SongCreate(SongBase):
    """Model for creating a new song"""
    pass


class Song(SongBase):
    """Complete song model from database"""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class SongPublic(BaseModel):
    """Public song model with essential fields"""
    id: UUID
    spotify_id: str
    title: str
    artist: str
    album: str | None = None
    duration_ms: int
    album_art_url: str | None = None
    spotify_uri: str

    class Config:
        from_attributes = True
