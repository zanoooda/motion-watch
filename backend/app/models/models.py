from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
import enum


class CameraStatus(str, enum.Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    RECORDING = "recording"
    ERROR = "error"


class Camera(Base):
    __tablename__ = "cameras"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1024), nullable=False)  # RTSP or HTTP URL
    
    # Status
    status = Column(SQLEnum(CameraStatus), default=CameraStatus.OFFLINE)
    is_enabled = Column(Boolean, default=True)
    
    # Recording settings
    recording_enabled = Column(Boolean, default=True)
    audio_enabled = Column(Boolean, default=True)
    
    # Motion detection settings
    motion_detection_enabled = Column(Boolean, default=True)
    motion_sensitivity = Column(Float, default=25.0)  # Threshold for motion (0-100)
    motion_min_area = Column(Integer, default=500)    # Minimum contour area
    motion_cooldown = Column(Integer, default=30)     # Seconds between notifications
    
    # Detection zones (JSON format: [[x1,y1,x2,y2], ...])
    detection_zones = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    events = relationship("MotionEvent", back_populates="camera", cascade="all, delete-orphan")


class MotionEvent(Base):
    __tablename__ = "motion_events"
    
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    
    # Event details
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    confidence = Column(Float, nullable=True)  # Motion detection confidence
    
    # File paths
    snapshot_path = Column(String(1024), nullable=True)  # Path to snapshot image
    video_clip_path = Column(String(1024), nullable=True)  # Path to video clip
    
    # Notification status
    notification_sent = Column(Boolean, default=False)
    
    # Relationship
    camera = relationship("Camera", back_populates="events")


class Recording(Base):
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=False)
    
    # File info
    file_path = Column(String(1024), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    file_size = Column(Integer, nullable=True)  # bytes
    
    # Segment info
    is_segment = Column(Boolean, default=True)
    segment_index = Column(Integer, nullable=True)


class SystemSettings(Base):
    __tablename__ = "system_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(255), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
