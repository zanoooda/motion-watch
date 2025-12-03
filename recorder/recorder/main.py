import asyncio
import json
import logging
import os
import signal
import subprocess
from datetime import datetime
from typing import Dict, Optional

import httpx
import redis.asyncio as redis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/recordings")
SEGMENT_DURATION = int(os.environ.get("SEGMENT_DURATION", "10"))

# Redis channels
CHANNEL_CAMERA_CONTROL = "camera:control"

# Active recording processes
active_recorders: Dict[int, subprocess.Popen] = {}
shutdown_event = asyncio.Event()


class CameraRecorder:
    """Handles FFmpeg recording for a single camera"""
    
    def __init__(self, camera_id: int, url: str, audio_enabled: bool = True):
        self.camera_id = camera_id
        self.url = url
        self.audio_enabled = audio_enabled
        self.process: Optional[subprocess.Popen] = None
        self.running = False
    
    def get_output_path(self) -> str:
        """Get output path for current segment"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        
        output_dir = os.path.join(STORAGE_PATH, f"camera_{self.camera_id}", date_str, "segments")
        os.makedirs(output_dir, exist_ok=True)
        
        return os.path.join(output_dir, f"{time_str}.ts")
    
    def build_ffmpeg_command(self) -> list:
        """Build FFmpeg command for recording"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = os.path.join(STORAGE_PATH, f"camera_{self.camera_id}", date_str, "segments")
        os.makedirs(output_dir, exist_ok=True)
        
        # Output pattern for segments
        output_pattern = os.path.join(output_dir, "%H-%M-%S.ts")
        
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "warning",
        ]
        
        # Different input options for local devices vs RTSP streams
        if self.url.startswith('/dev/video'):
            # Local camera device (V4L2)
            cmd.extend([
                "-f", "v4l2",
                "-input_format", "mjpeg",
                "-video_size", "640x480",
                "-framerate", "30",
                "-i", self.url,
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-tune", "zerolatency",
            ])
        else:
            # RTSP stream
            cmd.extend([
                "-rtsp_transport", "tcp",
                "-i", self.url,
                "-c:v", "copy",
            ])
        
        if self.audio_enabled and not self.url.startswith('/dev/video'):
            cmd.extend(["-c:a", "aac", "-b:a", "128k"])
        else:
            cmd.extend(["-an"])  # No audio for local cameras or if disabled
        
        cmd.extend([
            "-f", "segment",
            "-segment_time", str(SEGMENT_DURATION),
            "-segment_format", "mpegts",
            "-strftime", "1",
            "-reset_timestamps", "1",
            output_pattern
        ])
        
        return cmd
    
    async def start(self):
        """Start recording"""
        if self.running:
            logger.warning(f"Camera {self.camera_id} is already recording")
            return
        
        cmd = self.build_ffmpeg_command()
        logger.info(f"Starting recording for camera {self.camera_id}: {' '.join(cmd)}")
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.running = True
            logger.info(f"Recording started for camera {self.camera_id}")
            
            # Update camera status via API
            async with httpx.AsyncClient() as client:
                try:
                    await client.put(
                        f"{BACKEND_URL}/api/cameras/{self.camera_id}",
                        json={"status": "recording"}
                    )
                except Exception as e:
                    logger.error(f"Failed to update camera status: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to start recording for camera {self.camera_id}: {e}")
            self.running = False
    
    async def stop(self):
        """Stop recording"""
        if not self.running or not self.process:
            return
        
        logger.info(f"Stopping recording for camera {self.camera_id}")
        
        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        
        self.running = False
        self.process = None
        
        # Update camera status via API
        async with httpx.AsyncClient() as client:
            try:
                await client.put(
                    f"{BACKEND_URL}/api/cameras/{self.camera_id}",
                    json={"status": "online"}
                )
            except Exception as e:
                logger.error(f"Failed to update camera status: {e}")
    
    def is_alive(self) -> bool:
        """Check if FFmpeg process is still running"""
        if not self.process:
            return False
        return self.process.poll() is None


