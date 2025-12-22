from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import RedirectResponse
from app.core.logging import get_logger
from app.services.spotify_service import SpotifyService
from app.services.supabase_service import SupabaseService
from app.services.jwt_service import create_access_token
from app.dependencies import get_current_user
from app.config import get_settings
from app.schemas.auth import UserProfileResponse, RefreshTokenResponse, LogoutResponse
import secrets

logger = get_logger("api.auth")

# Router for protected API endpoints
router = APIRouter()

# Router for OAuth endpoints (no /api/v1 prefix)
oauth_router = APIRouter()

settings = get_settings()
spotify_service = SpotifyService()
supabase_service = SupabaseService()


@oauth_router.get("/login")
async def login():
    """Initiate Spotify OAuth flow"""
    logger.info("Initiating Spotify OAuth flow")
    state = secrets.token_urlsafe(16)
    auth_url = spotify_service.get_auth_url(state)
    return RedirectResponse(url=auth_url)


@oauth_router.get("/callback")
async def callback(code: str = Query(...), state: str = Query(None)):
    """Handle Spotify OAuth callback"""
    logger.info("Processing Spotify OAuth callback")
    try:
        # Exchange code for tokens
        token_data = await spotify_service.exchange_code_for_tokens(code)

        if "error" in token_data:
            logger.warning(f"OAuth token exchange failed: {token_data.get('error_description')}")
            raise HTTPException(status_code=400, detail=token_data["error_description"])

        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")

        # Get user profile
        user_profile = await spotify_service.get_current_user(access_token)
        spotify_id = user_profile["id"]
        image_url = user_profile.get("images", [{}])[0].get("url", "")

        logger.info(f"User authenticated: {spotify_id} ({user_profile.get('display_name', 'Unknown')})")

        # Save/update user in database
        await supabase_service.create_user(
            spotify_id=spotify_id,
            display_name=user_profile.get("display_name", ""),
            email=user_profile.get("email", ""),
            access_token=access_token,
            refresh_token=refresh_token,
            product=user_profile.get("product", ""),
            profile_image_url=image_url
        )

        # Create our own JWT token for the frontend
        jwt_token = create_access_token(spotify_id)

        # Redirect to frontend with our JWT token
        redirect_url = (
            f"{settings.frontend_url}/callback"
            f"?token={jwt_token}"
        )
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(current_user: dict = Depends(get_current_user)):
    """
    Get the current authenticated user's profile.
    Protected endpoint - requires valid JWT token.
    """
    logger.info(f"Fetching profile for user: {current_user['spotify_id']}")
    return {
        "id": current_user["id"],
        "spotify_id": current_user["spotify_id"],
        "display_name": current_user["display_name"],
        "email": current_user["email"],
        "product": current_user["product"],
        "profile_image_url": current_user.get("profile_image_url"),
        "created_at": current_user["created_at"],
        "access_token": current_user["access_token"],
    }

@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_spotify_token(current_user: dict = Depends(get_current_user)):
    """
    Refresh the user's Spotify access token.
    Protected endpoint - requires valid JWT token.
    """
    logger.info(f"Refreshing token for user: {current_user['spotify_id']}")
    try:
        refresh_token = current_user.get("refresh_token")
        if not refresh_token:
            logger.warning(f"No refresh token available for user: {current_user['spotify_id']}")
            raise HTTPException(status_code=400, detail="No refresh token available")

        token_data = await spotify_service.refresh_access_token(refresh_token)

        if "error" in token_data:
            logger.error(f"Token refresh failed: {token_data.get('error_description')}")
            raise HTTPException(status_code=400, detail=token_data.get("error_description", "Refresh failed"))

        # Update tokens in database
        new_access_token = token_data["access_token"]
        new_refresh_token = token_data.get("refresh_token", refresh_token)

        await supabase_service.update_user_tokens(
            current_user["spotify_id"],
            new_access_token,
            new_refresh_token
        )

        logger.info(f"Token refreshed successfully for user: {current_user['spotify_id']}")
        return {
            "message": "Spotify token refreshed successfully",
            "access_token": new_access_token
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: dict = Depends(get_current_user)):
    """
    Logout the user (optional: could invalidate tokens in DB).
    For now, the frontend just discards the JWT.
    """
    logger.info(f"User logged out: {current_user['spotify_id']}")
    return {"message": "Logged out successfully"}
