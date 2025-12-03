import asyncio
import json
import logging
import os
import signal
from datetime import datetime
from typing import Dict, Optional

import httpx
import redis.asyncio as redis
from telegram import Bot
from telegram.error import TelegramError

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration from environment
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STORAGE_PATH = os.environ.get("STORAGE_PATH", "/recordings")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")

# Redis channels
CHANNEL_NOTIFICATIONS = "notifications"

shutdown_event = asyncio.Event()

# Track last notification time per camera for cooldown
last_notification_time: Dict[int, datetime] = {}


class TelegramNotifier:
    """Handles Telegram notifications for motion events"""
    
    def __init__(self):
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.bot = None
        self.enabled = bool(self.bot_token and self.chat_id)
        self.send_snapshots = True
        self.cooldown = 60  # Default cooldown in seconds
        
        if self.enabled:
            self.bot = Bot(token=self.bot_token)
            logger.info("Telegram notifier initialized")
        else:
            logger.warning("Telegram not configured - notifications disabled")
    
    async def update_settings(self):
        """Fetch settings from backend database"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{BACKEND_URL}/api/settings/all", timeout=5)
                if response.status_code == 200:
                    settings = response.json()
                    
                    # Update bot token and chat ID if set in database
                    new_token = settings.get("telegram_bot_token", "")
                    new_chat = settings.get("telegram_chat_id", "")
                    
                    # Only use database values if they contain actual data (not masked)
                    if new_token and "..." not in new_token:
                        self.bot_token = new_token
                    if new_chat and new_chat != self.chat_id:
                        self.chat_id = new_chat
                    
                    # Update other settings
                    self.enabled = settings.get("telegram_enabled", False)
                    self.send_snapshots = settings.get("telegram_send_snapshots", True)
                    self.cooldown = settings.get("notification_cooldown", 60)
                    
                    if self.enabled and self.bot_token:
                        self.bot = Bot(token=self.bot_token)
                    
                    logger.info(f"Settings updated: enabled={self.enabled}, send_snapshots={self.send_snapshots}, cooldown={self.cooldown}")
        except Exception as e:
            logger.warning(f"Failed to fetch settings from backend: {e}")
    
    def can_send_notification(self, camera_id: int, camera_cooldown: Optional[int] = None) -> bool:
        """Check if we can send a notification (respecting cooldown)"""
        now = datetime.now()
        last_time = last_notification_time.get(camera_id)
        
        cooldown = camera_cooldown if camera_cooldown is not None else self.cooldown
        
        if last_time is None:
            return True
        
        elapsed = (now - last_time).total_seconds()
        return elapsed >= cooldown
    
    async def send_motion_alert(
        self,
        camera_id: int,
        camera_name: str,
        timestamp: str,
        confidence: float,
        snapshot_path: str = None,
        camera_cooldown: int = None
    ):
        """Send motion detection alert to Telegram"""
        if not self.enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False
        
        if not self.can_send_notification(camera_id, camera_cooldown):
            logger.debug(f"Notification cooldown active for camera {camera_id}")
            return False
        
        try:
            # Format message in English
            message = (
                f"🚨 *Motion Detected!*\n\n"
                f"📷 Camera: {camera_name} (ID: {camera_id})\n"
                f"⏰ Time: {timestamp}\n"
                f"📊 Confidence: {confidence:.1f}%"
            )
            
            # Send with photo if available and enabled
            if self.send_snapshots and snapshot_path and os.path.exists(snapshot_path):
                with open(snapshot_path, 'rb') as photo:
                    await self.bot.send_photo(
                        chat_id=self.chat_id,
                        photo=photo,
                        caption=message,
                        parse_mode='Markdown'
                    )
            else:
                await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )
            
            # Update last notification time
            last_notification_time[camera_id] = datetime.now()
            
            logger.info(f"Notification sent for camera {camera_id}")
            return True
            
        except TelegramError as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False
    
    async def send_system_alert(self, title: str, message: str):
        """Send system alert to Telegram"""
        if not self.enabled:
            return False
        
        try:
            text = f"⚙️ *{title}*\n\n{message}"
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode='Markdown'
            )
            return True
        except TelegramError as e:
            logger.error(f"Failed to send system alert: {e}")
            return False


async def get_camera_info(camera_id: int) -> dict:
    """Fetch camera info from backend"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{BACKEND_URL}/api/cameras/{camera_id}", timeout=5)
            if response.status_code == 200:
                return response.json()
        except Exception as e:
            logger.warning(f"Failed to fetch camera info: {e}")
    return {"name": f"Camera {camera_id}", "notification_cooldown": None}


async def subscribe_to_notifications(notifier: TelegramNotifier):
    """Subscribe to Redis notifications channel"""
    redis_client = redis.from_url(REDIS_URL)
    pubsub = redis_client.pubsub()
    
    await pubsub.subscribe(CHANNEL_NOTIFICATIONS)
    logger.info(f"Subscribed to {CHANNEL_NOTIFICATIONS}")
    
    try:
        while not shutdown_event.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            
            if message and message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await handle_notification(notifier, data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON in notification: {message['data']}")
            
            await asyncio.sleep(0.1)
    finally:
        await pubsub.unsubscribe(CHANNEL_NOTIFICATIONS)
        await redis_client.close()


async def settings_refresh_task(notifier: TelegramNotifier):
    """Periodically refresh settings from database"""
    while not shutdown_event.is_set():
        await notifier.update_settings()
        # Refresh every 60 seconds
        for _ in range(60):
            if shutdown_event.is_set():
                break
            await asyncio.sleep(1)


async def handle_notification(notifier: TelegramNotifier, data: dict):
    """Handle incoming notification event"""
    event_type = data.get("type", "motion")
    
    if event_type == "motion" or "camera_id" in data:
        # Motion detection event
        camera_id = data.get("camera_id")
        camera_info = await get_camera_info(camera_id)
        camera_name = camera_info.get("name", f"Camera {camera_id}")
        camera_cooldown = camera_info.get("notification_cooldown")
        
        timestamp = data.get("timestamp", datetime.now().isoformat())
        confidence = data.get("confidence", 0)
        snapshot_path = data.get("snapshot_path")
        
        # Format timestamp for display
        try:
            dt = datetime.fromisoformat(timestamp)
            display_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            display_time = timestamp
        
        await notifier.send_motion_alert(
            camera_id=camera_id,
            camera_name=camera_name,
            timestamp=display_time,
            confidence=confidence,
            snapshot_path=snapshot_path,
            camera_cooldown=camera_cooldown
        )
    
    elif event_type == "system":
        # System event
        title = data.get("title", "System Alert")
        message = data.get("message", "")
        await notifier.send_system_alert(title, message)


async def main():
    """Main entry point"""
    logger.info("Starting Motion Watch Notifier Service")
    
    # Initialize Telegram notifier
    notifier = TelegramNotifier()
    
    # Fetch initial settings
    await notifier.update_settings()
    
    # Send startup notification
    if notifier.enabled:
        await notifier.send_system_alert(
            "Motion Watch Started",
            "Video surveillance system started and ready."
        )
    
    # Start tasks
    tasks = [
        asyncio.create_task(subscribe_to_notifications(notifier)),
        asyncio.create_task(settings_refresh_task(notifier)),
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
        # Cancel tasks
        for task in tasks:
            task.cancel()
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Send shutdown notification
        if notifier.enabled:
            await notifier.send_system_alert(
                "Motion Watch Stopped",
                "Video surveillance system stopped."
            )
    
    logger.info("Notifier service stopped")


if __name__ == "__main__":
    asyncio.run(main())
