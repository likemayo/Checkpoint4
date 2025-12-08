-- Session storage table for server-side session management
-- Allows multiple independent sessions (multiple browser tabs with different logins)
CREATE TABLE IF NOT EXISTS flask_sessions (
    id TEXT PRIMARY KEY,
    data BLOB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

-- Index for cleanup queries
CREATE INDEX IF NOT EXISTS idx_flask_sessions_expires_at ON flask_sessions(expires_at);
