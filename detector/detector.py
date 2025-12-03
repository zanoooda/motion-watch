#!/usr/bin/env python3
"""Detector service - performs motion detection on frames"""

import os
import cv2
import redis
import pickle
import time
import uuid
import numpy as np

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
MOTION_THRESHOLD = float(os.getenv('MOTION_THRESHOLD', 2500))  # pixels changed

class MotionDetector:
    """Simple motion detector using background subtraction"""
    def __init__(self):
        self.prev_frame = None
        self.motion_detected = False
        
    def detect(self, frame):
        """Detect motion in frame"""
        # Convert to grayscale
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        if self.prev_frame is None:
            self.prev_frame = gray
            return False
        
        # Compute difference
        frame_delta = cv2.absdiff(self.prev_frame, gray)
        thresh = cv2.threshold(frame_delta, 25, 255, cv2.THRESH_BINARY)[1]
        
        # Dilate to fill gaps
        thresh = cv2.dilate(thresh, None, iterations=2)
        
        # Count non-zero pixels
        motion_pixels = cv2.countNonZero(thresh)
        
        # Update previous frame
        self.prev_frame = gray
        
        return motion_pixels > MOTION_THRESHOLD

def listen_for_frames(r, detector):
    """Subscribe to frame stream and detect motion"""
    pubsub = r.pubsub()
    pubsub.subscribe('frames')
    
    print("Listening for frames...")
    
    requester_id = str(uuid.uuid4())
    frame_count = 0
    motion_count = 0
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                frame_meta = pickle.loads(message['data'])
                frame_count += 1
                
                # Request actual frame
                r.publish('frame_request', pickle.dumps({
                    'requester': requester_id,
                    'count': 1
                }))
                
                # Wait for frame response
                response_channel = f"frame_response_{requester_id}"
                response = r.blpop(response_channel, timeout=1)
                
                if response:
                    frame_data = pickle.loads(response[1])
                    frame = frame_data['frame']
                    
                    # Detect motion
                    motion = detector.detect(frame)
                    
                    if motion:
                        motion_count += 1
                        print(f"[MOTION DETECTED] Frame {frame_meta['frame_id']} - Total: {motion_count}")
                        
                        # Publish motion event
                        r.publish('motion_events', pickle.dumps({
                            'frame_id': frame_meta['frame_id'],
                            'timestamp': time.time(),
                            'type': 'motion_start'
                        }))
                        
                        # Store event in Redis
                        r.lpush('motion:events', pickle.dumps({
                            'frame_id': frame_meta['frame_id'],
                            'timestamp': time.time()
                        }))
                        r.ltrim('motion:events', 0, 999)  # Keep last 1000 events
                
                # Log progress
                if frame_count % 30 == 0:
                    print(f"Processed {frame_count} frames, {motion_count} motion events")
                    
            except Exception as e:
                print(f"Detection error: {e}")

def main():
    print("Starting detector service...")
    
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)
    
    # Wait for Redis and streamer
    while True:
        try:
            r.ping()
            if r.get('streamer:status') == b'ready':
                print("Connected to Redis and streamer is ready")
                break
        except:
            pass
        print("Waiting for streamer...")
        time.sleep(1)
    
    # Initialize detector
    detector = MotionDetector()
    
    # Set status
    r.set('detector:status', 'ready')
    
    print("Detector running...")
    
    # Start listening
    listen_for_frames(r, detector)

if __name__ == '__main__':
    main()
