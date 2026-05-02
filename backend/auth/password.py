# backend/auth/password.py
"""
Password hashing utilities — bcrypt.
"""

import bcrypt

def hash_password(plain: str) -> str:
    """Return bcrypt hash of *plain*."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(plain.encode('utf-8'), salt).decode('utf-8')

def verify_password(plain: str, hashed: str) -> bool:
    """Return True if *plain* matches *hashed*."""
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False
