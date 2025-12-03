from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List
import json
import os
import subprocess
import tempfile
from pathlib import Path

from app.core.database import get_db
from app.core.redis import publish_event, CHANNEL_CAMERA_CONTROL, get_redis
from app.models.models import Camera, CameraStatus
from app.schemas.schemas import (
    CameraCreate, CameraUpdate, CameraResponse, CameraControlRequest
)

router = APIRouter(prefix="/cameras", tags=["cameras"])


@router.get("/", response_model=List[CameraResponse])
async def get_cameras(db: AsyncSession = Depends(get_db)):
    """Get all cameras"""
    result = await db.execute(select(Camera).order_by(Camera.created_at.desc()))
    cameras = result.scalars().all()
    return cameras


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Get camera by ID"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    return camera


@router.post("/", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(camera_data: CameraCreate, db: AsyncSession = Depends(get_db)):
    """Create a new camera"""
    camera = Camera(**camera_data.model_dump())
    db.add(camera)
    await db.flush()
    await db.refresh(camera)
    
    # Notify other services about new camera
    await publish_event(CHANNEL_CAMERA_CONTROL, {
        "action": "camera_added",
        "camera_id": camera.id,
        "url": camera.url
    })
    
    return camera


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(
    camera_id: int, 
    camera_data: CameraUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """Update camera settings"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    update_data = camera_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(camera, field, value)
    
    await db.flush()
    await db.refresh(camera)
    
    # Notify other services about camera update
    await publish_event(CHANNEL_CAMERA_CONTROL, {
        "action": "camera_updated",
        "camera_id": camera.id,
        "changes": update_data
    })
    
    return camera


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a camera"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Notify other services to stop recording/detection
    await publish_event(CHANNEL_CAMERA_CONTROL, {
        "action": "camera_deleted",
        "camera_id": camera.id
    })
    
    await db.delete(camera)


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Get camera snapshot from Redis cache"""
    from app.core.redis import get_frame
    
    # Get cached frame from Redis
    frame_data = await get_frame(camera_id)
    
    if not frame_data:
        from fastapi.responses import Response
        # Return 1x1 transparent PNG if no frame available
        return Response(
            content=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82',
            media_type="image/png"
        )
    
    from fastapi.responses import Response
    return Response(content=frame_data, media_type="image/jpeg")


@router.post("/{camera_id}/control")
async def control_camera(
    camera_id: int, 
    request: CameraControlRequest,
    db: AsyncSession = Depends(get_db)
):
    """Control camera (start/stop recording/detection)"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    action = request.action
    
    # Update camera settings based on action
    if action == "start_recording":
        # Recording is handled by recorder service, just send command
        pass
    elif action == "stop_recording":
        # Recording is handled by recorder service, just send command
        pass
    elif action == "start_detection":
        camera.motion_detection_enabled = True
    elif action == "stop_detection":
        camera.motion_detection_enabled = False
    elif action == "restart":
        pass  # Just send the restart command
    
    await db.flush()
    
    # Publish control command to workers
    await publish_event(CHANNEL_CAMERA_CONTROL, {
        "action": action,
        "camera_id": camera.id,
        "url": camera.url
    })
    
    return {"status": "ok", "action": action, "camera_id": camera_id}


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(camera_id: int, db: AsyncSession = Depends(get_db)):
    """Get current snapshot from camera - returns JPEG image"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # Try to get cached snapshot from Redis first
    redis = await get_redis()
    cached_snapshot = await redis.get(f"snapshot:{camera_id}")
    
    if cached_snapshot:
        return StreamingResponse(
            iter([cached_snapshot]),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
    
    # Otherwise capture a snapshot using FFmpeg
    try:
        # Create temp file for snapshot
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
            tmp_path = tmp.name
        
        # Build FFmpeg command based on camera URL
        url = camera.url
        if url.startswith('/dev/'):
            # Local video device
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-f', 'v4l2',
                '-i', url,
                '-frames:v', '1',
                '-q:v', '2',
                tmp_path
            ]
        else:
            # RTSP or HTTP stream
            ffmpeg_cmd = [
                'ffmpeg', '-y',
                '-rtsp_transport', 'tcp',
                '-i', url,
                '-frames:v', '1',
                '-q:v', '2',
                tmp_path
            ]
        
        # Run FFmpeg
        process = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            timeout=5
        )
        
        if process.returncode != 0 or not os.path.exists(tmp_path):
            raise HTTPException(status_code=500, detail="Failed to capture snapshot")
        
        # Read and return the image
        with open(tmp_path, 'rb') as f:
            image_data = f.read()
        
        # Cache in Redis for 1 second
        await redis.setex(f"snapshot:{camera_id}", 1, image_data)
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        return StreamingResponse(
            iter([image_data]),
            media_type="image/jpeg",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"}
        )
        
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Snapshot capture timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Snapshot capture failed: {str(e)}")
