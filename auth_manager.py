"""
Authentication Manager for Metagros

Handles user authentication using a local SQLite database.
Securely stores credentials with SHA-256 hashing + salt.
"""

import sqlite3
import hashlib
import os
from typing import Optional, Tuple

DB_PATH = "users.db"


class AuthManager:
    """Manages user authentication and session state."""
    
    def __init__(self):
        self.init_db()
        # Seed default admin if empty
        self.create_user("admin", "metagros")

    def init_db(self):
        """Initialize SQLite database for users."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        username TEXT PRIMARY KEY,
                        password_hash TEXT NOT NULL,
                        salt TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
        except Exception as e:
            print(f"[Auth] DB Init Error: {e}")

    def _hash_password(self, password: str, salt: bytes = None) -> Tuple[str, str]:
        """Hash password with salt using SHA-256."""
        if salt is None:
            salt = os.urandom(32)
        else:
            salt = bytes.fromhex(salt) if isinstance(salt, str) else salt
            
        pwd_hash = hashlib.pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt, 
            100000
        )
        return pwd_hash.hex(), salt.hex()

    def create_user(self, username: str, password: str) -> bool:
        """Create a new user. Returns True if successful."""
        try:
            pwd_hash, salt = self._hash_password(password)
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                # Check if exists
                cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
                if cursor.fetchone():
                    return False  # Already exists
                
                cursor.execute(
                    "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
                    (username, pwd_hash, salt)
                )
                conn.commit()
                print(f"[Auth] Created user: {username}")
                return True
        except Exception as e:
            print(f"[Auth] Create User Error: {e}")
            return False

    def authenticate(self, username: str, password: str) -> bool:
        """Verify username and password."""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username,))
                row = cursor.fetchone()
                
                if not row:
                    return False
                
                stored_hash, stored_salt = row
                # Verify hash
                pwd_hash, _ = self._hash_password(password, stored_salt)
                
                if pwd_hash == stored_hash:
                    return True
                return False
        except Exception as e:
            print(f"[Auth] Auth Error: {e}")
            return False

    def update_password(self, username: str, new_password: str) -> bool:
        """Update password for existing user."""
        try:
            pwd_hash, salt = self._hash_password(new_password)
            
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
                    (pwd_hash, salt, username)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"[Auth] Update Password Error: {e}")
            return False


# Global instance
_auth_manager = None

def get_auth_manager() -> AuthManager:
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
