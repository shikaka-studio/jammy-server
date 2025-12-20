import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from app.services.supabase_service import SupabaseService
from app.services.websocket_manager import websocket_manager


class PlaybackManager:
    """
    Manages playback state for all sessions.
    Runs background tasks to auto-play next songs.
    Independent of client connections.
    """

    def __init__(self):
        self.supabase_service = SupabaseService()
        self.session_tasks: Dict[str, asyncio.Task] = {}
        self.session_playback_state: Dict[str, dict] = {}

    async def start_playback(
        self,
        session_id: str,
        session_song_id: Optional[str] = None,
        position_ms: int = 0
    ) -> dict:
        """
        Start playback for a session.

        Args:
            session_id: Session ID
            session_song_id: Session song ID to play (if None, gets next from queue)
            position_ms: Starting position (for seeking/resuming)
        """
        if session_song_id is None:
            next_song = await self.supabase_service.get_next_session_song(session_id)
            if not next_song.data:
                await self.supabase_service.update_session_playback_state(
                    session_id=session_id,
                    current_song_id=None,
                    current_song_start=None,
                    paused_position_ms=0
                )
                return {
                    "is_playing": False,
                    "current_track": None,
                    "position_ms": 0,
                    "playback_started_at": None,
                    "message": "Queue is empty"
                }
            session_song = next_song.data[0]
            session_song_id = session_song["id"]
            song = session_song["song"]
        else:
            session_song_result = await self.supabase_service.get_session_song_by_id(session_song_id)
            if not session_song_result.data:
                raise Exception("Session song not found")
            session_song = session_song_result.data[0]
            song = session_song["song"]

        now = datetime.now(timezone.utc)
        remaining_duration = song["duration_ms"] - position_ms
        end_time = now + timedelta(milliseconds=remaining_duration)

        # Store in-memory state
        self.session_playback_state[session_id] = {
            "session_song_id": session_song_id,
            "song": song,
            "started_at": now,
            "position_ms": position_ms,
            "end_time": end_time,
            "is_playing": True,
        }

        # Update database
        await self.supabase_service.update_session_playback_state(
            session_id=session_id,
            current_song_id=song["id"],
            current_song_start=now.isoformat(),
            paused_position_ms=0
        )

        # Cancel existing task
        await self._cancel_session_task(session_id)

        # Start background task to auto-play next song
        task = asyncio.create_task(
            self._auto_play_next(session_id, session_song_id, remaining_duration)
        )
        self.session_tasks[session_id] = task

        # Get session to broadcast with room_id
        session = await self.supabase_service.get_session_by_id(session_id)
        room_id = session.data["room_id"]

        # Broadcast playback state to all clients
        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "playback_state",
                "data": {
                    "is_playing": True,
                    "current_track": {
                        "id": song["id"],
                        "title": song["title"],
                        "artist": song["artist"],
                        "album": song.get("album"),
                        "album_art_url": song["album_art_url"],
                        "duration_ms": song["duration_ms"],
                        "spotify_id": song["spotify_id"],
                        "spotify_uri": song["spotify_uri"]
                    },
                    "position_ms": position_ms,
                    "playback_started_at": now.isoformat()
                }
            }
        )

        return {
            "is_playing": True,
            "current_track": {
                "id": song["id"],
                "title": song["title"],
                "artist": song["artist"],
                "album": song.get("album"),
                "album_art_url": song["album_art_url"],
                "duration_ms": song["duration_ms"],
                "spotify_id": song["spotify_id"],
                "spotify_uri": song["spotify_uri"]
            },
            "position_ms": position_ms,
            "playback_started_at": now.isoformat()
        }

    async def pause_playback(self, session_id: str) -> dict:
        """
        Pause playback for a session.
        Calculates and stores current position.
        """
        state = self.session_playback_state.get(session_id)

        if state and state["is_playing"]:
            elapsed = (datetime.now(timezone.utc) - state["started_at"]).total_seconds() * 1000
            current_position = state["position_ms"] + int(elapsed)

            if state["song"].get("duration_ms"):
                current_position = min(current_position, state["song"]["duration_ms"])
        else:
            session = await self.supabase_service.get_session_by_id(session_id)
            if not session.data:
                raise Exception("Session not found")
            current_position = session.data.get("paused_position_ms", 0)

        # Update in-memory state
        if session_id in self.session_playback_state:
            self.session_playback_state[session_id]["is_playing"] = False
            self.session_playback_state[session_id]["position_ms"] = current_position

        # Update database - clear current_song_start and set paused position
        await self.supabase_service.update_session_playback_state(
            session_id=session_id,
            current_song_start=None,
            paused_position_ms=current_position
        )

        # Cancel background task
        await self._cancel_session_task(session_id)

        # Broadcast pause state
        playback_state = await self.get_playback_state(session_id)

        session = await self.supabase_service.get_session_by_id(session_id)
        room_id = session.data["room_id"]

        await websocket_manager.broadcast_to_room(
            room_id,
            {
                "type": "playback_state",
                "data": playback_state
            }
        )

        return playback_state

    async def resume_playback(self, session_id: str) -> dict:
        """
        Resume paused playback.
        Resets playback_started_at to account for pause duration.
        """
        session = await self.supabase_service.get_session_by_id(session_id)
        if not session.data:
            raise Exception("Session not found")

        session_data = session.data

        # Check if already playing (has current_song_start)
        if session_data.get("current_song_start"):
            return await self.get_playback_state(session_id)

        current_position_ms = session_data.get("paused_position_ms", 0)
        current_song_id = session_data.get("current_song_id")

        if not current_song_id:
            return await self.start_playback(session_id)

        # Get session_song for the current song
        session_songs = await self.supabase_service.get_session_queue(session_id)
        current_session_song = None
        for ss in session_songs.data:
            if ss["song"]["id"] == current_song_id:
                current_session_song = ss
                break

        if not current_session_song:
            return await self.start_playback(session_id)

        # Resume from paused position
        return await self.start_playback(
            session_id=session_id,
            session_song_id=current_session_song["id"],
            position_ms=current_position_ms
        )

    async def skip_to_next(self, session_id: str) -> dict:
        """
        Skip to next song in queue.
        Marks current song as played and starts next song.
        """
        state = self.session_playback_state.get(session_id)

        if state:
            await self.supabase_service.mark_session_song_played(state["session_song_id"])
        else:
            session = await self.supabase_service.get_session_by_id(session_id)
            if session.data and session.data.get("current_song_id"):
                # Find current session_song
                queue = await self.supabase_service.get_session_queue(session_id)
                for session_song in queue.data:
                    if session_song["song"]["id"] == session.data["current_song_id"]:
                        await self.supabase_service.mark_session_song_played(session_song["id"])
                        break

        # Cancel current task
        await self._cancel_session_task(session_id)

        # Play next song
        return await self._play_next_song(session_id)

    async def get_playback_state(self, session_id: str) -> dict:
        """
        Get current playback state for a session.
        Calculates current position based on elapsed time.
        """
        state = self.session_playback_state.get(session_id)

        if not state:
            session = await self.supabase_service.get_session_by_id(session_id)
            if not session.data:
                raise Exception("Session not found")

            session_data = session.data
            is_playing = bool(session_data.get("current_song_start"))

            if not is_playing or not session_data.get("current_song_id"):
                return {
                    "is_playing": False,
                    "current_track": None,
                    "position_ms": 0,
                    "playback_started_at": None
                }

            # Get song data
            song_result = await self.supabase_service.get_song_by_id(session_data["current_song_id"])
            if not song_result.data:
                return {
                    "is_playing": False,
                    "current_track": None,
                    "position_ms": 0,
                    "playback_started_at": None
                }

            song = song_result.data
            started_at = datetime.fromisoformat(session_data["current_song_start"].replace("Z", "+00:00"))

            state = {
                "song": song,
                "started_at": started_at,
                "position_ms": session_data.get("paused_position_ms", 0),
                "is_playing": is_playing,
            }

        # Calculate current position
        if state["is_playing"]:
            elapsed = (datetime.now(timezone.utc) - state["started_at"]).total_seconds() * 1000
            current_position = state["position_ms"] + int(elapsed)
        else:
            current_position = state["position_ms"]

        current_track = None
        if state.get("song"):
            song = state["song"]
            current_track = {
                "id": song["id"],
                "title": song["title"],
                "artist": song["artist"],
                "album": song.get("album"),
                "album_art_url": song["album_art_url"],
                "duration_ms": song["duration_ms"],
                "spotify_id": song["spotify_id"],
                "spotify_uri": song["spotify_uri"]
            }

        return {
            "is_playing": state["is_playing"],
            "current_track": current_track,
            "position_ms": current_position,
            "playback_started_at": state["started_at"].isoformat() if state.get("started_at") else None
        }

    async def handle_song_added(self, session_id: str) -> None:
        """
        Handle when a song is added to session queue.
        Auto-starts playback if queue was empty and not playing.
        """
        session = await self.supabase_service.get_session_by_id(session_id)
        if not session.data:
            return

        session_data = session.data

        # Auto-start if not playing and no current song
        if not session_data.get("current_song_start") and not session_data.get("current_song_id"):
            await self.start_playback(session_id)

    async def restore_from_database(self, session_id: str) -> None:
        """
        Restore playback state from database.
        Used when server restarts.
        """
        session = await self.supabase_service.get_session_by_id(session_id)
        if not session.data or not session.data.get("current_song_start"):
            return

        session_data = session.data

        # Get song data
        song_result = await self.supabase_service.get_song_by_id(session_data["current_song_id"])
        if not song_result.data:
            return

        song = song_result.data
        started_at = datetime.fromisoformat(session_data["current_song_start"].replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - started_at).total_seconds() * 1000
        current_position = int(elapsed)

        # Get session_song
        queue = await self.supabase_service.get_session_queue(session_id)
        current_session_song = None
        for ss in queue.data:
            if ss["song"]["id"] == session_data["current_song_id"]:
                current_session_song = ss
                break

        if not current_session_song:
            await self._play_next_song(session_id)
            return

        if current_position >= song["duration_ms"]:
            await self._play_next_song(session_id)
        else:
            await self.start_playback(
                session_id=session_id,
                session_song_id=current_session_song["id"],
                position_ms=current_position
            )

    # ==================== PRIVATE METHODS ====================

    async def _auto_play_next(
        self,
        session_id: str,
        session_song_id: str,
        duration_ms: int
    ):
        """
        Background task that waits for song to end, then plays next.

        Args:
            session_id: Session ID
            session_song_id: Current session song ID
            duration_ms: Remaining duration in milliseconds
        """
        try:
            duration_seconds = duration_ms / 1000
            print(f"[PlaybackManager] Auto-play timer started for {duration_seconds}s in session {session_id}")

            await asyncio.sleep(duration_seconds)

            print(f"[PlaybackManager] Song ended in session {session_id}, playing next")

            await self.supabase_service.mark_session_song_played(session_song_id)
            await self._play_next_song(session_id)

        except asyncio.CancelledError:
            print(f"[PlaybackManager] Auto-play cancelled for session {session_id}")
            raise
        except Exception as e:
            print(f"[PlaybackManager] Error in auto-play: {e}")

    async def _play_next_song(self, session_id: str) -> dict:
        """
        Play the next song in queue.
        If no songs left, stop playback.
        """
        next_song = await self.supabase_service.get_next_session_song(session_id)

        session = await self.supabase_service.get_session_by_id(session_id)
        room_id = session.data["room_id"]

        if next_song.data:
            session_song = next_song.data[0]
            song = session_song["song"]
            print(f"[PlaybackManager] Playing next song: {song['title']}")

            result = await self.start_playback(
                session_id=session_id,
                session_song_id=session_song["id"],
                position_ms=0
            )

            # Broadcast queue update
            remaining_queue = await self.supabase_service.get_session_queue(session_id)
            recently_played = await self.supabase_service.get_recently_played_songs(session_id)

            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "queue_update",
                    "data": {
                        "queue": [
                            {
                                "id": s["id"],
                                "title": s["song"]["title"],
                                "artist": s["song"]["artist"],
                                "album": s["song"].get("album"),
                                "album_art_url": s["song"]["album_art_url"],
                                "duration_ms": s["song"]["duration_ms"],
                                "spotify_id": s["song"]["spotify_id"],
                                "spotify_uri": s["song"]["spotify_uri"],
                                "added_by": {
                                    "id": s["user"]["id"],
                                    "spotify_id": s["user"]["spotify_id"],
                                    "display_name": s["user"]["display_name"],
                                    "profile_image_url": s["user"]["profile_image_url"]
                                } if s.get("user") else None
                            }
                            for s in remaining_queue.data
                        ] if remaining_queue.data else [],
                        "recently_played": [
                            {
                                "id": s["id"],
                                "title": s["song"]["title"],
                                "artist": s["song"]["artist"],
                                "album": s["song"].get("album"),
                                "album_art_url": s["song"]["album_art_url"],
                                "duration_ms": s["song"]["duration_ms"],
                                "spotify_id": s["song"]["spotify_id"],
                                "spotify_uri": s["song"]["spotify_uri"],
                                "played_at": s.get("played_at"),
                                "added_by": {
                                    "id": s["user"]["id"],
                                    "spotify_id": s["user"]["spotify_id"],
                                    "display_name": s["user"]["display_name"],
                                    "profile_image_url": s["user"]["profile_image_url"]
                                } if s.get("user") else None
                            }
                            for s in recently_played.data
                        ] if recently_played.data else []
                    }
                }
            )

            return result
        else:
            print(f"[PlaybackManager] No more songs in queue for session {session_id}")

            await self.supabase_service.update_session_playback_state(
                session_id=session_id,
                current_song_id=None,
                current_song_start=None,
                paused_position_ms=0
            )

            if session_id in self.session_playback_state:
                del self.session_playback_state[session_id]

            # Broadcast empty state, queue update, and notification
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "playback_state",
                    "data": {
                        "is_playing": False,
                        "current_track": None,
                        "position_ms": 0,
                        "playback_started_at": None
                    }
                }
            )

            # Broadcast queue update with empty queue and recently played
            recently_played = await self.supabase_service.get_recently_played_songs(session_id)
            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "queue_update",
                    "data": {
                        "queue": [],
                        "recently_played": [
                            {
                                "id": s["id"],
                                "title": s["song"]["title"],
                                "artist": s["song"]["artist"],
                                "album": s["song"].get("album"),
                                "album_art_url": s["song"]["album_art_url"],
                                "duration_ms": s["song"]["duration_ms"],
                                "spotify_id": s["song"]["spotify_id"],
                                "spotify_uri": s["song"]["spotify_uri"],
                                "played_at": s.get("played_at"),
                                "added_by": {
                                    "id": s["user"]["id"],
                                    "spotify_id": s["user"]["spotify_id"],
                                    "display_name": s["user"]["display_name"],
                                    "profile_image_url": s["user"]["profile_image_url"]
                                } if s.get("user") else None
                            }
                            for s in recently_played.data
                        ] if recently_played.data else []
                    }
                }
            )

            await websocket_manager.broadcast_to_room(
                room_id,
                {
                    "type": "notification",
                    "data": {
                        "message": "Queue is empty! Add more songs to continue.",
                        "level": "info"
                    }
                }
            )

            return {
                "is_playing": False,
                "current_track": None,
                "position_ms": 0,
                "playback_started_at": None,
                "message": "Queue is empty"
            }

    async def _cancel_session_task(self, session_id: str):
        """Cancel background task for a session"""
        if session_id in self.session_tasks:
            self.session_tasks[session_id].cancel()
            try:
                await self.session_tasks[session_id]
            except asyncio.CancelledError:
                pass
            del self.session_tasks[session_id]
