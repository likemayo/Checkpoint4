"""
Database-backed Flask session interface for independent multi-tab sessions.

This allows users to have separate sessions in different browser tabs,
enabling simultaneous customer and admin logins.
"""

import json
import os
import pickle
import sqlite3
from datetime import datetime, timedelta
from flask.sessions import SessionInterface, SessionMixin
from werkzeug.datastructures import CallbackDict


class DatabaseSession(CallbackDict, SessionMixin):
    """A session object backed by the database."""

    def __init__(self, initial=None, sid=None, permanent=False):
        def on_update(self):
            self.modified = True

        CallbackDict.__init__(self, initial, on_update)
        self.sid = sid
        self.permanent = permanent
        self.modified = False


class DatabaseSessionInterface(SessionInterface):
    """Flask session interface that stores sessions in SQLite database."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def open_session(self, app, request):
        """Load session from database."""
        sid = request.cookies.get(app.config['SESSION_COOKIE_NAME'])
        
        if not sid:
            return DatabaseSession(sid=None, permanent=False)

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # Get session data from database
            cur.execute(
                "SELECT data, expires_at FROM flask_sessions WHERE id = ? AND expires_at > datetime('now')",
                (sid,)
            )
            row = cur.fetchone()
            conn.close()
            
            if row:
                try:
                    data = pickle.loads(row['data'])
                    return DatabaseSession(initial=data, sid=sid, permanent=True)
                except Exception as e:
                    # Corrupted session data
                    app.logger.error(f"Failed to deserialize session data: {e}")
                    return DatabaseSession(sid=None, permanent=False)
            else:
                # Session expired or not found
                return DatabaseSession(sid=None, permanent=False)
        except Exception as e:
            app.logger.error(f"Failed to load session: {e}")
            return DatabaseSession(sid=None, permanent=False)

    def save_session(self, app, session, response):
        """Save session to database."""
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)
        
        # Delete if empty
        if not session:
            if session.sid:
                try:
                    conn = sqlite3.connect(self.db_path)
                    conn.execute("DELETE FROM flask_sessions WHERE id = ?", (session.sid,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    app.logger.error(f"Failed to delete session: {e}")
            
            if session.sid:
                response.delete_cookie(
                    app.config['SESSION_COOKIE_NAME'],
                    domain=domain,
                    path=path
                )
            return

        # Only save if session has been modified or if there's no SID yet
        if not session.modified and session.sid:
            return

        # Generate session ID if needed
        if not session.sid:
            import secrets
            session.sid = secrets.token_urlsafe(32)

        # Calculate expiration
        if session.permanent:
            expires = datetime.utcnow() + timedelta(days=7)
        else:
            expires = datetime.utcnow() + timedelta(hours=24)

        # Save to database
        try:
            conn = sqlite3.connect(self.db_path)
            data = pickle.dumps(dict(session))
            
            conn.execute(
                """
                INSERT OR REPLACE INTO flask_sessions (id, data, updated_at, expires_at)
                VALUES (?, ?, datetime('now'), ?)
                """,
                (session.sid, data, expires.isoformat())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            app.logger.error(f"Failed to save session: {e}")
            return

        # Set cookie
        response.set_cookie(
            app.config['SESSION_COOKIE_NAME'],
            session.sid,
            expires=expires,
            httponly=self.get_cookie_httponly(app),
            domain=domain,
            path=path,
            secure=self.get_cookie_secure(app),
            samesite=self.get_cookie_samesite(app)
        )
