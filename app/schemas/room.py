"""
Room-related request and response schemas for API endpoints.
"""
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime


# ==================== REQUEST SCHEMAS ====================

class CreateRoomRequest(BaseModel):
    """Request schema for creating a new room"""
    name: str = Field(..., min_length=1, max_length=255)
    host_spotify_id: str
    description: str | None = None
    cover_image_url: str | None = None
    tags: list[str] | None = None


class JoinRoomRequest(BaseModel):
    """Request schema for joining a room"""
    code: str = Field(..., min_length=4, max_length=10)
    user_spotify_id: str


class UpdateRoomRequest(BaseModel):
    """Request schema for updating room details"""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    cover_image_url: str | None = None
    tags: list[str] | None = None


# ==================== RESPONSE SCHEMAS ====================

class RoomResponse(BaseModel):
    """Response schema for room data"""
    id: UUID
    code: str
    name: str
    description: str | None = None
    cover_image_url: str | None = None
    tags: list[str] | None = None
    host_id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RoomWithMembersResponse(RoomResponse):
    """Response schema for room with members list"""
    members: list[dict]


class CreateRoomResponse(RoomResponse):
    """Response schema for room creation"""
    pass


class JoinRoomResponse(BaseModel):
    """Response schema for joining a room"""
    room: RoomResponse
    message: str


class UploadCoverImageResponse(BaseModel):
    """Response schema for cover image upload"""
    url: str
    message: str


class LeaveRoomResponse(BaseModel):
    """Response schema for leaving a room"""
    message: str


class CloseRoomResponse(BaseModel):
    """Response schema for closing a room"""
    message: str
