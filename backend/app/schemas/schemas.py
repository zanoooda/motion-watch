from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from app.models.models import CameraStatus


class CameraBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=1024)
    is_enabled: bool = True
    recording_enabled: bool = False
    audio_enabled: bool = True
    motion_detection_enabled: bool = True
    motion_sensitivity: float = Field(default=25.0, ge=0, le=100)
    motion_min_area: int = Field(default=500, ge=0)
    motion_cooldown: int = Field(default=30, ge=0)
    detection_zones: Optional[str] = None
    # New fields for snapshot/clip settings
    save_snapshots: bool = True
    save_video_clips: bool = False
    video_clip_duration: int = Field(default=10, ge=5, le=120)
    notification_cooldown: int = Field(default=60, ge=0)


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
    # New fields
    save_snapshots: Optional[bool] = None
    save_video_clips: Optional[bool] = None
    video_clip_duration: Optional[int] = Field(None, ge=5, le=120)
    notification_cooldown: Optional[int] = Field(None, ge=0)


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
    telegram_enabled: Optional[bool] = None
    telegram_send_snapshots: Optional[bool] = None
    notification_cooldown: Optional[int] = Field(None, ge=0)
    retention_days: Optional[int] = Field(None, ge=1)
    events_retention_days: Optional[int] = Field(None, ge=1)
    auto_cleanup: Optional[bool] = None
    default_sensitivity: Optional[float] = Field(None, ge=0, le=100)
    default_motion_cooldown: Optional[int] = Field(None, ge=0)
    default_clip_duration: Optional[int] = Field(None, ge=5, le=120)


class SystemSettingsResponse(BaseModel):
    telegram_configured: bool
    storage_retention_days: int = 30
    total_cameras: int = 0
    active_cameras: int = 0
    storage_used_gb: float = 0.0


class AllSettingsResponse(BaseModel):
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_enabled: bool = False
    telegram_send_snapshots: bool = True
    notification_cooldown: int = 60
    retention_days: int = 7
    events_retention_days: int = 30
    auto_cleanup: bool = True
    default_sensitivity: float = 25.0
    default_motion_cooldown: int = 30
    default_clip_duration: int = 10


class CameraControlRequest(BaseModel):
    action: str = Field(..., pattern="^(start_recording|stop_recording|start_detection|stop_detection|restart)$")


class CreateClipRequest(BaseModel):
    camera_id: int
    start_time: datetime
    end_time: datetime
    output_filename: Optional[str] = None
