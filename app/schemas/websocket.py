"""
WebSocket message schemas.
"""
from pydantic import BaseModel
from uuid import UUID
from typing import Literal


# ==================== MESSAGE SCHEMAS ====================

class WebSocketMessage(BaseModel):
    """Base WebSocket message schema"""
    type: str
    data: dict


class ConnectedMessage(BaseModel):
    """WebSocket connected message"""
    type: Literal["connected"]
    data: dict


class PlaybackStateMessage(BaseModel):
    """WebSocket playback state update message"""
    type: Literal["playback_state"]
    data: dict


class QueueUpdateMessage(BaseModel):
    """WebSocket queue update message"""
    type: Literal["queue_update"]
    data: dict


class MemberJoinedMessage(BaseModel):
    """WebSocket member joined message"""
    type: Literal["member_joined"]
    data: dict


class MemberLeftMessage(BaseModel):
    """WebSocket member left message"""
    type: Literal["member_left"]
    data: dict


class NotificationMessage(BaseModel):
    """WebSocket notification message"""
    type: Literal["notification"]
    data: dict


class PongMessage(BaseModel):
    """WebSocket pong response"""
    type: Literal["pong"]
    data: dict
