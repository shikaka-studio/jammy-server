import httpx
import base64
from urllib.parse import urlencode
from app.config import get_settings

settings = get_settings()


class SpotifyService:
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE_URL = "https://api.spotify.com/v1"

    # Scopes needed for the app
    SCOPES = [
        "user-read-email",
        "user-read-private",
        "user-modify-playback-state",
        "user-read-playback-state",
        "user-read-currently-playing",
        "streaming",
        "app-remote-control"
    ]

    def __init__(self):
        self.client_id = settings.spotify_client_id
        self.client_secret = settings.spotify_client_secret
        self.redirect_uri = settings.spotify_redirect_uri

    def _get_auth_header(self) -> str:
        """Generate Base64 encoded auth header for client credentials"""
        credentials = f"{self.client_id}:{self.client_secret}"
        return base64.b64encode(credentials.encode()).decode()

    # ==================== AUTHENTICATION ====================

    def get_auth_url(self, state: str) -> str:
        """Generate Spotify OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "show_dialog": "true"  # Always show login dialog
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_tokens(self, code: str) -> dict:
        """Exchange authorization code for access and refresh tokens"""
        headers = {
            "Authorization": f"Basic {self._get_auth_header()}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> dict:
        """Refresh an expired access token"""
        headers = {
            "Authorization": f"Basic {self._get_auth_header()}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(self.TOKEN_URL, headers=headers, data=data)
            response.raise_for_status()
            return response.json()

    # ==================== USER ====================

    async def get_current_user(self, access_token: str) -> dict:
        """Get the current user's Spotify profile"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.API_BASE_URL}/me", headers=headers)
            response.raise_for_status()
            return response.json()

    # ==================== SEARCH ====================

    async def search_tracks(self, access_token: str, query: str, limit: int = 20) -> dict:
        """Search for tracks on Spotify"""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/search",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()

    async def get_track(self, access_token: str, track_id: str) -> dict:
        """Get track details by ID"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/tracks/{track_id}",
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def get_tracks(self, access_token: str, track_ids: list[str]) -> dict:
        """Get multiple tracks by IDs (max 50)"""
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"ids": ",".join(track_ids[:50])}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/tracks",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            return response.json()

    # ==================== PLAYBACK ====================

    async def get_playback_state(self, access_token: str) -> dict | None:
        """Get information about the user's current playback state"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/me/player",
                headers=headers
            )
            if response.status_code == 204:
                return None  # No active device
            response.raise_for_status()
            return response.json()

    async def get_available_devices(self, access_token: str) -> dict:
        """Get a list of user's available devices"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/me/player/devices",
                headers=headers
            )
            response.raise_for_status()
            return response.json()

    async def start_playback(
        self,
        access_token: str,
        track_uris: list[str] | None = None,
        context_uri: str | None = None,
        device_id: str | None = None,
        position_ms: int = 0
    ) -> bool:
        """Start or resume playback"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }

        url = f"{self.API_BASE_URL}/me/player/play"
        if device_id:
            url += f"?device_id={device_id}"

        # Build request body
        body = {}
        if track_uris:
            body["uris"] = track_uris
        if context_uri:
            body["context_uri"] = context_uri
        if position_ms > 0:
            body["position_ms"] = position_ms

        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, json=body if body else None)
            return response.status_code in [200, 202, 204]

    async def pause_playback(self, access_token: str, device_id: str | None = None) -> bool:
        """Pause playback"""
        headers = {"Authorization": f"Bearer {access_token}"}

        url = f"{self.API_BASE_URL}/me/player/pause"
        if device_id:
            url += f"?device_id={device_id}"

        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers)
            return response.status_code in [200, 202, 204]

    async def skip_to_next(self, access_token: str, device_id: str | None = None) -> bool:
        """Skip to next track"""
        headers = {"Authorization": f"Bearer {access_token}"}

        url = f"{self.API_BASE_URL}/me/player/next"
        if device_id:
            url += f"?device_id={device_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            return response.status_code in [200, 202, 204]

    async def skip_to_previous(self, access_token: str, device_id: str | None = None) -> bool:
        """Skip to previous track"""
        headers = {"Authorization": f"Bearer {access_token}"}

        url = f"{self.API_BASE_URL}/me/player/previous"
        if device_id:
            url += f"?device_id={device_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers)
            return response.status_code in [200, 202, 204]

    async def seek_to_position(self, access_token: str, position_ms: int, device_id: str | None = None) -> bool:
        """Seek to position in currently playing track"""
        headers = {"Authorization": f"Bearer {access_token}"}

        url = f"{self.API_BASE_URL}/me/player/seek"
        params = {"position_ms": position_ms}
        if device_id:
            params["device_id"] = device_id

        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, params=params)
            return response.status_code in [200, 202, 204]

    async def set_volume(self, access_token: str, volume_percent: int, device_id: str | None = None) -> bool:
        """Set playback volume (0-100)"""
        headers = {"Authorization": f"Bearer {access_token}"}

        url = f"{self.API_BASE_URL}/me/player/volume"
        params = {"volume_percent": max(0, min(100, volume_percent))}
        if device_id:
            params["device_id"] = device_id

        async with httpx.AsyncClient() as client:
            response = await client.put(url, headers=headers, params=params)
            return response.status_code in [200, 202, 204]

    async def transfer_playback(self, access_token: str, device_id: str, play: bool = False) -> bool:
        """Transfer playback to a different device"""
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        body = {
            "device_ids": [device_id],
            "play": play
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.API_BASE_URL}/me/player",
                headers=headers,
                json=body
            )
            return response.status_code in [200, 202, 204]

    async def get_currently_playing(self, access_token: str) -> dict | None:
        """Get the currently playing track"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.API_BASE_URL}/me/player/currently-playing",
                headers=headers
            )
            if response.status_code == 204:
                return None
            response.raise_for_status()
            return response.json()
