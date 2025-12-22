# Jammy Server

Backend for collaborative Spotify listening rooms.

## Features

- 🎵 Real-time collaborative playback
- 🎧 Session-based room management
- 🔐 Spotify OAuth authentication
- 💬 WebSocket communication
- 🖼️ Room cover image uploads
- 📊 Queue management

## Tech Stack

- **Framework**: FastAPI
- **Database**: Supabase (PostgreSQL)
- **Storage**: Supabase Storage
- **Authentication**: Spotify OAuth 2.0
- **Real-time**: WebSockets

## Setup

### 1. Prerequisites

- Python 3.10+
- Supabase account
- Spotify Developer account

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Environment Variables

Create a `.env` file in the root directory:

```env
# Supabase
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# Spotify OAuth
SPOTIFY_CLIENT_ID=your_spotify_client_id
SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:3000/auth/callback

# App
SECRET_KEY=your_secret_key
FRONTEND_URL=http://localhost:5173
FULL_FRONTEND_URL=http://localhost:5173
```

### 4. Supabase Setup

You can use either a cloud Supabase instance or run Supabase locally with Docker.

#### Local Supabase (Recommended for Development)

**Prerequisites:**

- Docker Desktop (or any container tool with Docker-compatible APIs like Podman, Colima, etc.)
- Node.js (for Supabase CLI)

**Steps:**

1. Install Docker Desktop:
    - Download and install from [docker.com](https://www.docker.com/products/docker-desktop/)
    - Start Docker Desktop and ensure it's running

2. Install Supabase CLI:

```bash
npm install -g supabase
```

3. Initialize Supabase in your project:

```bash
npx supabase init
```

4. Start local Supabase:

```bash
npx supabase start
```

This will:

- Pull and start Supabase Docker containers
- Automatically run migrations from `supabase/migrations/`
- Display connection details including:
    - API URL (use for `SUPABASE_URL`)
    - anon key (use for `SUPABASE_KEY`)
    - Studio URL (local dashboard at `http://localhost:54323`)

3. Update your `.env` file with the local credentials:

```env
SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=<anon_key_from_supabase_start_output>
```

4. Access Supabase Studio at `http://localhost:54323` to manage your local database.

**Useful Commands:**

```bash
# Stop local Supabase
npx supabase stop

# Reset local database (deletes all data)
npx supabase db reset

# Check status
npx supabase status

# Create a new migration
npx supabase migration new <migration_name>
```

#### Storage Bucket Setup

1. Go to Supabase Dashboard → Storage
2. Create a new bucket named `room-covers`
3. Set the bucket to **Public**
4. Configure the following policies:

**Upload Policy:**

```sql
CREATE POLICY "Allow authenticated uploads"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'room-covers');
```

**Read Policy:**

```sql
CREATE POLICY "Allow public read access"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'room-covers');
```

**Delete Policy:**

```sql
CREATE POLICY "Allow authenticated deletes"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'room-covers');
```

### 5. Run the Server

```bash
uvicorn app.main:app --reload
```

The server will be available at `http://localhost:8000`

## API Documentation

Once the server is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Authentication

- `GET /auth/login` - Initiate Spotify OAuth
- `GET /auth/callback` - OAuth callback
- `POST /auth/refresh` - Refresh access token

### Rooms

- `GET /rooms` - Get all rooms
- `POST /rooms/create` - Create a room
- `POST /rooms/join` - Join a room
- `POST /rooms/upload/cover` - Upload room cover image
- `GET /rooms/{code}` - Get room details
- `POST /rooms/{code}/leave` - Leave a room
- `DELETE /rooms/{code}` - Close a room (host only)

### Songs

- `POST /songs/add` - Add song to queue
- `GET /songs/queue/{code}` - Get room queue
- `DELETE /songs/{session_song_id}` - Remove song from queue

### Playback

- `GET /playback/room/{code}/state` - Get playback state
- `POST /playback/room/{code}/play` - Start/resume playback (host only)
- `POST /playback/room/{code}/pause` - Pause playback (host only)
- `POST /playback/room/{code}/resume` - Resume playback (host only)
- `POST /playback/room/{code}/skip` - Skip to next song (host only)

### WebSocket

- `WS /ws/{code}` - WebSocket connection for real-time updates

## Project Structure

```
app/
├── main.py                 # FastAPI application entry point
├── config.py              # Configuration settings
├── dependencies.py        # Dependency injection
├── models/               # Pydantic database models
├── schemas/              # API request/response schemas
├── api/                  # API route handlers
├── services/             # Business logic layer
│   ├── supabase_service.py
│   ├── spotify_service.py
│   ├── playback_manager.py
│   └── websocket_manager.py
└── utils/                # Utility functions
```

## Architecture

### Playback Management

The server manages playback state independently from Spotify's Web Playback SDK:

- Tracks current song and position in database
- Auto-advances to next song when current song ends
- Broadcasts state changes via WebSocket
- Restores playback state on server restart

### WebSocket Messages

- `connected` - Client connected
- `playback_state` - Playback state update
- `queue_update` - Queue changed
- `member_joined` - User joined room
- `member_left` - User left room
- `notification` - General notification
