from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
from typing import List
import json

from app.core.database import get_db
from app.core.redis import publish_event, CHANNEL_CAMERA_CONTROL
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
    
    # Update camera status based on action
    if action == "start_recording":
        camera.recording_enabled = True
        camera.status = CameraStatus.RECORDING
    elif action == "stop_recording":
        camera.recording_enabled = False
        if camera.status == CameraStatus.RECORDING:
            camera.status = CameraStatus.ONLINE
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
    """Get current snapshot from camera"""
    result = await db.execute(select(Camera).where(Camera.id == camera_id))
    camera = result.scalar_one_or_none()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # This will be handled by the recorder service
    # For now, return the camera URL for direct streaming
    return {"camera_id": camera_id, "stream_url": f"/api/stream/{camera_id}"}
