from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List, Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.models.models import MotionEvent, Camera
from app.schemas.schemas import MotionEventResponse, MotionEventCreate

router = APIRouter(prefix="/events", tags=["events"])


@router.post("/", response_model=MotionEventResponse)
async def create_event(
    event: MotionEventCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new motion event"""
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == event.camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    db_event = MotionEvent(
        camera_id=event.camera_id,
        timestamp=datetime.utcnow(),
        confidence=event.confidence,
        snapshot_path=event.snapshot_path,
        notification_sent=False
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event


@router.get("/", response_model=List[MotionEventResponse])
async def get_events(
    camera_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get motion events with optional filters"""
    query = select(MotionEvent).order_by(MotionEvent.timestamp.desc())
    
    if camera_id:
        query = query.where(MotionEvent.camera_id == camera_id)
    if start_date:
        query = query.where(MotionEvent.timestamp >= start_date)
    if end_date:
        query = query.where(MotionEvent.timestamp <= end_date)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    events = result.scalars().all()
    return events


@router.get("/recent", response_model=List[MotionEventResponse])
async def get_recent_events(
    hours: int = Query(default=24, le=168),  # Max 7 days
    db: AsyncSession = Depends(get_db)
):
    """Get recent motion events"""
    since = datetime.utcnow() - timedelta(hours=hours)
    query = select(MotionEvent).where(
        MotionEvent.timestamp >= since
    ).order_by(MotionEvent.timestamp.desc()).limit(100)
    
    result = await db.execute(query)
    events = result.scalars().all()
    return events


@router.get("/stats")
async def get_event_stats(
    camera_id: Optional[int] = None,
    days: int = Query(default=7, le=30),
    db: AsyncSession = Depends(get_db)
):
    """Get motion event statistics"""
    since = datetime.utcnow() - timedelta(days=days)
    
    query = select(
        func.date(MotionEvent.timestamp).label('date'),
        func.count(MotionEvent.id).label('count')
    ).where(MotionEvent.timestamp >= since)
    
    if camera_id:
        query = query.where(MotionEvent.camera_id == camera_id)
    
    query = query.group_by(func.date(MotionEvent.timestamp)).order_by(func.date(MotionEvent.timestamp))
    
    result = await db.execute(query)
    stats = [{"date": str(row.date), "count": row.count} for row in result]
    
    return {"stats": stats, "period_days": days}


@router.delete("/{event_id}")
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a motion event"""
    result = await db.execute(select(MotionEvent).where(MotionEvent.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    await db.delete(event)
    return {"status": "deleted", "event_id": event_id}
