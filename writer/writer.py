#!/usr/bin/env python3
"""Writer service - writes video chunks to disk"""

import os
import cv2
import redis
import pickle
import time
import uuid
from datetime import datetime
from pathlib import Path

REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', '/data'))
CHUNK_DURATION = int(os.getenv('CHUNK_DURATION', 10))  # seconds

class ChunkWriter:
    """Writes video chunks to disk"""
    def __init__(self, output_dir, chunk_duration):
        self.output_dir = output_dir
        self.chunk_duration = chunk_duration
        self.current_writer = None
        self.chunk_start_time = None
        self.frame_count = 0
        self.chunk_count = 0
        
        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def write_frame(self, frame):
        """Write frame to current chunk or start new chunk"""
        now = time.time()
        
        # Check if need new chunk
        if (self.current_writer is None or 
            self.chunk_start_time is None or
            (now - self.chunk_start_time) >= self.chunk_duration):
            self._start_new_chunk(frame.shape)
        
        # Write frame
        if self.current_writer:
            self.current_writer.write(frame)
            self.frame_count += 1
    
    def _start_new_chunk(self, frame_shape):
        """Start a new video chunk"""
        # Close previous writer
        if self.current_writer:
            self.current_writer.release()
            print(f"Closed chunk {self.chunk_count} with {self.frame_count} frames")
        
        # Create new chunk file
        self.chunk_count += 1
        self.frame_count = 0
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f"chunk_{timestamp}_{self.chunk_count:04d}.mp4"
        
        # Initialize writer
        height, width = frame_shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.current_writer = cv2.VideoWriter(
            str(filename),
            fourcc,
            30.0,  # fps
            (width, height)
        )
        
        self.chunk_start_time = time.time()
        print(f"Started chunk {self.chunk_count}: {filename}")
    
    def close(self):
        """Close current writer"""
        if self.current_writer:
            self.current_writer.release()
            print(f"Closed final chunk {self.chunk_count}")

def listen_for_frames(r, writer):
    """Subscribe to frame stream and write chunks"""
    pubsub = r.pubsub()
    pubsub.subscribe('frames')
    
    print("Listening for frames to write...")
    
    requester_id = str(uuid.uuid4())
    frame_count = 0
    
    for message in pubsub.listen():
        if message['type'] == 'message':
            try:
                frame_meta = pickle.loads(message['data'])
                frame_count += 1
                
                # Request actual frame (less frequently than detector)
                if frame_count % 2 == 0:  # Write every other frame to reduce load
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
                        
                        # Write frame to chunk
                        writer.write_frame(frame)
                
                # Log progress
                if frame_count % 60 == 0:
                    print(f"Written {frame_count} frames, chunk {writer.chunk_count}")
                    
            except Exception as e:
                print(f"Write error: {e}")

def main():
    print("Starting writer service...")
    
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
    
    # Initialize writer
    writer = ChunkWriter(OUTPUT_DIR, CHUNK_DURATION)
    
    # Set status
    r.set('writer:status', 'ready')
    
    print(f"Writer running, output dir: {OUTPUT_DIR}")
    
    try:
        # Start listening
        listen_for_frames(r, writer)
    finally:
        writer.close()

if __name__ == '__main__':
    main()
