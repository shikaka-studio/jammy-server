from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.supabase_service import SupabaseService
import secrets
import string

router = APIRouter()
supabase_service = SupabaseService()


class CreateRoomRequest(BaseModel):
    name: str
    host_spotify_id: str


class JoinRoomRequest(BaseModel):
    room_code: str
    user_spotify_id: str


def generate_room_code(length: int = 6) -> str:
    """Generate a random room code"""
    characters = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(characters) for _ in range(length))


@router.get("")
async def get_all_rooms():
    """Get all rooms with host and members info"""
    try:
        result = await supabase_service.get_all_rooms()

        rooms_with_members = []
        for room in result.data:
            members = await supabase_service.get_room_members(room["id"])
            rooms_with_members.append({
                "room": room,
                "members": members.data
            })

        return {"rooms": rooms_with_members}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create")
async def create_room(request: CreateRoomRequest):
    """Create a new listening room"""
    try:
        room_code = generate_room_code()

        # Get user to get their ID
        user = await supabase_service.get_user_by_spotify_id(request.host_spotify_id)
        if not user.data:
            raise HTTPException(status_code=404, detail="User not found")

        result = await supabase_service.create_room(
            name=request.name,
            host_id=user.data["id"],
            room_code=room_code
        )

        # Host automatically joins the room
        await supabase_service.join_room(result.data[0]["id"], user.data["id"])

        return {
            "room": result.data[0],
            "room_code": room_code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/join")
async def join_room(request: JoinRoomRequest):
    """Join an existing room"""
    try:
        # Find room by code
        room = await supabase_service.get_room_by_code(request.room_code)
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


@router.get("/{room_code}")
async def get_room(room_code: str):
    """Get room details"""
    try:
        room = await supabase_service.get_room_by_code(room_code)
        if not room.data:
            raise HTTPException(status_code=404, detail="Room not found")

        members = await supabase_service.get_room_members(room.data["id"])

        return {
            "room": room.data,
            "members": members.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{room_code}/leave")
async def leave_room(room_code: str, user_spotify_id: str):
    """Leave a room"""
    try:
        room = await supabase_service.get_room_by_code(room_code)
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


@router.delete("/{room_code}")
async def close_room(room_code: str, host_spotify_id: str):
    """Close a room (host only)"""
    try:
        room = await supabase_service.get_room_by_code(room_code)
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
