from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from app.core.database import Base


class CameraStatus(str, enum.Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    ERROR = "error"


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)
    
    status = Column(SQLEnum(CameraStatus), default=CameraStatus.OFFLINE)
    is_enabled = Column(Boolean, default=True)
    motion_detection_enabled = Column(Boolean, default=True)
    motion_sensitivity = Column(Float, default=25.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    events = relationship("MotionEvent", back_populates="camera", cascade="all, delete-orphan")


class MotionEvent(Base):
    __tablename__ = "motion_events"
    
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    confidence = Column(Float, nullable=True)
    snapshot_path = Column(String(1024), nullable=True)
    
    camera = relationship("Camera", back_populates="events")


class NotificationSettings(Base):
    __tablename__ = "notification_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    
    telegram_bot_token = Column(String(500), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)
    telegram_enabled = Column(Boolean, default=False)
    
    send_photo = Column(Boolean, default=True)
    send_video = Column(Boolean, default=False)
    send_text_only = Column(Boolean, default=False)
    
    custom_message = Column(Text, nullable=True)
    cooldown_seconds = Column(Integer, default=60)
    
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
