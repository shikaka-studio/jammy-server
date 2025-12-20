from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.jwt_service import verify_token
from app.services.supabase_service import SupabaseService

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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user = await supabase_service.get_user_by_spotify_id(spotify_id)
        if not user.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        return user.data
    except Exception:
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
    try:
        room = await supabase_service.get_room_by_code(code)

        if not room.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Room not found"
            )

        if room.data['host_id'] != current_user['id']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the room host can control playback"
            )

        return room.data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
