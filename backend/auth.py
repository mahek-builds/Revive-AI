"""
auth.py — FastAPI API-key authentication dependency.
If API_KEY env var is empty, auth is disabled (development mode).
"""
from fastapi import Header, HTTPException, status
from backend.config import API_KEY


async def require_api_key(x_api_key: str = Header(default="")):
    """FastAPI dependency: validates X-API-KEY header.
    Disabled when API_KEY env var is not configured (dev mode).
    """
    if not API_KEY:
        return   # auth disabled in dev mode
    if x_api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": {"code": "INVALID_API_KEY", "message": "Invalid or missing X-API-KEY header."}},
        )
