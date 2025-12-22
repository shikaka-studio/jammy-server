from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.logging import get_logger
from app.services.jwt_service import verify_token
from app.services.supabase_service import SupabaseService

logger = get_logger("Dependencies")
security = HTTPBearer()
supabase_service = SupabaseService()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> dict:
    """
    Dependency that validates the JWT token and returns the current user.
    Use this to protect endpoints.
    """
    token = credentials.credentials
    spotify_id = verify_token(token)

    if spotify_id is None:
        logger.warning("Invalid or expired token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await supabase_service.get_user_by_spotify_id(spotify_id)
        if not user.data:
            logger.warning(f"Token valid but user not found: {spotify_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        logger.debug(f"User authenticated: {spotify_id}")
        return user.data
    except Exception:
        logger.error(f"Failed to validate credentials for user: {spotify_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_room_host(
    code: str,
    current_user: dict = Depends(get_current_user)
) -> dict:
    """
    Verify that the current user is the host of the specified room.

    Args:
        code: The room code to verify
        current_user: Current authenticated user (from get_current_user dependency)

    Returns:
        Room data if user is host

    Raises:
        HTTPException(404): Room not found
        HTTPException(403): User is not the host
    """
    logger.debug(f"Verifying host for room {code}, user: {current_user['spotify_id']}")
    try:
        room = await supabase_service.get_room_by_code(code)

        if not room.data:
            logger.warning(f"Room not found for host verification: {code}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.data['host_id'] != current_user['id']:
            logger.warning(f"User {current_user['spotify_id']} is not host of room {code}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the room host can control playback"
            )

        logger.debug(f"Host verified for room {code}")
        return room.data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying room host: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
