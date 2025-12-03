import asyncio
import json
import logging
import os
import signal
import time
import subprocess
from datetime import datetime
from typing import Dict, Optional, Tuple
import threading
from queue import Queue

import cv2
import numpy as np
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

# Redis channels
CHANNEL_CAMERA_CONTROL = "camera:control"
CHANNEL_MOTION_EVENTS = "motion:events"
CHANNEL_NOTIFICATIONS = "notifications"

shutdown_event = asyncio.Event()

# Sync Redis client for use in threads
_redis_sync = None


def get_sync_redis():
    """Get synchronous Redis client for threads"""
    global _redis_sync
    if _redis_sync is None:
        import redis as sync_redis
        _redis_sync = sync_redis.from_url(REDIS_URL, decode_responses=False)
    return _redis_sync


class MotionDetector:
    """
    Motion detector using OpenCV background subtraction.
    Optimized for CPU with configurable sensitivity.
    """
    
    def __init__(
        self,
        camera_id: int,
        url: str,
        sensitivity: float = 25.0,
        min_area: int = 50,  # Very small area = extremely sensitive
        cooldown: int = 30,
        detection_zones: Optional[list] = None,
        save_snapshots: bool = True,
        save_video_clips: bool = False,
        video_clip_duration: int = 10,
        audio_enabled: bool = True
    ):
        self.camera_id = camera_id
        self.url = url
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.cooldown = cooldown
        self.detection_zones = detection_zones
        self.save_snapshots = save_snapshots
        self.save_video_clips = save_video_clips
        self.video_clip_duration = video_clip_duration
        self.audio_enabled = audio_enabled
        
        # State
        self.running = False
        self.last_motion_time = 0
        self.capture = None
        self.thread = None
        self.event_queue: Queue = Queue()
        self.last_frame = None  # For live view
        self.recording_clip = False  # Currently recording clip
        
        # Background subtractor - MOG2 optimized for HIGH sensitivity
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=50,  # Very short history for fast adaptation
            varThreshold=5,  # Very low threshold = extremely sensitive
            detectShadows=False
        )
        
        # Frame processing settings
        self.process_width = 320  # Process at lower resolution
        self.process_height = 240
        self.skip_frames = 0  # Process every frame for maximum sensitivity
        self.frame_count = 0
    
    def start(self):
        """Start motion detection in separate thread"""
        if self.running:
            logger.warning(f"Detector for camera {self.camera_id} already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.thread.start()
        logger.info(f"Motion detector started for camera {self.camera_id}")
    
    def stop(self):
        """Stop motion detection"""
        self.running = False
        if self.capture:
            self.capture.release()
            self.capture = None
        if self.thread:
            self.thread.join(timeout=5)
        logger.info(f"Motion detector stopped for camera {self.camera_id}")
    
    def _detection_loop(self):
        """Main detection loop running in separate thread"""
        reconnect_delay = 1
        max_reconnect_delay = 30
        
        while self.running:
            try:
                # Use FFmpeg for all local devices - more reliable in Docker
                if self.url.startswith('/dev/video'):
                    self._ffmpeg_capture_loop(reconnect_delay, max_reconnect_delay)
                else:
                    self._opencv_capture_loop(reconnect_delay, max_reconnect_delay)
                    
            except Exception as e:
                logger.error(f"Error in detection loop for camera {self.camera_id}: {e}")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    def _generate_test_frame(self, frame_counter):
        """Generate test pattern frame when camera is unavailable"""
        width, height = 640, 480
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Draw moving rectangle
        x = int((frame_counter * 2) % width)
        y = height // 2 - 50
        cv2.rectangle(frame, (x, y), (x + 100, y + 100), (0, 255, 0), -1)
        
        # Add text
        text = f"Test Pattern - Camera {self.camera_id}"
        cv2.putText(frame, text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(frame, f"Frame: {frame_counter}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 1)
        
        return frame
    
    def _ffmpeg_capture_loop(self, reconnect_delay, max_reconnect_delay):
        """Capture using FFmpeg for local camera devices"""
        width, height = 640, 480
        
        cmd = [
            'ffmpeg',
            '-f', 'v4l2',
            '-video_size', f'{width}x{height}',
            '-framerate', '10',
            '-i', self.url,
            '-f', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-an',
            '-'
        ]
        
        logger.info(f"Starting FFmpeg capture for camera {self.camera_id}: {' '.join(cmd)}")
        
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=width * height * 3 * 10
            )
        except Exception as e:
            logger.error(f"Failed to start FFmpeg for camera {self.camera_id}: {e}")
            logger.info(f"Falling back to test pattern for camera {self.camera_id}")
            # Fall back to test pattern
            frame_counter = 0
            while self.running:
                frame = self._generate_test_frame(frame_counter)
                self._process_frame(frame)
                frame_counter += 1
                time.sleep(0.1)  # 10 FPS
            return
        
        frame_size = width * height * 3
        logger.info(f"Connected to camera {self.camera_id} via FFmpeg")
        
        # Read stderr in background to avoid blocking
        def log_stderr():
            for line in process.stderr:
                line_str = line.decode('utf-8', errors='ignore').strip()
                if line_str and 'frame=' not in line_str:  # Skip progress lines
                    logger.debug(f"FFmpeg [{self.camera_id}]: {line_str}")
        
        import threading
        stderr_thread = threading.Thread(target=log_stderr, daemon=True)
        stderr_thread.start()
        
        consecutive_errors = 0
        frame_counter = 0
        try:
            while self.running:
                raw_frame = process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    consecutive_errors += 1
                    if consecutive_errors > 10:
                        logger.warning(f"FFmpeg failed for camera {self.camera_id}, using test pattern")
                        # Fall back to test pattern
                        process.terminate()
                        while self.running:
                            frame = self._generate_test_frame(frame_counter)
                            self._process_frame(frame)
                            frame_counter += 1
                            time.sleep(0.1)  # 10 FPS
                        break
                    continue
                
                consecutive_errors = 0
                frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
                self._process_frame(frame)
                
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    
    def _opencv_local_capture_loop(self, reconnect_delay, max_reconnect_delay):
        """Capture using OpenCV for local camera devices"""
        # Use device path directly
        device_path = self.url
        
        # Try different backends for Docker compatibility
        backends = [cv2.CAP_V4L2, cv2.CAP_ANY]
        self.capture = None
        
        for backend in backends:
            self.capture = cv2.VideoCapture(device_path, backend)
            if self.capture.isOpened():
                logger.info(f"Opened {device_path} with backend {backend}")
                break
            self.capture.release()
        
        if not self.capture or not self.capture.isOpened():
            logger.error(f"Failed to open device {device_path} for camera {self.camera_id}")
            time.sleep(reconnect_delay)
            return
        
        # Set camera properties for better performance
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.capture.set(cv2.CAP_PROP_FPS, 15)
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimize latency
        
        logger.info(f"Connected to camera {self.camera_id} ({device_path}) via OpenCV")
        
        consecutive_failures = 0
        try:
            while self.running and self.capture.isOpened():
                ret, frame = self.capture.read()
                
                if not ret:
                    consecutive_failures += 1
                    if consecutive_failures > 10:
                        logger.warning(f"Too many read failures from camera {self.camera_id}")
                        break
                    time.sleep(0.1)
                    continue
                
                consecutive_failures = 0
                self._process_frame(frame)
        finally:
            if self.capture:
                self.capture.release()
                self.capture = None
    
    def _opencv_capture_loop(self, reconnect_delay, max_reconnect_delay):
        """Capture using OpenCV for RTSP streams"""
        self.capture = cv2.VideoCapture(self.url)
        
        if not self.capture.isOpened():
            logger.error(f"Failed to open stream for camera {self.camera_id}")
            time.sleep(reconnect_delay)
            return
        
        logger.info(f"Connected to camera {self.camera_id}")
        
        try:
            while self.running and self.capture.isOpened():
                ret, frame = self.capture.read()
                
                if not ret:
                    logger.warning(f"Failed to read frame from camera {self.camera_id}")
                    break
                
                self._process_frame(frame)
        finally:
            if self.capture:
                self.capture.release()
                self.capture = None
    
    def _process_frame(self, frame: np.ndarray):
        """Process a single frame for motion detection"""
        self.frame_count += 1
        
        # Store last frame for live view (cache in Redis)
        self.last_frame = frame
        
        # Cache every frame for live view (faster updates)
        self._cache_snapshot(frame)
        
        # Skip frames for motion detection (performance)
        if self.frame_count % self.skip_frames != 0:
            return
        
        # Detect motion
        motion_detected, confidence, contours = self._detect_motion(frame)
        
        if motion_detected:
            current_time = time.time()
            
            # Check cooldown
            if current_time - self.last_motion_time >= self.cooldown:
                self.last_motion_time = current_time
                
                snapshot_path = None
                video_clip_path = None
                
                # Save snapshot if enabled
                if self.save_snapshots:
                    snapshot_path = self._save_snapshot(frame, contours)
                
                # Start video clip recording if enabled
                if self.save_video_clips and not self.recording_clip:
                    video_clip_path = self._start_video_clip()
                
                # Queue motion event
                self.event_queue.put({
                    "camera_id": self.camera_id,
                    "timestamp": datetime.now().isoformat(),
                    "confidence": confidence,
                    "snapshot_path": snapshot_path,
                    "video_clip_path": video_clip_path
                })
                
                logger.info(f"Motion detected on camera {self.camera_id}, confidence: {confidence:.2f}")
    
    def _cache_snapshot(self, frame: np.ndarray):
        """Cache current frame in Redis for live view"""
        try:
            # Encode frame as JPEG with lower quality for speed
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            
            # Cache in Redis with 1 second expiry for live view
            redis_client = get_sync_redis()
            redis_client.setex(f"snapshot:{self.camera_id}", 1, buffer.tobytes())
        except Exception as e:
            # Don't log every frame to avoid spam
            pass
    
    def _start_video_clip(self) -> Optional[str]:
        """Start recording a video clip with audio"""
        if self.recording_clip:
            return None
        
        self.recording_clip = True
        
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        
        clip_dir = os.path.join(STORAGE_PATH, f"camera_{self.camera_id}", date_str, "clips")
        os.makedirs(clip_dir, exist_ok=True)
        
        clip_path = os.path.join(clip_dir, f"motion_{time_str}.mp4")
        
        # Start FFmpeg to record clip in background
        threading.Thread(
            target=self._record_video_clip,
            args=(clip_path,),
            daemon=True
        ).start()
        
        return clip_path
    
    def _record_video_clip(self, output_path: str):
        """Record video clip using FFmpeg"""
        try:
            duration = self.video_clip_duration
            
            # Build FFmpeg command based on source type
            if self.url.startswith('/dev/video'):
                # Local camera - record with audio if enabled
                if self.audio_enabled:
                    cmd = [
                        'ffmpeg', '-y',
                        '-f', 'v4l2', '-i', self.url,
                        '-f', 'alsa', '-i', 'default',
                        '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-c:a', 'aac', '-b:a', '128k',
                        output_path
                    ]
                else:
                    cmd = [
                        'ffmpeg', '-y',
                        '-f', 'v4l2', '-i', self.url,
                        '-t', str(duration),
                        '-c:v', 'libx264', '-preset', 'ultrafast',
                        '-an',
                        output_path
                    ]
            else:
                # RTSP stream
                cmd = [
                    'ffmpeg', '-y',
                    '-rtsp_transport', 'tcp',
                    '-i', self.url,
                    '-t', str(duration),
                    '-c:v', 'libx264', '-preset', 'ultrafast',
                    '-c:a', 'aac' if self.audio_enabled else '-an',
                    output_path
                ]
            
            logger.info(f"Recording {duration}s video clip for camera {self.camera_id}")
            
            process = subprocess.run(
                cmd,
                capture_output=True,
                timeout=duration + 10
            )
            
            if process.returncode == 0:
                logger.info(f"Video clip saved: {output_path}")
            else:
                logger.error(f"Failed to save video clip: {process.stderr.decode()[:200]}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"Video clip recording timed out for camera {self.camera_id}")
        except Exception as e:
            logger.error(f"Error recording video clip: {e}")
        finally:
            self.recording_clip = False
    
    def _detect_motion(self, frame: np.ndarray) -> Tuple[bool, float, list]:
        """
        Detect motion in frame using background subtraction.
        Returns: (motion_detected, confidence, contours)
        """
        # Resize for faster processing
        small_frame = cv2.resize(frame, (self.process_width, self.process_height))
        
        # Convert to grayscale
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # Apply background subtraction
        fg_mask = self.bg_subtractor.apply(blurred)
        
        # Apply threshold based on sensitivity
        threshold = int(255 * (100 - self.sensitivity) / 100)
        _, thresh = cv2.threshold(fg_mask, threshold, 255, cv2.THRESH_BINARY)
        
        # Dilate to fill gaps
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area
        significant_contours = []
        total_motion_area = 0
        
        # Scale min_area to match resized frame
        scale_x = self.process_width / frame.shape[1]
        scale_y = self.process_height / frame.shape[0]
        scaled_min_area = self.min_area * scale_x * scale_y
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= scaled_min_area:
                # Check if contour is within detection zones
                if self._is_in_detection_zone(contour):
                    significant_contours.append(contour)
                    total_motion_area += area
        
        # Calculate confidence based on motion area
        frame_area = self.process_width * self.process_height
        confidence = min(total_motion_area / frame_area * 100, 100)
        
        motion_detected = len(significant_contours) > 0
        
        return motion_detected, confidence, significant_contours
    
    def _is_in_detection_zone(self, contour) -> bool:
        """Check if contour is within configured detection zones"""
        if not self.detection_zones:
            return True  # No zones configured, detect everywhere
        
        # Get contour center
        M = cv2.moments(contour)
        if M["m00"] == 0:
            return False
        
        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        
        # Scale to frame coordinates
        cx = int(cx / self.process_width * 100)  # Normalize to 0-100
        cy = int(cy / self.process_height * 100)
        
        # Check if point is in any zone
        for zone in self.detection_zones:
            x1, y1, x2, y2 = zone
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return True
        
        return False
    
    def _save_snapshot(self, frame: np.ndarray, contours: list) -> str:
        """Save snapshot with motion highlighted"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H-%M-%S")
        
        snapshot_dir = os.path.join(STORAGE_PATH, f"camera_{self.camera_id}", date_str, "snapshots")
        os.makedirs(snapshot_dir, exist_ok=True)
        
        snapshot_path = os.path.join(snapshot_dir, f"motion_{time_str}.jpg")
        
        # Make a writable copy of the frame
        frame = frame.copy()
        
        # Draw contours on frame (optional visualization)
        # Scale contours back to original frame size
        scale_x = frame.shape[1] / self.process_width
        scale_y = frame.shape[0] / self.process_height
        
        for contour in contours:
            scaled_contour = (contour * [scale_x, scale_y]).astype(np.int32)
            x, y, w, h = cv2.boundingRect(scaled_contour)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Add timestamp
        cv2.putText(
            frame,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (255, 255, 255),
            2
        )
        
        cv2.imwrite(snapshot_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        
        return snapshot_path
    
    def get_pending_events(self) -> list:
        """Get all pending motion events from queue"""
        events = []
        while not self.event_queue.empty():
            events.append(self.event_queue.get_nowait())
        return events


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


async def handle_control_message(message: dict, detectors: Dict[int, MotionDetector]):
    """Handle control messages from Redis"""
    action = message.get("action")
    camera_id = message.get("camera_id")
    
    logger.info(f"Received control message: {action} for camera {camera_id}")
    
    if action == "start_detection":
        if camera_id in detectors:
            detectors[camera_id].start()
        else:
            # Fetch camera info and create detector
            cameras = await fetch_cameras()
            for cam in cameras:
                if cam["id"] == camera_id:
                    detector = MotionDetector(
                        camera_id=cam["id"],
                        url=cam["url"],
                        sensitivity=cam.get("motion_sensitivity", 25.0),
                        min_area=cam.get("motion_min_area", 50),
                        cooldown=cam.get("motion_cooldown", 30),
                    )
                    detectors[camera_id] = detector
                    detector.start()
                    break
    
    elif action == "stop_detection":
        if camera_id in detectors:
            detectors[camera_id].stop()
    
    elif action == "camera_added":
        url = message.get("url")
        if url:
            # Fetch full camera info to get all settings
            cameras = await fetch_cameras()
            for cam in cameras:
                if cam["id"] == camera_id:
                    detector = MotionDetector(
                        camera_id=cam["id"],
                        url=cam["url"],
                        sensitivity=cam.get("motion_sensitivity", 25.0),
                        min_area=cam.get("motion_min_area", 500),
                        cooldown=cam.get("motion_cooldown", 30)
                    )
                    detectors[camera_id] = detector
                    # Auto-start if motion detection enabled
                    if cam.get("motion_detection_enabled", True):
                        detector.start()
                    break
    
    elif action == "camera_deleted":
        if camera_id in detectors:
            detectors[camera_id].stop()
            del detectors[camera_id]
    
    elif action == "camera_updated":
        changes = message.get("changes", {})
        if camera_id in detectors:
            detector = detectors[camera_id]
            if "motion_sensitivity" in changes:
                detector.sensitivity = changes["motion_sensitivity"]
            if "motion_min_area" in changes:
                detector.min_area = changes["motion_min_area"]
            if "motion_cooldown" in changes:
                detector.cooldown = changes["motion_cooldown"]
            if "save_snapshots" in changes:
                detector.save_snapshots = changes["save_snapshots"]
            if "save_video_clips" in changes:
                detector.save_video_clips = changes["save_video_clips"]
            if "video_clip_duration" in changes:
                detector.video_clip_duration = changes["video_clip_duration"]
            if "audio_enabled" in changes:
                detector.audio_enabled = changes["audio_enabled"]
            if "url" in changes:
                detector.stop()
                detector.url = changes["url"]
                detector.start()


async def subscribe_to_control_channel(detectors: Dict[int, MotionDetector]):
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
                    await handle_control_message(data, detectors)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in control message: {message['data']}")
            await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(CHANNEL_CAMERA_CONTROL)
        await redis_client.close()


async def event_publisher(detectors: Dict[int, MotionDetector]):
    """Publish motion events to Redis and backend"""
    redis_client = redis.from_url(REDIS_URL)
    
    while not shutdown_event.is_set():
        for detector in detectors.values():
            events = detector.get_pending_events()
            
            for event in events:
                # Publish to notification channel
                await redis_client.publish(CHANNEL_NOTIFICATIONS, json.dumps(event))
                
                # Save event to backend
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            f"{BACKEND_URL}/api/events/",
                            json={
                                "camera_id": event["camera_id"],
                                "event_type": "motion",
                                "confidence": event["confidence"],
                                "snapshot_path": event["snapshot_path"]
                            }
                        )
                        if response.status_code == 200:
                            logger.info(f"Motion event saved: {event}")
                        else:
                            logger.error(f"Failed to save event: {response.status_code}")
                    except Exception as e:
                        logger.error(f"Failed to save event to backend: {e}")
        
        await asyncio.sleep(1)
    
    await redis_client.close()


async def init_detectors() -> Dict[int, MotionDetector]:
    """Initialize detectors for all enabled cameras"""
    detectors = {}
    
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
        return detectors
    
    for camera in cameras:
        if camera.get("is_enabled") and camera.get("motion_detection_enabled"):
            detector = MotionDetector(
                camera_id=camera["id"],
                url=camera["url"],
                sensitivity=camera.get("motion_sensitivity", 25.0),
                min_area=camera.get("motion_min_area", 50),
                cooldown=camera.get("motion_cooldown", 30),
                save_snapshots=camera.get("save_snapshots", True),
                save_video_clips=camera.get("save_video_clips", False),
                video_clip_duration=camera.get("video_clip_duration", 10),
                audio_enabled=camera.get("audio_enabled", True)
            )
            detectors[camera["id"]] = detector
            detector.start()
    
    return detectors


async def main():
    """Main entry point"""
    logger.info("Starting Motion Watch Detector Service")
    
    # Initialize detectors for existing cameras
    detectors = await init_detectors()
    
    # Start tasks
    tasks = [
        asyncio.create_task(subscribe_to_control_channel(detectors)),
        asyncio.create_task(event_publisher(detectors)),
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
        # Stop all detectors
        logger.info("Stopping all detectors...")
        for detector in detectors.values():
            detector.stop()
        
        # Cancel tasks
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Detector service stopped")


if __name__ == "__main__":
    asyncio.run(main())
