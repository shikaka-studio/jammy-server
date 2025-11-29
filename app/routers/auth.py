from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from app.services.spotify_service import SpotifyService
from app.services.supabase_service import SupabaseService
from app.config import get_settings
import secrets

router = APIRouter()
settings = get_settings()
spotify_service = SpotifyService()
supabase_service = SupabaseService()


@router.get("/login")
async def login():
    """Initiate Spotify OAuth flow"""
    state = secrets.token_urlsafe(16)
    auth_url = spotify_service.get_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(code: str = Query(...), state: str = Query(None)):
    """Handle Spotify OAuth callback"""
    try:
        # Exchange code for tokens
        token_data = await spotify_service.exchange_code_for_tokens(code)

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error_description"])

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")

        # Get user profile
        user_profile = await spotify_service.get_current_user(access_token)
        image_url = user_profile.get("images", [{}])[0].get("url", "")

        # Save/update user in database
        await supabase_service.create_user(
            spotify_id=user_profile["id"],
            display_name=user_profile.get("display_name", ""),
            email=user_profile.get("email", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            profile_image_url=image_url
        )

        # Redirect to frontend with tokens
        redirect_url = (
            f"{settings.frontend_url}/auth/callback"
            f"?access_token={access_token}"
            f"&spotify_id={user_profile['id']}"
        )
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh an expired access token"""
    try:
        token_data = await spotify_service.refresh_access_token(refresh_token)

        if "error" in token_data:
            raise HTTPException(status_code=400, detail=token_data["error_description"])

        return {
            "access_token": token_data["access_token"],
            "expires_in": token_data["expires_in"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
async def get_current_user(spotify_id: str):
    """Get current user from database"""
    try:
        user = await supabase_service.get_user_by_spotify_id(spotify_id)
        return user.data
    except Exception as e:
        raise HTTPException(status_code=404, detail="User not found")
