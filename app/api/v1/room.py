from fastapi import APIRouter, HTTPException, File, UploadFile
from app.core.logging import get_logger
from app.services.supabase_service import SupabaseService
from app.schemas.room import (
    CreateRoomRequest, 
    JoinRoomRequest, 
    UploadCoverImageResponse,
    RoomWithMembersResponse,
    CreateRoomResponse,
    JoinRoomResponse,
    LeaveRoomResponse,
    CloseRoomResponse
)
import secrets
import string

logger = get_logger("api.room")
router = APIRouter()
supabase_service = SupabaseService()


def generate_room_code(length: int = 6) -> str:
    """Generate a random room code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@router.get("", response_model=list[RoomWithMembersResponse])
async def get_all_rooms():
    """Get all rooms with host and members info"""
    try:
        logger.info("Fetching all rooms with members")
        result = await supabase_service.get_all_rooms()

        rooms_with_members = []
        for room in result.data:
            members = await supabase_service.get_room_members(room["id"])
            # Extract only user data, not room_member metadata
            user_list = [member["user"] for member in members.data]
            rooms_with_members.append({
                **room,
                "members": user_list
            })

        logger.info(f"Successfully fetched {len(rooms_with_members)} rooms")
        return rooms_with_members
    except Exception as e:
        logger.error(f"Error fetching rooms: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/cover", response_model=UploadCoverImageResponse)
async def upload_cover_image(file: UploadFile = File(...)):
    """
    Upload a cover image for a room.
    Accepts: JPEG, PNG, WebP
    Max size: 5MB
    Returns the public URL of the uploaded image.
    """
    logger.info(f"Attempting to upload cover image: {file.filename}")
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        logger.warning(f"Invalid file type attempted: {file.content_type}")
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Validate file size (5MB max)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    file_data = await file.read()

    if len(file_data) > max_size:
        logger.warning(f"File too large: {len(file_data)} bytes")
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 5MB"
        )

    try:
        # Upload to Supabase Storage
        public_url = await supabase_service.upload_room_cover_image(
            file_data=file_data,
            file_name=file.filename or "cover.jpg",
            content_type=file.content_type
        )

        logger.info(f"Successfully uploaded cover image: {file.filename}")
        return {
            "url": public_url,
            "message": "Cover image uploaded successfully"
        }
    except Exception as e:
        logger.error(f"Failed to upload cover image: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(request: CreateRoomRequest):
    """Create a new listening room"""
    logger.info(f"Creating room: {request.name} by {request.host_spotify_id}")
    try:
        code = generate_room_code()
        logger.debug(f"Generated room code: {code}")

        # Get user to get their ID
        user = await supabase_service.get_user_by_spotify_id(request.host_spotify_id)
        if not user.data:
            logger.warning(f"User not found: {request.host_spotify_id}")
            raise HTTPException(status_code=404, detail="User not found")

        result = await supabase_service.create_room(
            name=request.name,
            host_id=user.data["id"],
            code=code,
            description=request.description,
            cover_image_url=request.cover_image_url,
            tags=request.tags
        )

        # Host automatically joins the room
        await supabase_service.join_room(result.data[0]["id"], user.data["id"])

        logger.info(f"Room created: {request.name} ({code}) by {user.data.get('display_name', request.host_spotify_id)}")
        return result.data[0]
    except Exception as e:
        logger.error(f"Failed to create room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join", response_model=JoinRoomResponse)
async def join_room(request: JoinRoomRequest):
    """Join an existing room"""
    try:
        # Find room by code
        room = await supabase_service.get_room_by_code(request.code)
        if not room.data:
            logger.warning(f"Room not found: {request.code}")
            raise HTTPException(status_code=404, detail="Room not found or inactive")

        # Get user
        user = await supabase_service.get_user_by_spotify_id(request.user_spotify_id)
        if not user.data:
            logger.warning(f"User not found: {request.user_spotify_id}")
            raise HTTPException(status_code=404, detail="User not found")

        room_name = room.data.get("name", request.code)
        user_name = user.data.get("display_name", request.user_spotify_id)
        logger.info(f"User {user_name} joining room {room_name} ({request.code})")

        # Add user to room
        await supabase_service.join_room(room.data["id"], user.data["id"])

        logger.info(f"User {request.user_spotify_id} joined room {request.code} successfully")
        return {"room": room.data, "message": "Successfully joined room"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to join room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}", response_model=RoomWithMembersResponse)
async def get_room(code: str):
    """Get room details with members"""
    logger.debug(f"Fetching room details: {code}")
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            logger.warning(f"Room not found: {code}")
            raise HTTPException(status_code=404, detail="Room not found")

        members = await supabase_service.get_room_members(room.data["id"])
        # Extract only user data, not room_member metadata
        user_list = [member["user"] for member in members.data]

        logger.debug(f"Room {code} has {len(user_list)} members")
        return {
            **room.data,
            "members": user_list
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{code}/leave", response_model=LeaveRoomResponse)
async def leave_room(code: str, user_spotify_id: str):
    """Leave a room"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            logger.warning(f"Room not found: {code}")
            raise HTTPException(status_code=404, detail="Room not found")

        user = await supabase_service.get_user_by_spotify_id(user_spotify_id)
        if not user.data:
            logger.warning(f"User not found: {user_spotify_id}")
            raise HTTPException(status_code=404, detail="User not found")

        room_name = room.data.get("name", code)
        user_name = user.data.get("display_name", user_spotify_id)
        logger.info(f"User {user_name} leaving room {room_name} ({code})")

        await supabase_service.leave_room(room.data["id"], user.data["id"])

        return {"message": "Successfully left room"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to leave room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{code}", response_model=CloseRoomResponse)
async def close_room(code: str, host_spotify_id: str):
    """Close a room (host only)"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            logger.warning(f"Room not found: {code}")
            raise HTTPException(status_code=404, detail="Room not found")

        user = await supabase_service.get_user_by_spotify_id(host_spotify_id)
        if not user.data or room.data["host_id"] != user.data["id"]:
            logger.warning(f"User {host_spotify_id} is not the host of room {code}")
            raise HTTPException(status_code=403, detail="Only the host can close the room")

        room_name = room.data.get("name", code)
        host_name = user.data.get("display_name", host_spotify_id)
        logger.info(f"Host {host_name} closing room {room_name} ({code})")

        await supabase_service.close_room(room.data["id"])

        return {"message": "Room closed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to close room: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
