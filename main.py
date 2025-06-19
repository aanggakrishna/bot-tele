import os
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import MessageService
from loguru import logger

# Load environment variables
load_dotenv()

# Configuration
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))
MONITOR_GROUPS = [int(x.strip()) for x in os.getenv("MONITOR_GROUPS", "").split(",") if x.strip()]
MONITOR_CHANNELS = [int(x.strip()) for x in os.getenv("MONITOR_CHANNELS", "").split(",") if x.strip()]

# Initialize Telegram client
client = TelegramClient("bot_session", API_ID, API_HASH)

# Function to process pinned messages
async def process_pinned_message(message, group_id, group_name):
    """Process a pinned message"""
    try:
        message_text = message.text or message.message or ""
        if not message_text and message.caption:
            message_text = message.caption

        if not message_text:
            logger.info(f"📌 Pinned message in {group_name} ({group_id}) is empty, skipping...")
            return

        logger.info(f"📌 Pinned message detected in {group_name} ({group_id}): {message_text[:50]}...")
        # Add your custom logic here (e.g., detect specific patterns, notify, etc.)
    except Exception as e:
        logger.error(f"❌ Error processing pinned message in {group_name}: {e}")

# Function to process new messages
async def process_new_message(message, source_name, source_id):
    """Process a new message"""
    try:
        message_text = message.text or message.message or ""
        if not message_text and message.caption:
            message_text = message.caption

        if not message_text:
            logger.info(f"📝 New message in {source_name} ({source_id}) is empty, skipping...")
            return

        logger.info(f"📝 New message in {source_name} ({source_id}): {message_text[:50]}...")
        # Add your custom logic here (e.g., detect specific patterns, notify, etc.)
    except Exception as e:
        logger.error(f"❌ Error processing new message in {source_name}: {e}")

# Event handler for new messages in monitored groups
@client.on(events.NewMessage(chats=MONITOR_GROUPS))
async def group_message_handler(event):
    """Handle new messages in monitored groups"""
    try:
        group_id = event.chat_id
        group_name = f"Group {group_id}"

        # Check if the message is a service message (e.g., pin action)
        if isinstance(event.message, MessageService) and hasattr(event.message.action, "message"):
            logger.info(f"🔧 Service message detected in {group_name} ({group_id})")
            pinned_msg_id = event.message.action.message.id
            pinned_msg = await client.get_messages(group_id, ids=pinned_msg_id)
            if pinned_msg:
                await process_pinned_message(pinned_msg, group_id, group_name)
        else:
            # Check if the message is pinned
            if hasattr(event.message, "pinned") and event.message.pinned:
                logger.info(f"📌 Pinned message detected in {group_name} ({group_id})")
                await process_pinned_message(event.message, group_id, group_name)
    except Exception as e:
        logger.error(f"❌ Error in group message handler: {e}")

# Event handler for new messages in monitored channels
@client.on(events.NewMessage(chats=MONITOR_CHANNELS))
async def channel_message_handler(event):
    """Handle new messages in monitored channels"""
    try:
        channel_id = event.chat_id
        channel_name = f"Channel {channel_id}"
        await process_new_message(event.message, channel_name, channel_id)
    except Exception as e:
        logger.error(f"❌ Error in channel message handler: {e}")

# Periodic task to check pinned messages in groups
async def periodic_pin_check():
    """Check pinned messages in monitored groups periodically"""
    while True:
        try:
            for group_id in MONITOR_GROUPS:
                group_name = f"Group {group_id}"
                logger.info(f"🔍 Checking pinned messages in {group_name} ({group_id})...")
                try:
                    # Get the full chat to access pinned message ID
                    full_chat = await client.get_entity(group_id)
                    if hasattr(full_chat, "pinned_msg_id") and full_chat.pinned_msg_id:
                        pinned_msg_id = full_chat.pinned_msg_id
                        pinned_msg = await client.get_messages(group_id, ids=pinned_msg_id)
                        if pinned_msg:
                            await process_pinned_message(pinned_msg, group_id, group_name)
                except Exception as e:
                    logger.warning(f"⚠️ Could not check pinned messages in {group_name}: {e}")
            await asyncio.sleep(30)  # Check every 30 seconds
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Error in periodic pin check: {e}")
            await asyncio.sleep(60)

# Main function
async def main():
    """Main entry point"""
    logger.info("🚀 Starting Telegram Monitor Bot...")
    await client.start()
    logger.success("✅ Telegram client started successfully")

    # Start periodic pin check
    asyncio.create_task(periodic_pin_check())

    # Keep the bot running
    logger.info("🔄 Bot is running... Press Ctrl+C to stop")
    await client.run_until_disconnected()

# Run the bot
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")