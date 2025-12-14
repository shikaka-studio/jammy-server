from supabase import create_client, Client
from app.config import get_settings

settings = get_settings()


def get_supabase_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)


class SupabaseService:
    def __init__(self):
        self.client = get_supabase_client()

    # ==================== USER OPERATIONS ====================

    async def create_user(
        self,
        spotify_id: str,
        display_name: str,
        email: str,
        access_token: str,
        refresh_token: str,
        product: str,
        profile_image_url: str | None = None
    ):
        data = {
            "spotify_id": spotify_id,
            "display_name": display_name,
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "product": product,
            "profile_image_url": profile_image_url
        }
        return self.client.table("users").upsert(data, on_conflict="spotify_id").execute()

    async def get_user_by_spotify_id(self, spotify_id: str):
        return self.client.table("users").select("*").eq("spotify_id", spotify_id).single().execute()

    async def get_user_by_id(self, user_id: str):
        return self.client.table("users").select("*").eq("id", user_id).single().execute()

    async def update_user_tokens(self, spotify_id: str, access_token: str, refresh_token: str | None = None):
        data = {"access_token": access_token}
        if refresh_token:
            data["refresh_token"] = refresh_token
        return self.client.table("users").update(data).eq("spotify_id", spotify_id).execute()

    # ==================== ROOM OPERATIONS ====================

    async def create_room(self, name: str, host_id: str, room_code: str):
        data = {
            "name": name,
            "host_id": host_id,
            "room_code": room_code,
            "is_active": True
        }
        return self.client.table("rooms").insert(data).execute()

    async def get_room_by_code(self, room_code: str):
        return self.client.table("rooms").select("*").eq("room_code", room_code).eq("is_active", True).single().execute()

    async def get_room_by_id(self, room_id: str):
        return self.client.table("rooms").select("*").eq("id", room_id).single().execute()

    async def get_all_rooms(self):
        return self.client.table("rooms").select("*, host:users!host_id(*)").execute()

    async def get_rooms_by_host(self, host_id: str):
        return self.client.table("rooms").select("*").eq("host_id", host_id).eq("is_active", True).execute()

    async def update_room_playback(self, room_id: str, track_uri: str, position_ms: int):
        data = {
            "current_track_uri": track_uri,
            "current_position_ms": position_ms
        }
        return self.client.table("rooms").update(data).eq("id", room_id).execute()

    async def close_room(self, room_id: str):
        return self.client.table("rooms").update({"is_active": False}).eq("id", room_id).execute()

    # ==================== ROOM MEMBERS ====================

    async def join_room(self, room_id: str, user_id: str):
        data = {"room_id": room_id, "user_id": user_id}
        return self.client.table("room_members").upsert(data, on_conflict="room_id,user_id").execute()

    async def leave_room(self, room_id: str, user_id: str):
        return self.client.table("room_members").delete().eq("room_id", room_id).eq("user_id", user_id).execute()

    async def get_room_members(self, room_id: str):
        return self.client.table("room_members").select("*, users(*)").eq("room_id", room_id).execute()

    async def is_user_in_room(self, room_id: str, user_id: str):
        result = self.client.table("room_members").select("*").eq("room_id", room_id).eq("user_id", user_id).execute()
        return len(result.data) > 0

    # ==================== SESSION OPERATIONS ====================

    async def create_session(self, room_id: str):
        """Create a new session for a room"""
        data = {
            "room_id": room_id,
            "is_active": True
        }
        return self.client.table("session").insert(data).execute()

    async def get_active_session(self, room_id: str):
        """Get the active session for a room"""
        return (
            self.client.table("session")
            .select("*")
            .eq("room_id", room_id)
            .eq("is_active", True)
            .single()
            .execute()
        )

    async def get_session_by_id(self, session_id: str):
        """Get session by ID"""
        return self.client.table("session").select("*").eq("id", session_id).single().execute()

    async def end_session(self, session_id: str):
        """End a session by setting is_active to False and setting ended_at"""
        from datetime import datetime, timezone
        data = {
            "is_active": False,
            "ended_at": datetime.now(timezone.utc).isoformat()
        }
        return self.client.table("session").update(data).eq("id", session_id).execute()

    async def update_session_playback_state(
        self,
        session_id: str,
        current_song: str | None = None,
        current_song_start: str | None = None,
        current_song_duration_ms: int | None = None,
        paused_position_ms: int | None = None
    ):
        """Update playback state for a session"""
        data = {}

        if current_song is not None:
            data["current_song"] = current_song
        if current_song_start is not None:
            data["current_song_start"] = current_song_start
        if current_song_duration_ms is not None:
            data["current_song_duration_ms"] = current_song_duration_ms
        if paused_position_ms is not None:
            data["paused_position_ms"] = paused_position_ms

        return self.client.table("session").update(data).eq("id", session_id).execute()

    # ==================== SONG OPERATIONS (song table) ====================

    async def create_or_get_song(
        self,
        spotify_track_id: str,
        track_name: str,
        artist_name: str,
        album_image_url: str | None = None,
        duration_ms: int | None = None
    ):
        """Create a song in the song table or get existing one by spotify_track_id"""
        data = {
            "spotify_track_id": spotify_track_id,
            "track_name": track_name,
            "artist_name": artist_name,
            "album_image_url": album_image_url,
            "duration_ms": duration_ms
        }
        return self.client.table("song").upsert(data, on_conflict="spotify_track_id").execute()

    async def get_song_by_spotify_id(self, spotify_track_id: str):
        """Get a song from the song table by Spotify track ID"""
        return self.client.table("song").select("*").eq("spotify_track_id", spotify_track_id).single().execute()

    # ==================== SESSION SONG OPERATIONS (session_song table) ====================

    async def add_song_to_session(
        self,
        session_id: str,
        song_id: str,
        added_by: str,
        position: int
    ):
        """Add a song to a session's queue"""
        data = {
            "session_id": session_id,
            "song_id": song_id,
            "added_by": added_by,
            "position": position,
            "is_played": False
        }
        return self.client.table("session_song").insert(data).execute()

    async def get_session_queue(self, session_id: str):
        """Get all unplayed songs in session queue, ordered by position"""
        return (
            self.client.table("session_song")
            .select("*, song:song_id(*), user:added_by(display_name, profile_image_url)")
            .eq("session_id", session_id)
            .eq("is_played", False)
            .order("position")
            .execute()
        )

    async def get_next_session_song(self, session_id: str):
        """Get the next unplayed song in session queue"""
        return (
            self.client.table("session_song")
            .select("*, song:song_id(*)")
            .eq("session_id", session_id)
            .eq("is_played", False)
            .order("position")
            .limit(1)
            .execute()
        )

    async def get_session_song_by_id(self, session_song_id: str):
        """Get a session_song by ID"""
        return self.client.table("session_song").select("*, song:song_id(*)").eq("id", session_song_id).execute()

    async def mark_session_song_played(self, session_song_id: str):
        """Mark a session_song as played"""
        from datetime import datetime, timezone
        data = {
            "is_played": True,
            "played_at": datetime.now(timezone.utc).isoformat()
        }
        return self.client.table("session_song").update(data).eq("id", session_song_id).execute()

    async def remove_session_song(self, session_song_id: str):
        """Remove a song from session queue"""
        return self.client.table("session_song").delete().eq("id", session_song_id).execute()

    async def get_next_position_in_session(self, session_id: str) -> int:
        """Get the next position number for adding a song to session queue"""
        result = (
            self.client.table("session_song")
            .select("position")
            .eq("session_id", session_id)
            .order("position", desc=True)
            .limit(1)
            .execute()
        )

        if result.data and len(result.data) > 0:
            return result.data[0]["position"] + 1
        return 0

