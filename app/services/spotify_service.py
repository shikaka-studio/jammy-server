import httpx
import base64
from urllib.parse import urlencode
from app.core.logging import get_logger
from app.config import get_settings

logger = get_logger("SpotifyService")
settings = get_settings()


class SpotifyService:
    AUTH_URL = "https://accounts.spotify.com/authorize"
    TOKEN_URL = "https://accounts.spotify.com/api/token"
    API_BASE_URL = "https://api.spotify.com/v1"

    # Scopes needed for the app
    SCOPES = [
        "user-read-email",
        "user-read-private",
        "streaming",  # Required for Web Playback SDK
        "user-read-playback-state",  # Read playback state
        "user-modify-playback-state",  # Control playback (play, pause, skip, etc.)
        "user-read-currently-playing"  # Get currently playing track
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
            try:
                response = await client.post(self.TOKEN_URL, headers=headers, data=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Token exchange failed: HTTP {e.response.status_code}", exc_info=True)
                raise

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
            try:
                response = await client.post(self.TOKEN_URL, headers=headers, data=data)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Token refresh failed: HTTP {e.response.status_code}", exc_info=True)
                raise

    # ==================== USER ====================

    async def get_current_user(self, access_token: str) -> dict:
        """Get the current user's Spotify profile"""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{self.API_BASE_URL}/me", headers=headers)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to fetch user profile: HTTP {e.response.status_code}", exc_info=True)
                raise
