from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, room, song, playback, websocket
from app.config import get_settings
from app.core.logging import setup_logging, get_logger
from app.services.playback_manager import PlaybackManager
from app.services.supabase_service import SupabaseService

# Configure logging before anything else
setup_logging()
logger = get_logger(__name__)

settings = get_settings()
playback_manager = PlaybackManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Restore playback state from database
    logger.info("Application startup: Restoring playback state from database...")
    try:
        supabase_service = SupabaseService()

        # Get all active sessions
        sessions_result = await supabase_service.get_all_active_sessions()

        for session in sessions_result.data:
            # Only restore if session has a current song playing
            if session.get('current_song_start'):
                logger.info(f"Restoring playback for session {session['id']}")
                await playback_manager.restore_from_database(session['id'])

        logger.info("Playback state restored successfully")
    except Exception as e:
        logger.error(f"Error restoring playback state: {e}", exc_info=True)

    yield

    # Shutdown: Cancel all session tasks
    logger.info("Application shutdown: Cancelling all playback tasks...")
    for session_id in list(playback_manager.session_tasks.keys()):
        await playback_manager._cancel_session_task(session_id)
    logger.info("All tasks cancelled successfully")


app = FastAPI(
    title="Jammy Server",
    description="Backend for collaborative Spotify listening rooms",
    version="1.0.0",
    debug=settings.debug,
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# OAuth endpoints (no /api/v1 prefix for Spotify redirects)
app.include_router(auth.oauth_router, prefix="/auth", tags=["OAuth"])

# API v1 endpoints
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["Authentication"])
app.include_router(room.router, prefix=f"{settings.api_v1_prefix}/rooms", tags=["Rooms"])
app.include_router(song.router, prefix=f"{settings.api_v1_prefix}/songs", tags=["Songs"])
app.include_router(playback.router, prefix=f"{settings.api_v1_prefix}/playback", tags=["Playback"])
app.include_router(websocket.router, tags=["WebSocket"])


@app.get("/")
async def root():
    return {"message": "Welcome to Jammy Server!", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
