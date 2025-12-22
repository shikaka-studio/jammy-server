"""
API request and response schemas (DTOs).
Separate from database models - these are for API endpoints.
"""

from .room import (
    CreateRoomRequest,
    JoinRoomRequest,
    UpdateRoomRequest,
    RoomResponse,
    RoomWithMembersResponse,
    CreateRoomResponse,
    JoinRoomResponse,
    UploadCoverImageResponse,
)
from .song import (
    AddSongRequest,
    QueueItemResponse,
    AddSongResponse,
)
from .playback import (
    CurrentTrackResponse,
    PlaybackStateResponse,
)
from .auth import (
    UserProfileResponse,
    RefreshTokenResponse,
    LogoutResponse,
)
from .websocket import (
    WebSocketMessage,
    ConnectedMessage,
    PlaybackStateMessage,
    QueueUpdateMessage,
    MemberJoinedMessage,
    MemberLeftMessage,
    NotificationMessage,
    PongMessage,
)

__all__ = [
    # Room schemas
    "CreateRoomRequest",
    "JoinRoomRequest",
    "UpdateRoomRequest",
    "RoomResponse",
    "RoomWithMembersResponse",
    "CreateRoomResponse",
    "JoinRoomResponse",
    "UploadCoverImageResponse",
    # Song schemas
    "AddSongRequest",
    "QueueItemResponse",
    "AddSongResponse",
    # Playback schemas
    "CurrentTrackResponse",
    "PlaybackStateResponse",
    # Auth schemas
    "UserProfileResponse",
    "RefreshTokenResponse",
    "LogoutResponse",
    # WebSocket schemas
    "WebSocketMessage",
    "ConnectedMessage",
    "PlaybackStateMessage",
    "QueueUpdateMessage",
    "MemberJoinedMessage",
    "MemberLeftMessage",
    "NotificationMessage",
    "PongMessage",
]
