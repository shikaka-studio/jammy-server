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

    # ==================== SONG QUEUE ====================

    async def add_song_to_queue(
        self,
        room_id: str,
        spotify_track_id: str,
        added_by: str,
        track_name: str,
        artist_name: str,
        album_image_url: str | None = None,
        duration_ms: int | None = None
    ):
        data = {
            "room_id": room_id,
            "spotify_track_id": spotify_track_id,
            "added_by": added_by,
            "track_name": track_name,
            "artist_name": artist_name,
            "album_image_url": album_image_url,
            "duration_ms": duration_ms,
            "is_played": False
        }
        return self.client.table("song_queue").insert(data).execute()

    async def get_room_queue(self, room_id: str):
        return (
            self.client.table("song_queue")
            .select("*, users:added_by(display_name, profile_image_url)")
            .eq("room_id", room_id)
            .eq("is_played", False)
            .order("created_at")
            .execute()
        )

    async def get_queue_history(self, room_id: str, limit: int = 20):
        return (
            self.client.table("song_queue")
            .select("*, users:added_by(display_name)")
            .eq("room_id", room_id)
            .eq("is_played", True)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

    async def mark_song_played(self, song_id: str):
        return self.client.table("song_queue").update({"is_played": True}).eq("id", song_id).execute()

    async def remove_song_from_queue(self, song_id: str):
        return self.client.table("song_queue").delete().eq("id", song_id).execute()

    async def reorder_queue(self, song_id: str, new_position: int):
        # This would require more complex logic with a position field
        # For now, we'll keep it simple with created_at ordering
        pass
