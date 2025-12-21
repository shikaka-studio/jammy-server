-- Jammy Server Database Schema
-- Supabase PostgreSQL Migration Script

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- USERS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS "user" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spotify_id VARCHAR(255) UNIQUE NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    profile_image_url TEXT,
    product VARCHAR(50), -- Spotify subscription tier: 'premium', 'free', 'open', etc.
    access_token TEXT,
    refresh_token TEXT,
    token_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for faster Spotify ID lookups
CREATE INDEX idx_user_spotify_id ON "user"(spotify_id);

-- ============================================================================
-- ROOMS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS room (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    cover_image_url TEXT,
    tags TEXT[], -- Array of tags for room categorization
    host_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE, -- Track if room is closed/archived
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for room code lookups
CREATE INDEX idx_room_code ON room(code);
CREATE INDEX idx_room_host_id ON room(host_id);

-- ============================================================================
-- SESSIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS session (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID NOT NULL REFERENCES room(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT TRUE,
    current_song_id UUID, -- References song table, added later with FK
    current_song_start TIMESTAMPTZ, -- NULL = paused, timestamp = playing
    paused_position_ms INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

-- Index for active session lookups per room
CREATE INDEX idx_session_room_id ON session(room_id);
CREATE INDEX idx_session_active ON session(is_active) WHERE is_active = TRUE;

-- Constraint: Only one active session per room
CREATE UNIQUE INDEX idx_session_one_active_per_room 
    ON session(room_id) 
    WHERE is_active = TRUE;

-- ============================================================================
-- SONGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS song (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    spotify_id VARCHAR(255) UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    artist VARCHAR(500) NOT NULL,
    album VARCHAR(500),
    duration_ms INTEGER NOT NULL,
    album_art_url TEXT,
    spotify_uri VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for Spotify ID lookups (song deduplication)
CREATE INDEX idx_song_spotify_id ON song(spotify_id);

-- ============================================================================
-- SESSION_SONG (Queue) TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS session_song (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES session(id) ON DELETE CASCADE,
    song_id UUID NOT NULL REFERENCES song(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    added_by_user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    played BOOLEAN DEFAULT FALSE,
    played_at TIMESTAMPTZ, -- Timestamp when the song was played
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for queue ordering and lookups
CREATE INDEX idx_session_song_session_id ON session_song(session_id);
CREATE INDEX idx_session_song_position ON session_song(session_id, position);
CREATE INDEX idx_session_song_played ON session_song(session_id, played);

-- Constraint: Unique position per session
CREATE UNIQUE INDEX idx_session_song_unique_position 
    ON session_song(session_id, position);

-- ============================================================================
-- ROOM_MEMBER (Junction) TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS room_member (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    room_id UUID NOT NULL REFERENCES room(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    joined_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for membership lookups
CREATE INDEX idx_room_member_room_id ON room_member(room_id);
CREATE INDEX idx_room_member_user_id ON room_member(user_id);

-- Constraint: User can only join a room once
CREATE UNIQUE INDEX idx_room_member_unique 
    ON room_member(room_id, user_id);

-- ============================================================================
-- ADD FOREIGN KEY FOR current_song_id (after song table exists)
-- ============================================================================
ALTER TABLE session 
    ADD CONSTRAINT fk_session_current_song 
    FOREIGN KEY (current_song_id) 
    REFERENCES song(id) 
    ON DELETE SET NULL;

-- ============================================================================
-- UPDATED_AT TRIGGER FUNCTION
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers to relevant tables
CREATE TRIGGER update_user_updated_at BEFORE UPDATE ON "user"
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_room_updated_at BEFORE UPDATE ON room
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_session_updated_at BEFORE UPDATE ON session
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) SETUP
-- ============================================================================

-- Example: Enable RLS on tables (customize policies as needed)
ALTER TABLE "user" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "room" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "session" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "song" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "session_song" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "room_member" ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- HELPER FUNCTIONS (Optional utility functions)
-- ============================================================================

-- Function to get active session for a room
CREATE OR REPLACE FUNCTION get_active_session(p_room_id UUID)
RETURNS TABLE (
    session_id UUID,
    current_song_id UUID,
    current_song_start TIMESTAMPTZ,
    paused_position_ms INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT id, current_song_id, current_song_start, paused_position_ms
    FROM session
    WHERE room_id = p_room_id AND is_active = TRUE
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- Function to get queue for a session
CREATE OR REPLACE FUNCTION get_session_queue(p_session_id UUID)
RETURNS TABLE (
    song_id UUID,
    spotify_id VARCHAR,
    title VARCHAR,
    artist VARCHAR,
    album VARCHAR,
    duration_ms INTEGER,
    album_art_url TEXT,
    "position" INTEGER,
    played BOOLEAN,
    added_by_user_id UUID
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        s.id,
        s.spotify_id,
        s.title,
        s.artist,
        s.album,
        s.duration_ms,
        s.album_art_url,
        ss."position",
        ss.played,
        ss.added_by_user_id
    FROM session_song ss
    JOIN song s ON ss.song_id = s.id
    WHERE ss.session_id = p_session_id
    ORDER BY ss."position";
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- NOTES
-- ============================================================================
-- 1. Run this script in Supabase SQL Editor
-- 2. Configure RLS policies based on your auth strategy
-- 3. Set up Supabase API keys and configure PostgREST
-- 4. Update your backend .env with:
--    - SUPABASE_URL
--    - SUPABASE_KEY (service_role key for backend)
-- 5. For production, review indexes and add any needed for performance
