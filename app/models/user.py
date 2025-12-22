from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


class UserBase(BaseModel):
    """Base user model with common fields"""
    spotify_id: str
    display_name: str
    email: str | None = None
    profile_image_url: str | None = None
    product: str | None = None  # Spotify subscription tier: 'premium', 'free', 'open', etc.


class UserCreate(UserBase):
    """Model for creating a new user"""
    access_token: str
    refresh_token: str
    token_expires_at: datetime | None = None


class UserUpdate(BaseModel):
    """Model for updating user fields"""
    display_name: str | None = None
    email: str | None = None
    profile_image_url: str | None = None
    product: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


class UserTokenUpdate(BaseModel):
    """Model for updating user tokens"""
    access_token: str
    refresh_token: str | None = None
    token_expires_at: datetime | None = None


class User(UserBase):
    """Complete user model from database"""
    id: UUID
    access_token: str | None = None  # Optional for security in responses
    refresh_token: str | None = None  # Optional for security in responses
    token_expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserPublic(BaseModel):
    """Public user model without sensitive data"""
    id: UUID
    spotify_id: str
    display_name: str
    profile_image_url: str | None = None
    product: str | None = None

    class Config:
        from_attributes = True
