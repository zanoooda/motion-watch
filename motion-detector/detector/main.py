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
        min_area: int = 500,
        cooldown: int = 30,
        detection_zones: Optional[list] = None
    ):
        self.camera_id = camera_id
        self.url = url
        self.sensitivity = sensitivity
        self.min_area = min_area
        self.cooldown = cooldown
        self.detection_zones = detection_zones
        
        # State
        self.running = False
        self.last_motion_time = 0
        self.capture = None
        self.thread = None
        self.event_queue: Queue = Queue()
        
        # Background subtractor - MOG2 is efficient on CPU
        self.bg_subtractor = cv2.createBackgroundSubtractorMOG2(
            history=500,
            varThreshold=16,
            detectShadows=False
        )
        
        # Frame processing settings
        self.process_width = 320  # Process at lower resolution
        self.process_height = 240
        self.skip_frames = 2  # Process every Nth frame
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
                # Use FFmpeg for local devices, OpenCV for RTSP
                if self.url.startswith('/dev/video'):
                    self._ffmpeg_capture_loop(reconnect_delay, max_reconnect_delay)
                else:
                    self._opencv_capture_loop(reconnect_delay, max_reconnect_delay)
                    
            except Exception as e:
                logger.error(f"Error in detection loop for camera {self.camera_id}: {e}")
                time.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, max_reconnect_delay)
    
    def _ffmpeg_capture_loop(self, reconnect_delay, max_reconnect_delay):
        """Capture using FFmpeg for local camera devices"""
        width, height = 640, 480
        
        cmd = [
            'ffmpeg',
            '-f', 'v4l2',
            '-input_format', 'yuyv422',  # More compatible than mjpeg
            '-video_size', f'{width}x{height}',
            '-framerate', '15',
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
            time.sleep(reconnect_delay)
            return
        
        frame_size = width * height * 3
        logger.info(f"Connected to camera {self.camera_id} via FFmpeg")
        
        consecutive_errors = 0
        try:
            while self.running:
                raw_frame = process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    consecutive_errors += 1
                    if consecutive_errors > 5:
                        logger.warning(f"Too many incomplete frames from camera {self.camera_id}")
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
        
        # Skip frames for performance
        if self.frame_count % self.skip_frames != 0:
            return
        
        # Detect motion
        motion_detected, confidence, contours = self._detect_motion(frame)
        
        if motion_detected:
            current_time = time.time()
            
            # Check cooldown
            if current_time - self.last_motion_time >= self.cooldown:
                self.last_motion_time = current_time
                
                # Save snapshot
                snapshot_path = self._save_snapshot(frame, contours)
                
                # Queue motion event
                self.event_queue.put({
                    "camera_id": self.camera_id,
                    "timestamp": datetime.now().isoformat(),
                    "confidence": confidence,
                    "snapshot_path": snapshot_path
                })
                
                logger.info(f"Motion detected on camera {self.camera_id}, confidence: {confidence:.2f}")
    
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
                        min_area=cam.get("motion_min_area", 500),
                        cooldown=cam.get("motion_cooldown", 30)
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
            detector = MotionDetector(camera_id=camera_id, url=url)
            detectors[camera_id] = detector
    
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
                min_area=camera.get("motion_min_area", 500),
                cooldown=camera.get("motion_cooldown", 30)
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
