from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class RoomMemberBase(BaseModel):
    """Base room member model"""
    room_id: UUID
    user_id: UUID


class RoomMemberCreate(RoomMemberBase):
    """Model for adding a member to a room"""
    pass


class RoomMember(RoomMemberBase):
    """Complete room member model from database"""
    id: UUID
    joined_at: datetime

    class Config:
        from_attributes = True


class RoomMemberWithUser(RoomMember):
    """Room member model with user information"""
    user: dict | None = None  # Will contain UserPublic data

    class Config:
        from_attributes = True
