"""
Authentication-related request and response schemas for API endpoints.
"""
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


# ==================== RESPONSE SCHEMAS ====================

class UserProfileResponse(BaseModel):
    """Response schema for user profile"""
    id: UUID
    spotify_id: str
    display_name: str
    email: str | None = None
    product: str | None = None
    profile_image_url: str | None = None
    created_at: datetime
    access_token: str


class RefreshTokenResponse(BaseModel):
    """Response schema for token refresh"""
    message: str
    access_token: str


class LogoutResponse(BaseModel):
    """Response schema for logout"""
    message: str
