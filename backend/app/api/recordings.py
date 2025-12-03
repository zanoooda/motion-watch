from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db

router = APIRouter(prefix="/recordings", tags=["recordings"])


@router.get("/")
async def get_recordings(
    camera_id: Optional[int] = None,
    limit: int = 24,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get recordings (placeholder - не implemented yet)"""
    return []
