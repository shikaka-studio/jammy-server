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
        profile_image_url: str | None = None,
        token_expires_at: str | None = None
    ):
        data = {
            "spotify_id": spotify_id,
            "display_name": display_name,
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "product": product,
            "profile_image_url": profile_image_url,
            "token_expires_at": token_expires_at
        }
        return self.client.table("user").upsert(data, on_conflict="spotify_id").execute()

    async def get_user_by_spotify_id(self, spotify_id: str):
        return self.client.table("user").select("*").eq("spotify_id", spotify_id).single().execute()

    async def get_user_by_id(self, user_id: str):
        return self.client.table("user").select("*").eq("id", user_id).single().execute()

    async def update_user_tokens(
        self,
        spotify_id: str,
        access_token: str,
        refresh_token: str | None = None,
        token_expires_at: str | None = None
    ):
        """
        Update user tokens.

        Args:
            spotify_id: User's Spotify ID
            access_token: New access token (required)
            refresh_token: New refresh token (optional)
            token_expires_at: Token expiration timestamp (optional)
        """
        data = {"access_token": access_token}

        # Only update optional fields if explicitly provided
        if refresh_token is not None:
            data["refresh_token"] = refresh_token
        if token_expires_at is not None:
            data["token_expires_at"] = token_expires_at

        return self.client.table("user").update(data).eq("spotify_id", spotify_id).execute()

    # ==================== ROOM OPERATIONS ====================

    async def create_room(
        self,
        name: str,
        host_id: str,
        code: str,
        description: str | None = None,
        cover_image_url: str | None = None,
        tags: list[str] | None = None
    ):
        data = {
            "name": name,
            "host_id": host_id,
            "code": code,
            "is_active": True,
            "description": description,
            "cover_image_url": cover_image_url,
            "tags": tags
        }
        return self.client.table("room").insert(data).execute()

    async def get_room_by_code(self, code: str):
        return self.client.table("room").select("*").eq("code", code).eq("is_active", True).single().execute()

    async def get_room_by_id(self, room_id: str):
        return self.client.table("room").select("*").eq("id", room_id).single().execute()

    async def get_all_rooms(self):
        """Get all rooms - only returns host_id, not sensitive host data"""
        return self.client.table("room").select("*").execute()

    async def get_rooms_by_host(self, host_id: str):
        return self.client.table("room").select("*").eq("host_id", host_id).eq("is_active", True).execute()

    async def update_room(self, room_id: str, **kwargs):
        """
        Update room fields dynamically.

        Args:
            room_id: Room ID
            **kwargs: Fields to update (name, description, cover_image_url, tags)
        """
        # Validate and filter allowed fields for security
        allowed_fields = {"name", "description", "cover_image_url", "tags"}
        data = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not data:
            raise ValueError("No valid fields provided for update")

        return self.client.table("room").update(data).eq("id", room_id).execute()

    async def close_room(self, room_id: str):
        return self.client.table("room").update({"is_active": False}).eq("id", room_id).execute()

    # ==================== ROOM MEMBERS ====================

    async def join_room(self, room_id: str, user_id: str):
        data = {"room_id": room_id, "user_id": user_id}
        return self.client.table("room_member").upsert(data, on_conflict="room_id,user_id").execute()

    async def leave_room(self, room_id: str, user_id: str):
        return self.client.table("room_member").delete().eq("room_id", room_id).eq("user_id", user_id).execute()

    async def get_room_members(self, room_id: str):
        """Get room members - only returns safe user fields (id, spotify_id, display_name, profile_image_url)"""
        return self.client.table("room_member").select("*, user(id, spotify_id, display_name, profile_image_url)").eq("room_id", room_id).execute()

    async def is_user_in_room(self, room_id: str, user_id: str):
        result = self.client.table("room_member").select("*").eq("room_id", room_id).eq("user_id", user_id).execute()
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

    async def get_all_active_sessions(self):
        """Get all active sessions"""
        return self.client.table("session").select("*").eq("is_active", True).execute()

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
        **kwargs
    ):
        """
        Update playback state for a session.

        Args:
            session_id: Session ID
            current_song_id: Song ID (pass None to reset)
            current_song_start: ISO timestamp when song started (pass None to reset)
            paused_position_ms: Position in ms when paused (pass 0 to reset)
        """
        # Only include fields that were explicitly provided
        # This allows us to set fields to None or 0 for reset
        valid_fields = {"current_song_id", "current_song_start", "paused_position_ms"}
        data = {k: v for k, v in kwargs.items() if k in valid_fields}

        return self.client.table("session").update(data).eq("id", session_id).execute()

    # ==================== SONG OPERATIONS (song table) ====================

    async def create_or_get_song(
        self,
        spotify_id: str,
        title: str,
        artist: str,
        spotify_uri: str,
        duration_ms: int,
        album: str | None = None,
        album_art_url: str | None = None
    ):
        """Create a song in the song table or get existing one by spotify_id"""
        # Try to get existing song first
        try:
            existing = await self.get_song_by_spotify_id(spotify_id)
            if existing.data:
                return existing
        except Exception:
            pass

        # Song doesn't exist, create it
        data = {
            "spotify_id": spotify_id,
            "title": title,
            "artist": artist,
            "album": album,
            "duration_ms": duration_ms,
            "album_art_url": album_art_url,
            "spotify_uri": spotify_uri
        }
        return self.client.table("song").insert(data).execute()

    async def get_song_by_spotify_id(self, spotify_id: str):
        """Get a song from the song table by Spotify ID"""
        return self.client.table("song").select("*").eq("spotify_id", spotify_id).single().execute()

    async def get_song_by_id(self, song_id: str):
        """Get a song from the song table by ID"""
        return self.client.table("song").select("*").eq("id", song_id).single().execute()

    # ==================== SESSION SONG OPERATIONS (session_song table) ====================

    async def add_song_to_session(
        self,
        session_id: str,
        song_id: str,
        added_by_user_id: str,
        position: int
    ):
        """Add a song to a session's queue"""
        data = {
            "session_id": session_id,
            "song_id": song_id,
            "added_by_user_id": added_by_user_id,
            "position": position,
            "played": False
        }
        return self.client.table("session_song").insert(data).execute()

    async def get_session_queue(self, session_id: str):
        """Get all unplayed songs in session queue, ordered by position"""
        return (
            self.client.table("session_song")
            .select("*, song:song_id(*), user:added_by_user_id(id, spotify_id, display_name, profile_image_url)")
            .eq("session_id", session_id)
            .eq("played", False)
            .order("position")
            .execute()
        )

    async def get_recently_played_songs(self, session_id: str):
        """Get recently played songs in session, ordered by played_at (most recent first)"""
        return (
            self.client.table("session_song")
            .select("*, song:song_id(*), user:added_by_user_id(id, spotify_id, display_name, profile_image_url)")
            .eq("session_id", session_id)
            .eq("played", True)
            .order("played_at", desc=True)
            .execute()
        )

    async def get_next_session_song(self, session_id: str):
        """Get the next unplayed song in session queue"""
        return (
            self.client.table("session_song")
            .select("*, song:song_id(*)")
            .eq("session_id", session_id)
            .eq("played", False)
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
            "played": True,
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

    # ==================== STORAGE OPERATIONS ====================

    async def upload_room_cover_image(self, file_data: bytes, file_name: str, content_type: str) -> str:
        """
        Upload room cover image to Supabase Storage and return public URL.

        Args:
            file_data: Image file bytes
            file_name: Name of the file
            content_type: MIME type of the file

        Returns:
            Public URL of the uploaded image
        """
        bucket_name = "room-covers"

        # Generate unique filename with timestamp
        from datetime import datetime
        import uuid
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}_{file_name}"

        # Upload to Supabase Storage
        self.client.storage.from_(bucket_name).upload(
            path=unique_filename,
            file=file_data,
            file_options={"content-type": content_type}
        )

        # Get public URL
        public_url = self.client.storage.from_(bucket_name).get_public_url(unique_filename)
        return public_url

    async def delete_room_cover_image(self, file_url: str) -> bool:
        """
        Delete room cover image from Supabase Storage.

        Args:
            file_url: Public URL of the image to delete

        Returns:
            True if deletion was successful
        """
        bucket_name = "room-covers"

        # Extract filename from URL
        # URL format: https://{project}.supabase.co/storage/v1/object/public/room-covers/{filename}
        filename = file_url.split("/")[-1]

        try:
            self.client.storage.from_(bucket_name).remove([filename])
            return True
        except Exception:
            return False
