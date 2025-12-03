from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import os
import shutil

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import Camera, CameraStatus, SystemSettings
from app.schemas.schemas import SystemSettingsUpdate, SystemSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])
settings = get_settings()


@router.get("/", response_model=SystemSettingsResponse)
async def get_system_settings(db: AsyncSession = Depends(get_db)):
    """Get system settings and statistics"""
    # Check if Telegram is configured
    telegram_configured = bool(settings.telegram_bot_token and settings.telegram_chat_id)
    
    # Get camera stats
    total_result = await db.execute(select(func.count(Camera.id)))
    total_cameras = total_result.scalar() or 0
    
    active_result = await db.execute(
        select(func.count(Camera.id)).where(Camera.status.in_([CameraStatus.ONLINE, CameraStatus.RECORDING]))
    )
    active_cameras = active_result.scalar() or 0
    
    # Get storage retention setting
    retention_result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == "storage_retention_days")
    )
    retention_setting = retention_result.scalar_one_or_none()
    storage_retention_days = int(retention_setting.value) if retention_setting else 30
    
    # Calculate storage used
    storage_used_gb = 0.0
    if os.path.exists(settings.storage_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(settings.storage_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                total_size += os.path.getsize(filepath)
        storage_used_gb = round(total_size / (1024 ** 3), 2)
    
    return SystemSettingsResponse(
        telegram_configured=telegram_configured,
        storage_retention_days=storage_retention_days,
        total_cameras=total_cameras,
        active_cameras=active_cameras,
        storage_used_gb=storage_used_gb
    )


@router.put("/")
async def update_system_settings(
    settings_data: SystemSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update system settings"""
    updates = settings_data.model_dump(exclude_unset=True)
    
    for key, value in updates.items():
        # Check if setting exists
        result = await db.execute(
            select(SystemSettings).where(SystemSettings.key == key)
        )
        setting = result.scalar_one_or_none()
        
        if setting:
            setting.value = str(value) if value is not None else None
        else:
            new_setting = SystemSettings(key=key, value=str(value) if value is not None else None)
            db.add(new_setting)
    
    await db.flush()
    
    return {"status": "updated", "settings": updates}


@router.get("/storage")
async def get_storage_info():
    """Get detailed storage information"""
    storage_path = settings.storage_path
    
    if not os.path.exists(storage_path):
        return {
            "path": storage_path,
            "total_gb": 0,
            "used_gb": 0,
            "free_gb": 0,
            "cameras": []
        }
    
    # Get disk usage
    total, used, free = shutil.disk_usage(storage_path)
    
    # Get per-camera storage
    cameras_storage = []
    for item in os.listdir(storage_path):
        item_path = os.path.join(storage_path, item)
        if os.path.isdir(item_path) and item.startswith("camera_"):
            camera_size = 0
            for dirpath, dirnames, filenames in os.walk(item_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    camera_size += os.path.getsize(filepath)
            
            cameras_storage.append({
                "camera_dir": item,
                "size_gb": round(camera_size / (1024 ** 3), 2)
            })
    
    return {
        "path": storage_path,
        "total_gb": round(total / (1024 ** 3), 2),
        "used_gb": round(used / (1024 ** 3), 2),
        "free_gb": round(free / (1024 ** 3), 2),
        "recordings_used_gb": sum(c["size_gb"] for c in cameras_storage),
        "cameras": cameras_storage
    }


@router.post("/cleanup")
async def cleanup_old_recordings(
    days: int = 30,
    db: AsyncSession = Depends(get_db)
):
    """Clean up recordings older than specified days"""
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0
    freed_space = 0
    
    storage_path = settings.storage_path
    if not os.path.exists(storage_path):
        return {"status": "no_storage", "deleted": 0, "freed_gb": 0}
    
    for camera_dir in os.listdir(storage_path):
        camera_path = os.path.join(storage_path, camera_dir)
        if not os.path.isdir(camera_path):
            continue
        
        for date_dir in os.listdir(camera_path):
            date_path = os.path.join(camera_path, date_dir)
            if not os.path.isdir(date_path):
                continue
            
            try:
                dir_date = datetime.strptime(date_dir, "%Y-%m-%d")
                if dir_date < cutoff_date:
                    # Calculate size before deletion
                    for dirpath, dirnames, filenames in os.walk(date_path):
                        for filename in filenames:
                            filepath = os.path.join(dirpath, filename)
                            freed_space += os.path.getsize(filepath)
                            deleted_count += 1
                    
                    # Delete directory
                    shutil.rmtree(date_path)
            except ValueError:
                continue
    
    return {
        "status": "completed",
        "deleted_files": deleted_count,
        "freed_gb": round(freed_space / (1024 ** 3), 2)
    }
