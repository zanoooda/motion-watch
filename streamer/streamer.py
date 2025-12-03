#!/usr/bin/env python3
"""Streamer service - reads video and maintains circular buffer in RAM"""

import os
import cv2
import redis
import pickle
import time
from collections import deque
from threading import Thread, Lock

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
VIDEO_SOURCE = os.getenv('VIDEO_SOURCE', '0')
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', 300))  # frames in RAM buffer

class FrameBuffer:
    """Circular buffer for frames in RAM"""
    def __init__(self, maxlen):
        self.buffer = deque(maxlen=maxlen)
        self.lock = Lock()
        self.frame_counter = 0
    
    def add_frame(self, frame):
        with self.lock:
            self.frame_counter += 1
            self.buffer.append({
                'frame_id': self.frame_counter,
                'timestamp': time.time(),
                'frame': frame
            })
            return self.frame_counter
    
    def get_latest_frames(self, n=1):
        with self.lock:
            if n >= len(self.buffer):
                return list(self.buffer)
            return list(self.buffer)[-n:]

def generate_test_video():
    """Generate a simple test video if no source available"""
    print("Generating synthetic test video...")
    width, height = 640, 480
    while True:
        # Create a frame with moving rectangle
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        t = int(time.time() * 50) % width
        cv2.rectangle(frame, (t, 200), (t+50, 300), (0, 255, 0), -1)
        yield frame
        time.sleep(0.033)  # ~30 fps

def read_video_stream(buffer, r):
    """Read video stream and populate buffer"""
    print(f"Opening video source: {VIDEO_SOURCE}")
    
    # Try to open video source
    if VIDEO_SOURCE.startswith('rtsp://') or VIDEO_SOURCE.isdigit():
        cap = cv2.VideoCapture(VIDEO_SOURCE)
    elif os.path.exists(VIDEO_SOURCE):
        cap = cv2.VideoCapture(VIDEO_SOURCE)
    else:
        print("No valid video source found, using synthetic video")
        cap = None
    
    fps = 30
    if cap and cap.isOpened():
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        print(f"Video opened successfully, FPS: {fps}")
    
    frame_delay = 1.0 / fps
    
    while True:
        if cap and cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("Restarting video...")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
        else:
            # Use synthetic video
            import numpy as np
            frame = np.zeros((480, 640, 3), dtype=np.uint8)
            t = int(time.time() * 50) % 640
            cv2.rectangle(frame, (t, 200), (t+50, 300), (0, 255, 0), -1)
        
        # Add to buffer
        frame_id = buffer.add_frame(frame)
        
        # Publish frame metadata to Redis
        try:
            r.publish('frames', pickle.dumps({
                'frame_id': frame_id,
                'timestamp': time.time(),
                'shape': frame.shape
            }))
        except Exception as e:
            print(f"Redis publish error: {e}")
        
        time.sleep(frame_delay)

def serve_frames(buffer, r):
    """Serve frames via Redis on request"""
    pubsub = r.pubsub()
    pubsub.subscribe('frame_request')
    
    print("Frame server ready")
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                request = pickle.loads(message['data'])
                frames = buffer.get_latest_frames(request.get('count', 1))
                
                # Send frames back
                for frame_data in frames:
                    r.publish(f"frame_response_{request['requester']}", 
                             pickle.dumps(frame_data))
            except Exception as e:
                print(f"Frame serve error: {e}")

def main():
    print("Starting streamer service...")
    
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    
    # Wait for Redis
    while True:
        try:
            r.ping()
            print("Connected to Redis")
            break
        except:
            print("Waiting for Redis...")
            time.sleep(1)
    
    # Initialize buffer
    buffer = FrameBuffer(BUFFER_SIZE)
    
    # Publish service ready
    r.set('streamer:status', 'ready')
    
    # Start reader thread
    reader_thread = Thread(target=read_video_stream, args=(buffer, r), daemon=True)
    reader_thread.start()
    
    # Start server thread
    server_thread = Thread(target=serve_frames, args=(buffer, r), daemon=True)
    server_thread.start()
    
    print("Streamer running...")
    
    # Keep alive
    while True:
        time.sleep(1)
        r.set('streamer:heartbeat', time.time())

if __name__ == '__main__':
    main()
