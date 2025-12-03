from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timedelta
import os
import subprocess
import asyncio

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import Recording, Camera
from app.schemas.schemas import RecordingResponse, CreateClipRequest

router = APIRouter(prefix="/recordings", tags=["recordings"])
settings = get_settings()


@router.get("/", response_model=List[RecordingResponse])
async def get_recordings(
    camera_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get recordings with optional filters"""
    query = select(Recording).order_by(Recording.start_time.desc())
    
    if camera_id:
        query = query.where(Recording.camera_id == camera_id)
    if start_date:
        query = query.where(Recording.start_time >= start_date)
    if end_date:
        query = query.where(Recording.start_time <= end_date)
    
    query = query.limit(limit).offset(offset)
    
    result = await db.execute(query)
    recordings = result.scalars().all()
    return recordings


@router.get("/{camera_id}/segments")
async def get_camera_segments(
    camera_id: int,
    date: Optional[str] = None,  # Format: YYYY-MM-DD
    db: AsyncSession = Depends(get_db)
):
    """Get available recording segments for a camera"""
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Build path
    camera_dir = os.path.join(settings.storage_path, f"camera_{camera_id}")
    
    if date:
        date_dir = os.path.join(camera_dir, date, "segments")
    else:
        # Get today's segments
        date_dir = os.path.join(camera_dir, datetime.now().strftime("%Y-%m-%d"), "segments")
    
    segments = []
    if os.path.exists(date_dir):
        for filename in sorted(os.listdir(date_dir)):
            if filename.endswith(('.ts', '.mp4')):
                filepath = os.path.join(date_dir, filename)
                segments.append({
                    "filename": filename,
                    "path": filepath,
                    "size": os.path.getsize(filepath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                })
    
    return {"camera_id": camera_id, "date": date, "segments": segments}


@router.get("/{camera_id}/dates")
async def get_available_dates(
    camera_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get list of dates with available recordings for a camera"""
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera_dir = os.path.join(settings.storage_path, f"camera_{camera_id}")
    
    dates = []
    if os.path.exists(camera_dir):
        for dirname in sorted(os.listdir(camera_dir), reverse=True):
            date_path = os.path.join(camera_dir, dirname)
            if os.path.isdir(date_path):
                # Check if there are segments
                segments_dir = os.path.join(date_path, "segments")
                segment_count = 0
                if os.path.exists(segments_dir):
                    segment_count = len([f for f in os.listdir(segments_dir) if f.endswith(('.ts', '.mp4'))])
                
                if segment_count > 0:
                    dates.append({
                        "date": dirname,
                        "segment_count": segment_count
                    })
    
    return {"camera_id": camera_id, "dates": dates}


async def create_clip_task(
    camera_id: int,
    start_time: datetime,
    end_time: datetime,
    output_path: str
):
    """Background task to create video clip from segments"""
    camera_dir = os.path.join(settings.storage_path, f"camera_{camera_id}")
    
    # Find segments that cover the time range
    segments_to_concat = []
    
    current_date = start_time.date()
    while current_date <= end_time.date():
        date_str = current_date.strftime("%Y-%m-%d")
        segments_dir = os.path.join(camera_dir, date_str, "segments")
        
        if os.path.exists(segments_dir):
            for filename in sorted(os.listdir(segments_dir)):
                if filename.endswith(('.ts', '.mp4')):
                    # Parse time from filename (format: HH-MM-SS.ts)
                    try:
                        time_parts = filename.replace('.ts', '').replace('.mp4', '').split('-')
                        segment_time = datetime.combine(
                            current_date,
                            datetime.strptime(f"{time_parts[0]}:{time_parts[1]}:{time_parts[2]}", "%H:%M:%S").time()
                        )
                        
                        # Check if segment is within range
                        if start_time <= segment_time <= end_time:
                            segments_to_concat.append(os.path.join(segments_dir, filename))
                    except (ValueError, IndexError):
                        continue
        
        current_date += timedelta(days=1)
    
    if not segments_to_concat:
        return
    
    # Create concat file for FFmpeg
    concat_file = os.path.join(settings.storage_path, "temp_concat.txt")
    with open(concat_file, 'w') as f:
        for segment in segments_to_concat:
            f.write(f"file '{segment}'\n")
    
    # Run FFmpeg to concatenate segments
    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', concat_file,
        '-c', 'copy',
        output_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.communicate()
    
    # Clean up
    os.remove(concat_file)


@router.post("/create-clip")
async def create_clip(
    request: CreateClipRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Create a video clip from recording segments"""
    # Verify camera exists
    result = await db.execute(select(Camera).where(Camera.id == request.camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Generate output path
    if request.output_filename:
        output_filename = request.output_filename
    else:
        output_filename = f"clip_{request.camera_id}_{request.start_time.strftime('%Y%m%d_%H%M%S')}.mp4"
    
    output_path = os.path.join(
        settings.storage_path, 
        f"camera_{request.camera_id}", 
        "clips",
        output_filename
    )
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Schedule background task
    background_tasks.add_task(
        create_clip_task,
        request.camera_id,
        request.start_time,
        request.end_time,
        output_path
    )
    
    return {
        "status": "processing",
        "output_path": output_path,
        "message": "Clip creation started in background"
    }


@router.delete("/{recording_id}")
async def delete_recording(recording_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a recording"""
    result = await db.execute(select(Recording).where(Recording.id == recording_id))
    recording = result.scalar_one_or_none()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    
    # Delete file if exists
    if os.path.exists(recording.file_path):
        os.remove(recording.file_path)
    
    await db.delete(recording)
    return {"status": "deleted", "recording_id": recording_id}
