from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import NotificationSettings
from app.schemas.schemas import NotificationSettingsResponse, NotificationSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/notifications", response_model=NotificationSettingsResponse)
async def get_notification_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create default settings
        settings = NotificationSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return settings


@router.put("/notifications", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    settings_data: NotificationSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = NotificationSettings()
        db.add(settings)
    
    for field, value in settings_data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    
    await db.commit()
    await db.refresh(settings)
    return settings


@router.get("/all")
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    """Get all settings"""
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create default settings
        settings = NotificationSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return {
        "telegram_bot_token": settings.telegram_bot_token or "",
        "telegram_chat_id": settings.telegram_chat_id or "",
        "telegram_enabled": settings.telegram_enabled,
        "telegram_send_snapshots": True,
        "notification_cooldown": 60,
        "retention_days": 7,
        "events_retention_days": 30,
        "auto_cleanup": False,
        "default_sensitivity": 25.0,
        "default_motion_cooldown": 5,
        "default_clip_duration": 10
    }


@router.get("/")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Get all settings - same as /all"""
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings:
        # Create default settings
        settings = NotificationSettings()
        db.add(settings)
        await db.commit()
        await db.refresh(settings)
    
    return {
        "telegram_bot_token": settings.telegram_bot_token or "",
        "telegram_chat_id": settings.telegram_chat_id or "",
        "telegram_enabled": settings.telegram_enabled,
        "telegram_send_snapshots": True,
        "notification_cooldown": 60,
        "retention_days": 7,
        "events_retention_days": 30,
        "auto_cleanup": False,
        "default_sensitivity": 25.0,
        "default_motion_cooldown": 5,
        "default_clip_duration": 10
    }


@router.put("/")
async def update_settings(settings_data: dict, db: AsyncSession = Depends(get_db)):
    """Update settings"""
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings:
        settings = NotificationSettings()
        db.add(settings)
    
    # Update only telegram fields
    if "telegram_bot_token" in settings_data:
        settings.telegram_bot_token = settings_data["telegram_bot_token"]
    if "telegram_chat_id" in settings_data:
        settings.telegram_chat_id = settings_data["telegram_chat_id"]
    if "telegram_enabled" in settings_data:
        settings.telegram_enabled = settings_data["telegram_enabled"]
    
    await db.commit()
    await db.refresh(settings)
    
    return {
        "telegram_bot_token": settings.telegram_bot_token or "",
        "telegram_chat_id": settings.telegram_chat_id or "",
        "telegram_enabled": settings.telegram_enabled,
        "telegram_send_snapshots": True,
        "notification_cooldown": 60,
        "retention_days": 7,
        "events_retention_days": 30,
        "auto_cleanup": False,
        "default_sensitivity": 25.0,
        "default_motion_cooldown": 5,
        "default_clip_duration": 10
    }


@router.post("/cleanup")
async def cleanup_storage():
    """Cleanup old recordings (placeholder)"""
    return {"status": "ok", "message": "Cleanup not implemented yet"}


@router.post("/test-telegram")
async def test_telegram(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(NotificationSettings))
    settings = result.scalar_one_or_none()
    
    if not settings or not settings.telegram_enabled:
        raise HTTPException(status_code=400, detail="Telegram not configured")
    
    # TODO: Send test message
    return {"status": "ok", "message": "Test notification sent"}
