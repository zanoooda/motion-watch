from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.models import CameraStatus


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=1024)
    is_enabled: bool = True
    recording_enabled: bool = True
    audio_enabled: bool = True
    motion_detection_enabled: bool = True
    motion_sensitivity: float = Field(default=25.0, ge=0, le=100)
    motion_min_area: int = Field(default=500, ge=0)
    motion_cooldown: int = Field(default=30, ge=0)
    detection_zones: Optional[str] = None


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=1024)
    is_enabled: Optional[bool] = None
    recording_enabled: Optional[bool] = None
    audio_enabled: Optional[bool] = None
    motion_detection_enabled: Optional[bool] = None
    motion_sensitivity: Optional[float] = Field(None, ge=0, le=100)
    motion_min_area: Optional[int] = Field(None, ge=0)
    motion_cooldown: Optional[int] = Field(None, ge=0)
    detection_zones: Optional[str] = None


class CameraResponse(CameraBase):
    id: int
    status: CameraStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class MotionEventCreate(BaseModel):
    camera_id: int
    event_type: str = "motion"
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None


class MotionEventResponse(BaseModel):
    id: int
    camera_id: int
    timestamp: datetime
    confidence: Optional[float] = None
    snapshot_path: Optional[str] = None
    video_clip_path: Optional[str] = None
    notification_sent: bool
    
    class Config:
        from_attributes = True


class RecordingResponse(BaseModel):
    id: int
    camera_id: int
    file_path: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    file_size: Optional[int] = None
    is_segment: bool
    
    class Config:
        from_attributes = True


class SystemSettingsUpdate(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    storage_retention_days: Optional[int] = Field(None, ge=1)


class SystemSettingsResponse(BaseModel):
    telegram_configured: bool
    storage_retention_days: int = 30
    total_cameras: int = 0
    active_cameras: int = 0
    storage_used_gb: float = 0.0


class CameraControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start_recording|stop_recording|start_detection|stop_detection|restart)$")


class CreateClipRequest(BaseModel):
    camera_id: int
    start_time: datetime
    end_time: datetime
    output_filename: Optional[str] = None
