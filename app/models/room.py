from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class RoomBase(BaseModel):
    """Base room model with common fields"""
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    cover_image_url: str | None = None
    tags: list[str] | None = None


class RoomCreate(RoomBase):
    """Model for creating a new room"""
    code: str = Field(..., min_length=4, max_length=10)
    host_id: UUID


class RoomUpdate(BaseModel):
    """Model for updating room fields"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    cover_image_url: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class Room(RoomBase):
    """Complete room model from database"""
    id: UUID
    code: str
    host_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoomWithHost(Room):
    """Room model with host information"""
    host: dict | None = None  # Will contain UserPublic data

    class Config:
        from_attributes = True


class RoomWithMembers(Room):
    """Room model with members list"""
    members: list[dict] | None = None  # Will contain list of UserPublic data
    member_count: int | None = None

    class Config:
        from_attributes = True
