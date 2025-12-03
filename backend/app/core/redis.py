import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

# Redis client for text data (messages, JSON)
redis_client = redis.from_url(settings.redis_url, decode_responses=True)

# Redis client for binary data (snapshots)
redis_binary_client = redis.from_url(settings.redis_url, decode_responses=False)


async def get_redis():
    """Get Redis client for binary data (snapshots, etc)"""
    return redis_binary_client


async def get_redis_text():
    """Get Redis client for text data (messages, JSON)"""
    return redis_client


# Redis channels
CHANNEL_CAMERA_CONTROL = "camera:control"  # Start/stop recording/detection
CHANNEL_MOTION_EVENTS = "motion:events"    # Motion detected events
CHANNEL_NOTIFICATIONS = "notifications"     # Telegram notifications


async def publish_event(channel: str, message: dict):
    """Publish event to Redis channel"""
    import json
    await redis_client.publish(channel, json.dumps(message))


async def add_to_queue(queue_name: str, message: dict):
    """Add message to Redis queue"""
    import json
    await redis_client.rpush(queue_name, json.dumps(message))


async def get_frame(camera_id: int) -> bytes | None:
    """Get latest frame from Redis cache for camera"""
    key = f"camera:{camera_id}:frame"
    frame_data = await redis_binary_client.get(key)
    return frame_data
