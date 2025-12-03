from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CameraBase(BaseModel):
    name: str
    url: str
    is_enabled: bool = True
    motion_detection_enabled: bool = True
    motion_sensitivity: float = 25.0


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    is_enabled: Optional[bool] = None
    motion_detection_enabled: Optional[bool] = None
    motion_sensitivity: Optional[float] = None


class CameraResponse(CameraBase):
    id: int
    status: str
    created_at: datetime
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True


class MotionEventResponse(BaseModel):
    id: int
    camera_id: int
    timestamp: datetime
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None

    class Config:
        from_attributes = True


class NotificationSettingsBase(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool = False
    send_photo: bool = True
    send_video: bool = False
    send_text_only: bool = False
    custom_message: Optional[str] = None
    cooldown_seconds: int = 60


class NotificationSettingsUpdate(NotificationSettingsBase):
    pass


class NotificationSettingsResponse(NotificationSettingsBase):
    id: int
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CameraControlRequest(BaseModel):
    action: str  # start_detection, stop_detection
