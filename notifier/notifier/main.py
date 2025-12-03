import asyncio
import json
import logging
import os
import signal
from datetime import datetime

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

# Redis channels
CHANNEL_NOTIFICATIONS = "notifications"

shutdown_event = asyncio.Event()


class TelegramNotifier:
    """Handles Telegram notifications for motion events"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.bot = None
        self.enabled = bool(bot_token and chat_id)
        
        if self.enabled:
            self.bot = Bot(token=bot_token)
            logger.info("Telegram notifier initialized")
        else:
            logger.warning("Telegram not configured - notifications disabled")
    
    async def send_motion_alert(
        self,
        camera_id: int,
        camera_name: str,
        timestamp: str,
        confidence: float,
        snapshot_path: str = None
    ):
        """Send motion detection alert to Telegram"""
        if not self.enabled:
            logger.debug("Telegram not enabled, skipping notification")
            return False
        
        try:
            # Format message
            message = (
                f"🚨 *Обнаружено движение!*\n\n"
                f"📷 Камера: {camera_name} (ID: {camera_id})\n"
                f"⏰ Время: {timestamp}\n"
                f"📊 Уверенность: {confidence:.1f}%"
            )
            
            # Send with photo if available
            if snapshot_path and os.path.exists(snapshot_path):
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


async def get_camera_name(camera_id: int) -> str:
    """Fetch camera name from backend"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"http://backend:8000/api/cameras/{camera_id}")
            if response.status_code == 200:
                return response.json().get("name", f"Camera {camera_id}")
        except Exception:
            pass
    return f"Camera {camera_id}"


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


async def handle_notification(notifier: TelegramNotifier, data: dict):
    """Handle incoming notification event"""
    event_type = data.get("type", "motion")
    
    if event_type == "motion" or "camera_id" in data:
        # Motion detection event
        camera_id = data.get("camera_id")
        camera_name = await get_camera_name(camera_id)
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
            snapshot_path=snapshot_path
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
    notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
    
    # Send startup notification
    if notifier.enabled:
        await notifier.send_system_alert(
            "Motion Watch Started",
            "Система видеонаблюдения запущена и готова к работе."
        )
    
    # Start tasks
    tasks = [
        asyncio.create_task(subscribe_to_notifications(notifier)),
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
                "Система видеонаблюдения остановлена."
            )
    
    logger.info("Notifier service stopped")


if __name__ == "__main__":
    asyncio.run(main())
