from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.routers import auth, rooms, songs, playback

settings = get_settings()

app = FastAPI(
    title="Jammy Server",
    description="Backend for collaborative Spotify listening rooms",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, settings.full_frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(rooms.router, prefix="/rooms", tags=["Rooms"])
app.include_router(songs.router, prefix="/songs", tags=["Songs"])
app.include_router(playback.router, prefix="/playback", tags=["Playback"])


@app.get("/")
async def root():
    return {"message": "Welcome to Jammy Server!", "status": "running"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
