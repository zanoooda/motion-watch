from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from contextlib import asynccontextmanager
import os

from app.core.database import init_db
from app.core.config import get_settings
from app.api import cameras, events, recordings, settings as settings_api

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    
    # Ensure storage directory exists
    os.makedirs(settings.storage_path, exist_ok=True)
    
    yield
    # Shutdown


app = FastAPI(
    title="Motion Watch API",
    description="Video surveillance system with motion detection",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(cameras.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(recordings.router, prefix="/api")
app.include_router(settings_api.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "Motion Watch API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Serve recordings as static files
@app.get("/api/media/{camera_id}/{date}/{segment_type}/{filename}")
async def serve_media(camera_id: int, date: str, segment_type: str, filename: str):
    """Serve recorded media files"""
    file_path = os.path.join(
        settings.storage_path,
        f"camera_{camera_id}",
        date,
        segment_type,
        filename
    )
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type
    if filename.endswith('.ts'):
        media_type = "video/mp2t"
    elif filename.endswith('.mp4'):
        media_type = "video/mp4"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg'):
        media_type = "image/jpeg"
    elif filename.endswith('.png'):
        media_type = "image/png"
    else:
        media_type = "application/octet-stream"
    
    return FileResponse(file_path, media_type=media_type)


@app.get("/api/snapshots/{camera_id}/latest")
async def get_latest_snapshot(camera_id: int):
    """Get the latest snapshot for a camera"""
    snapshots_dir = os.path.join(
        settings.storage_path,
        f"camera_{camera_id}",
        "snapshots"
    )
    
    if not os.path.exists(snapshots_dir):
        raise HTTPException(status_code=404, detail="No snapshots available")
    
    # Get the most recent snapshot
    snapshots = [f for f in os.listdir(snapshots_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
    if not snapshots:
        raise HTTPException(status_code=404, detail="No snapshots available")
    
    latest = max(snapshots, key=lambda f: os.path.getmtime(os.path.join(snapshots_dir, f)))
    file_path = os.path.join(snapshots_dir, latest)
    
    return FileResponse(file_path, media_type="image/jpeg")
