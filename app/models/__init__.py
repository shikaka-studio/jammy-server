"""
Database models for Jammy Server.
These Pydantic models map to the Supabase database schema.
"""

from .user import (
    User,
    UserBase,
    UserCreate,
    UserUpdate,
    UserTokenUpdate,
    UserPublic,
)
from .room import (
    Room,
    RoomBase,
    RoomCreate,
    RoomUpdate,
    RoomWithHost,
    RoomWithMembers,
)
from .song import (
    Song,
    SongBase,
    SongCreate,
    SongPublic,
)
from .session import (
    Session,
    SessionBase,
    SessionCreate,
    SessionUpdate,
    SessionPlaybackUpdate,
    SessionWithSong,
)
from .room_member import (
    RoomMember,
    RoomMemberBase,
    RoomMemberCreate,
    RoomMemberWithUser,
)
from .session_song import (
    SessionSong,
    SessionSongBase,
    SessionSongCreate,
    SessionSongUpdate,
    SessionSongWithDetails,
    QueueItem,
)

__all__ = [
    # User models
    "User",
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserTokenUpdate",
    "UserPublic",
    # Room models
    "Room",
    "RoomBase",
    "RoomCreate",
    "RoomUpdate",
    "RoomWithHost",
    "RoomWithMembers",
    # Song models
    "Song",
    "SongBase",
    "SongCreate",
    "SongPublic",
    # Session models
    "Session",
    "SessionBase",
    "SessionCreate",
    "SessionUpdate",
    "SessionPlaybackUpdate",
    "SessionWithSong",
    # Room member models
    "RoomMember",
    "RoomMemberBase",
    "RoomMemberCreate",
    "RoomMemberWithUser",
    # Session song models
    "SessionSong",
    "SessionSongBase",
    "SessionSongCreate",
    "SessionSongUpdate",
    "SessionSongWithDetails",
    "QueueItem",
]
