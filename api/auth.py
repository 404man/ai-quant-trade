# api/auth.py
import os
from fastapi import HTTPException, Request


def verify_api_key(request: Request):
    """FastAPI dependency: validate Bearer token against LOCAL_API_KEY env var.

    Skips auth when LOCAL_API_KEY is not set (dev mode).
    """
    api_key = os.environ.get("LOCAL_API_KEY")
    if not api_key:
        return  # dev mode: no auth
    auth = request.headers.get("Authorization", "")
    if auth != f"Bearer {api_key}":
        raise HTTPException(status_code=401, detail="Invalid API key")
