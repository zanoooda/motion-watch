from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from typing import List, Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.models import MotionEvent
from app.schemas.schemas import MotionEventResponse

router = APIRouter(prefix="/events", tags=["events"])


class MotionEventCreate(BaseModel):
    camera_id: int
    confidence: float
    snapshot_path: Optional[str] = None


@router.post("/", response_model=MotionEventResponse)
async def create_event(event: MotionEventCreate, db: AsyncSession = Depends(get_db)):
    """Create new motion event"""
    db_event = MotionEvent(**event.model_dump())
    db.add(db_event)
    await db.flush()
    await db.refresh(db_event)
    return db_event


@router.get("/", response_model=List[MotionEventResponse])
async def get_events(
    camera_id: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    query = select(MotionEvent).order_by(desc(MotionEvent.timestamp)).offset(offset).limit(limit)
    if camera_id:
        query = query.where(MotionEvent.camera_id == camera_id)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/recent", response_model=List[MotionEventResponse])
async def get_recent_events(
    hours: int = 24,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get recent events from the last N hours"""
    from datetime import datetime, timedelta
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = (
        select(MotionEvent)
        .where(MotionEvent.timestamp >= since)
        .order_by(desc(MotionEvent.timestamp))
        .limit(limit)
    )
    
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{event_id}/snapshot")
async def get_event_snapshot(event_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MotionEvent).where(MotionEvent.id == event_id))
    event = result.scalar_one_or_none()
    
    if not event or not event.snapshot_path:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    
    return FileResponse(event.snapshot_path, media_type="image/jpeg")
