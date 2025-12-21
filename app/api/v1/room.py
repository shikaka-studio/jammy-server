from fastapi import APIRouter, HTTPException, File, UploadFile
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

        return rooms_with_members
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload/cover", response_model=UploadCoverImageResponse)
async def upload_cover_image(file: UploadFile = File(...)):
    """
    Upload a cover image for a room.
    Accepts: JPEG, PNG, WebP
    Max size: 5MB
    Returns the public URL of the uploaded image.
    """
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    # Validate file size (5MB max)
    max_size = 5 * 1024 * 1024  # 5MB in bytes
    file_data = await file.read()

    if len(file_data) > max_size:
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

        return {
            "url": public_url,
            "message": "Cover image uploaded successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/create", response_model=CreateRoomResponse)
async def create_room(request: CreateRoomRequest):
    """Create a new listening room"""
    try:
        code = generate_room_code()

        # Get user to get their ID
        user = await supabase_service.get_user_by_spotify_id(request.host_spotify_id)
        if not user.data:
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

        return result.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join", response_model=JoinRoomResponse)
async def join_room(request: JoinRoomRequest):
    """Join an existing room"""
    try:
        # Find room by code
        room = await supabase_service.get_room_by_code(request.code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found or inactive")

        # Get user
        user = await supabase_service.get_user_by_spotify_id(request.user_spotify_id)
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        # Add user to room
        await supabase_service.join_room(room.data["id"], user.data["id"])

        return {"room": room.data, "message": "Successfully joined room"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{code}", response_model=RoomWithMembersResponse)
async def get_room(code: str):
    """Get room details with members"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        members = await supabase_service.get_room_members(room.data["id"])
        # Extract only user data, not room_member metadata
        user_list = [member["user"] for member in members.data]

        return {
            **room.data,
            "members": user_list
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{code}/leave", response_model=LeaveRoomResponse)
async def leave_room(code: str, user_spotify_id: str):
    """Leave a room"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        user = await supabase_service.get_user_by_spotify_id(user_spotify_id)
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        await supabase_service.leave_room(room.data["id"], user.data["id"])

        return {"message": "Successfully left room"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{code}", response_model=CloseRoomResponse)
async def close_room(code: str, host_spotify_id: str):
    """Close a room (host only)"""
    try:
        room = await supabase_service.get_room_by_code(code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        user = await supabase_service.get_user_by_spotify_id(host_spotify_id)
        if not user.data or room.data["host_id"] != user.data["id"]:
            raise HTTPException(status_code=403, detail="Only the host can close the room")

        await supabase_service.close_room(room.data["id"])

        return {"message": "Room closed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