async def fetch_cameras() -> list:
    """Fetch camera list from backend API"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/cameras/")
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.error(f"Failed to fetch cameras: {e}")
    return []


async def handle_control_message(message: dict, recorders: Dict[int, CameraRecorder]):
    """Handle control messages from Redis"""
    action = message.get("action")
    camera_id = message.get("camera_id")
    
    logger.info(f"Received control message: {action} for camera {camera_id}")
    
    if action == "start_recording":
        if camera_id in recorders:
            await recorders[camera_id].start()
        else:
            # Fetch camera info and create recorder
            cameras = await fetch_cameras()
            for cam in cameras:
                if cam["id"] == camera_id:
                    recorder = CameraRecorder(
                        camera_id=cam["id"],
                        url=cam["url"],
                        audio_enabled=cam.get("audio_enabled", True)
                    )
                    recorders[camera_id] = recorder
                    await recorder.start()
                    break
    
    elif action == "stop_recording":
        if camera_id in recorders:
            await recorders[camera_id].stop()
    
    elif action == "camera_added":
        url = message.get("url")
        if url:
            recorder = CameraRecorder(camera_id=camera_id, url=url)
            recorders[camera_id] = recorder
    
    elif action == "camera_deleted":
        if camera_id in recorders:
            await recorders[camera_id].stop()
            del recorders[camera_id]
    
    elif action == "camera_updated":
        changes = message.get("changes", {})
        if camera_id in recorders and "url" in changes:
            # Restart recorder with new URL
            await recorders[camera_id].stop()
            recorders[camera_id].url = changes["url"]
            await recorders[camera_id].start()


async def subscribe_to_control_channel(recorders: Dict[int, CameraRecorder]):
    """Subscribe to Redis control channel"""
    redis_client = redis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()
    
    await pubsub.subscribe(CHANNEL_CAMERA_CONTROL)
    logger.info(f"Subscribed to {CHANNEL_CAMERA_CONTROL}")
    
    try:
        while not shutdown_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await handle_control_message(data, recorders)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in control message: {message['data']}")
            await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(CHANNEL_CAMERA_CONTROL)
        await redis_client.close()


async def health_check_loop(recorders: Dict[int, CameraRecorder]):
    """Periodically check recorder health and restart if needed"""
    while not shutdown_event.is_set():
        for camera_id, recorder in list(recorders.items()):
            if recorder.running and not recorder.is_alive():
                logger.warning(f"Recorder for camera {camera_id} died, restarting...")
                recorder.running = False
                await recorder.start()
        
        await asyncio.sleep(10)


async def init_recorders() -> Dict[int, CameraRecorder]:
    """Initialize recorders for all enabled cameras"""
    recorders = {}
    
    # Wait for backend to be ready
    for _ in range(30):
        try:
            cameras = await fetch_cameras()
            break
        except Exception:
            logger.info("Waiting for backend...")
            await asyncio.sleep(2)
    else:
        logger.error("Backend not available after 60 seconds")
        return recorders
    
    for camera in cameras:
        if camera.get("is_enabled") and camera.get("recording_enabled"):
            recorder = CameraRecorder(
                camera_id=camera["id"],
                url=camera["url"],
                audio_enabled=camera.get("audio_enabled", True)
            )
            recorders[camera["id"]] = recorder
            await recorder.start()
    
    return recorders


async def main():
    """Main entry point"""
    logger.info("Starting Motion Watch Recorder Service")
    
    # Initialize recorders for existing cameras
    recorders = await init_recorders()
    
    # Start tasks
    tasks = [
        asyncio.create_task(subscribe_to_control_channel(recorders)),
        asyncio.create_task(health_check_loop(recorders)),
    ]
    
    # Handle shutdown signals
    def signal_handler():
        logger.info("Received shutdown signal")
        shutdown_event.set()
    
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
    
    try:
        await shutdown_event.wait()
    finally:
        # Stop all recorders
        logger.info("Stopping all recorders...")
        for recorder in recorders.values():
            await recorder.stop()
        
        # Cancel tasks
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Recorder service stopped")


if __name__ == "__main__":
    asyncio.run(main())
