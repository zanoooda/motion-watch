import redis.asyncio as redis
from app.core.config import get_settings

settings = get_settings()

redis_client = redis.from_url(settings.redis_url, decode_responses=True)


async def get_redis():
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
