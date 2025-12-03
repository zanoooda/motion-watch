from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import os
import shutil
import httpx

from app.core.database import get_db
from app.core.config import get_settings
from app.models.models import Camera, CameraStatus, SystemSettings
from app.schemas.schemas import SystemSettingsUpdate, SystemSettingsResponse, AllSettingsResponse

router = APIRouter(prefix="/settings", tags=["settings"])
settings = get_settings()


# Default settings values
DEFAULT_SETTINGS = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_enabled": False,
    "telegram_send_snapshots": True,
    "notification_cooldown": 60,
    "retention_days": 7,
    "events_retention_days": 30,
    "auto_cleanup": True,
    "default_sensitivity": 25.0,
    "default_motion_cooldown": 30,
    "default_clip_duration": 10,
}


async def get_setting_value(db: AsyncSession, key: str, default=None):
    """Get a setting value from the database"""
    result = await db.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()
    if setting and setting.value:
        # Try to convert to appropriate type
        value = setting.value
        if default is not None:
            if isinstance(default, bool):
                return value.lower() in ('true', '1', 'yes')
            if isinstance(default, int):
                try:
                    return int(value)
                except ValueError:
                    return default
            if isinstance(default, float):
                try:
                    return float(value)
                except ValueError:
                    return default
        return value
    return default


@router.get("/", response_model=SystemSettingsResponse)
async def get_system_settings(db: AsyncSession = Depends(get_db)):
    """Get system settings and statistics"""
    # Check if Telegram is configured
    telegram_token = await get_setting_value(db, "telegram_bot_token", "")
    telegram_chat = await get_setting_value(db, "telegram_chat_id", "")
    telegram_configured = bool(telegram_token and telegram_chat)
    
    # Get camera stats
    total_result = await db.execute(select(func.count(Camera.id)))
    total_cameras = total_result.scalar() or 0
    
    active_result = await db.execute(
        select(func.count(Camera.id)).where(Camera.status.in_([CameraStatus.ONLINE, CameraStatus.RECORDING]))
    )
    active_cameras = active_result.scalar() or 0
    
    # Get storage retention setting
    storage_retention_days = await get_setting_value(db, "retention_days", 7)
    
    # Calculate storage used
    storage_used_gb = 0.0
    if os.path.exists(settings.storage_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(settings.storage_path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    pass
        storage_used_gb = round(total_size / (1024 ** 3), 2)
    
    return SystemSettingsResponse(
        telegram_configured=telegram_configured,
        storage_retention_days=storage_retention_days,
        total_cameras=total_cameras,
        active_cameras=active_cameras,
        storage_used_gb=storage_used_gb
    )


@router.get("/all", response_model=AllSettingsResponse)
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Get all system settings including Telegram configuration"""
    result = {}
    for key, default in DEFAULT_SETTINGS.items():
        result[key] = await get_setting_value(db, key, default)
    
    # Mask the bot token for security
    if result.get("telegram_bot_token"):
        token = result["telegram_bot_token"]
        if len(token) > 10:
            result["telegram_bot_token"] = token[:5] + "..." + token[-5:]
    
    return AllSettingsResponse(**result)


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


@router.post("/test-telegram")
async def test_telegram_notification(db: AsyncSession = Depends(get_db)):
    """Send a test notification to Telegram"""
    bot_token = await get_setting_value(db, "telegram_bot_token", "")
    chat_id = await get_setting_value(db, "telegram_chat_id", "")
    
    if not bot_token or not chat_id:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": "🎥 Motion Watch - Test notification\n\nYour Telegram integration is working correctly!",
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=500, detail=f"Telegram API error: {response.text}")
            
            return {"status": "success", "message": "Test notification sent"}
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Telegram API timeout")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send notification: {str(e)}")


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


@router.post("/cleanup-storage")
async def cleanup_storage(db: AsyncSession = Depends(get_db)):
    """Clean up old recordings based on retention settings"""
    retention_days = await get_setting_value(db, "retention_days", 7)
    events_retention_days = await get_setting_value(db, "events_retention_days", 30)
    
    from datetime import datetime, timedelta
    from app.models.models import MotionEvent
    
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    events_cutoff = datetime.now() - timedelta(days=events_retention_days)
    
    deleted_count = 0
    freed_space = 0
    
    storage_path = settings.storage_path
    if os.path.exists(storage_path):
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
                        for dirpath, dirnames, filenames in os.walk(date_path):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                try:
                                    freed_space += os.path.getsize(filepath)
                                    deleted_count += 1
                                except OSError:
                                    pass
                        shutil.rmtree(date_path)
                except ValueError:
                    continue
    
    # Also clean up old events from database
    deleted_events = await db.execute(
        select(MotionEvent).where(MotionEvent.timestamp < events_cutoff)
    )
    old_events = deleted_events.scalars().all()
    for event in old_events:
        # Delete associated files
        if event.snapshot_path and os.path.exists(event.snapshot_path):
            try:
                freed_space += os.path.getsize(event.snapshot_path)
                os.remove(event.snapshot_path)
            except OSError:
                pass
        if event.video_clip_path and os.path.exists(event.video_clip_path):
            try:
                freed_space += os.path.getsize(event.video_clip_path)
                os.remove(event.video_clip_path)
            except OSError:
                pass
        await db.delete(event)
    
    await db.flush()
    
    return {
        "status": "completed",
        "deleted_files": deleted_count,
        "deleted_events": len(old_events),
        "freed_gb": round(freed_space / (1024 ** 3), 2)
    }
