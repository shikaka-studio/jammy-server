from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_key: str

    # Spotify OAuth
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str

    # App
    secret_key: str
    frontend_url: str
    full_frontend_url: str

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
