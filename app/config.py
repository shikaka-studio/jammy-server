from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration settings"""

    # App
    environment: Literal["development", "production"] = "development"
    frontend_url: str
    full_frontend_url: str

    # API
    api_v1_prefix: str = "/api/v1"

    # Supabase
    supabase_url: str
    supabase_key: str

    # Spotify OAuth
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str

    # Security
    secret_key: str

    # CORS
    allowed_cors_origins: list[str] = [self.frontend_url, self.full_frontend_url]

    # Logging
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def debug(self) -> bool:
        return self.environment == "development"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
