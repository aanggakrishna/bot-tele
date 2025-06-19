import asyncio
import time
import os
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel, Message, MessageService
from telethon.tl.functions.channels import GetFullChannelRequest
from loguru import logger
from config import config
from ca_detector import CADetector

class TelegramMonitorBot:
    def __init__(self):
        """Initialize bot"""
        self.client = None
        self.detector = CADetector()
        self.last_heartbeat = time.time()
        self.heartbeat_interval = 60  # Seconds
        self.entity_details = {
            'groups': {},
            'channels': {}
        }
        self.running = False
        self.start_time = datetime.now()
        self.processed_pins = set()
    
    async def init_client(self):
        """Initialize Telegram client"""
        try:
            # Create session directory if it doesn't exist
            os.makedirs('sessions', exist_ok=True)
            
            # Initialize client
            self.client = TelegramClient('sessions/monitor_session', config.API_ID, config.API_HASH)
            await self.client.start()
            
            # Load entity details
            await self.load_entity_details()
            
            logger.success("✅ Telegram client initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize client: {e}")
            return False
    
    async def load_entity_details(self):
        """Load entity details (names, etc.)"""
        try:
            # Load from config if available
            self.entity_details = config.get_entity_details()
            
            # Update with fresh data
            for group_id in config.MONITOR_GROUPS:
                try:
                    group = await self.client.get_entity(group_id)
                    self.entity_details['groups'][str(group_id)] = getattr(group, 'title', f"Group {group_id}")
                    logger.info(f"✅ Loaded group: {self.entity_details['groups'][str(group_id)]} ({group_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load group {group_id}: {e}")
            
            for channel_id in config.MONITOR_CHANNELS:
                try:
                    channel = await self.client.get_entity(channel_id)
                    self.entity_details['channels'][str(channel_id)] = getattr(channel, 'title', f"Channel {channel_id}")
                    logger.info(f"✅ Loaded channel: {self.entity_details['channels'][str(channel_id)]} ({channel_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load channel {channel_id}: {e}")
            
            # Save updated details
            config.save_entity_details(self.entity_details)
            
        except Exception as e:
            logger.error(f"❌ Error loading entity details: {e}")
            # Initialize with default values if failed
            self.entity_details = {
                'groups': {str(id): f"Group {id}" for id in config.MONITOR_GROUPS},
                'channels': {str(id): f"Channel {id}" for id in config.MONITOR_CHANNELS}
            }
    
    async def send_notification(self, ca_data, source_info, message_text):
        """Send notification to owner and configured user"""
        try:
            # Get CA data
            platform = ca_data['platform'].upper()
            address = ca_data['address']
            
            # Create detailed message for owner and saved messages
            detailed_message = f"🚨 **{platform} CA DETECTED!**\n\n"
            detailed_message += f"🔗 `{address}`\n\n"
            detailed_message += f"📊 **Source:** {source_info}\n"
            detailed_message += f"🕒 **Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            
            # Add snippet of original message (truncate if too long)
            snippet = message_text.strip()
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
            detailed_message += f"📝 **Message:**\n{snippet}"
            
            # Send detailed message to owner
            await self.client.send_message(config.OWNER_ID, detailed_message)
            
            # Send only CA to configured user (TO_USER_ID) if different from owner
            if config.TO_USER_ID and config.TO_USER_ID != config.OWNER_ID:
                try:
                    # Simple message with just the CA
                    simple_message = f"{address}"
                    await self.client.send_message(config.TO_USER_ID, simple_message)
                    logger.info(f"📨 CA only sent to TO_USER_ID: {config.TO_USER_ID}")
                except Exception as e:
                    logger.error(f"❌ Failed to send to TO_USER_ID: {e}")
            
            # Save detailed message to "Saved Messages"
            await self.client.send_message('me', detailed_message)
            
            logger.info(f"📨 Notification sent for {platform} CA: {address[:8]}...")
            
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def handle_new_channel_message(self, event):
        """Handle new message in monitored channel"""
        try:
            # Check if message is valid
            if not event.message or not isinstance(event.message, Message):
                return
            
            # Get channel details
            channel_id = str(event.chat_id)
            channel_name = self.entity_details['channels'].get(channel_id, f"Channel {channel_id}")
            
            # Extract message text
            message_text = event.message.text or event.message.message or ""
            if not message_text:
                if event.message.caption:
                    message_text = event.message.caption
            
            # Skip empty messages
            if not message_text:
                return
            
            # Log for heartbeat
            logger.debug(f"📝 New message in {channel_name} ({channel_id})")
            
            # Process message to detect CAs
            source_info = f"{channel_name} (Channel)"
            ca_results = self.detector.process_message(message_text, source_info)
            
            # Send notifications for each CA
            for ca_data in ca_results:
                await self.send_notification(ca_data, source_info, message_text)
            
        except Exception as e:
            logger.error(f"❌ Error handling channel message: {e}")
    
    async def handle_pinned_message(self, event):
        """Handle pinned message in monitored group"""
        try:
            # Check if message is valid
            if not event.message:
                return
            
            message = event.message
            
            # Get group details
            group_id = str(event.chat_id)
            group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
            
            # Extract message text
            message_text = message.text or message.message or ""
            if not message_text and message.caption:
                message_text = message.caption
                
            # Skip empty messages
            if not message_text:
                return
            
            logger.info(f"📌 Pinned message in {group_name} ({group_id})")
            
            # Process message to detect CAs
            source_info = f"{group_name} (Pinned)"
            ca_results = self.detector.process_message(message_text, source_info)
            
            # Send notifications for each CA
            for ca_data in ca_results:
                await self.send_notification(ca_data, source_info, message_text)
            
        except Exception as e:
            logger.error(f"❌ Error handling pinned message: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def heartbeat(self):
        """Send heartbeat to terminal"""
        while self.running:
            try:
                current_time = time.time()
                
                # Only heartbeat at interval
                if current_time - self.last_heartbeat >= self.heartbeat_interval:
                    self.last_heartbeat = current_time
                    
                    # Calculate uptime
                    uptime = datetime.now() - self.start_time
                    hours, remainder = divmod(uptime.total_seconds(), 3600)
                    minutes, seconds = divmod(remainder, 60)
                    
                    logger.info(f"❤️ HEARTBEAT - Bot running - Uptime: {int(hours)}h {int(minutes)}m {int(seconds)}s")
                    logger.info(f"📊 Stats: {self.detector.stats['messages_processed']} messages processed, "
                               f"{self.detector.stats['addresses_found']} addresses found")
                    
                    detected = (
                        f"PumpFun: {self.detector.stats['pumpfun_detected']}, "
                        f"Moonshot: {self.detector.stats['moonshot_detected']}, "
                        f"Native: {self.detector.stats['native_detected']}"
                    )
                    logger.info(f"🔍 Detected: {detected}")
                    
                # Sleep to avoid high CPU usage
                await asyncio.sleep(5)
                
            except Exception as e:
                logger.error(f"❌ Heartbeat error: {e}")
                await asyncio.sleep(10)
    
    async def setup_handlers(self):
        """Setup event handlers"""
        try:
            # Monitor new messages in channels
            @self.client.on(events.NewMessage(chats=config.MONITOR_CHANNELS))
            async def channel_handler(event):
                await self.handle_new_channel_message(event)
            
            # Method 1: Watch for pin notifications using ChatAction
            # Note: Requires recent Telethon version
            try:
                @self.client.on(events.ChatAction(chats=config.MONITOR_GROUPS))
                async def action_handler(event):
                    if hasattr(event, 'action') and hasattr(event.action, 'message'):
                        # This is likely a pin event
                        try:
                            pinned_msg_id = event.action.message.id
                            pinned_msg = await self.client.get_messages(event.chat_id, ids=pinned_msg_id)
                            if pinned_msg:
                                await self.handle_pinned_message_by_id(event.chat_id, pinned_msg)
                        except Exception as e:
                            logger.error(f"❌ Error in action handler: {e}")
            except Exception as e:
                logger.warning(f"⚠️ ChatAction handler setup failed: {e}")
            
            # Method 2: Check message pinned status in new & edited messages
            @self.client.on(events.NewMessage(chats=config.MONITOR_GROUPS))
            async def new_message_handler(event):
                if hasattr(event.message, 'pinned') and event.message.pinned:
                    await self.handle_pinned_message(event)
            
            @self.client.on(events.MessageEdited(chats=config.MONITOR_GROUPS))
            async def edit_handler(event):
                if hasattr(event.message, 'pinned') and event.message.pinned:
                    await self.handle_pinned_message(event)
            
            # Method 3: Periodically check pinned messages
            self.check_pins_task = asyncio.create_task(self.periodic_pin_check())
            
            logger.success("✅ Event handlers registered")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup handlers: {e}")

# Add new method for periodic pin checking
async def periodic_pin_check(self):
    """Periodically check pinned messages in all monitored groups"""
    while self.running:
        try:
            for group_id in config.MONITOR_GROUPS:
                try:
                    # Get the chat
                    chat = await self.client.get_entity(group_id)
                    
                    # Get full chat to access pinned message
                    full_chat = await self.client(GetFullChannelRequest(channel=chat))
                    
                    # Check if there is a pinned message
                    if hasattr(full_chat, 'full_chat') and full_chat.full_chat.pinned_msg_id:
                        pinned_id = full_chat.full_chat.pinned_msg_id
                        pinned_msg = await self.client.get_messages(group_id, ids=pinned_id)
                        if pinned_msg:
                            await self.handle_pinned_message_by_id(group_id, pinned_msg)
                except Exception as e:
                    logger.debug(f"⚠️ Error checking pins in {group_id}: {e}")
            
            # Wait before next check
            await asyncio.sleep(300)  # Check every 5 minutes
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"❌ Error in periodic pin check: {e}")
            await asyncio.sleep(60)

# Add helper method to handle pinned messages by ID
async def handle_pinned_message_by_id(self, chat_id, message):
    """Handle pinned message using direct message object"""
    try:
        # Skip if already processed (add message ID tracking)
        message_id = message.id
        if message_id in self.processed_pins:
            return
            
        # Mark as processed
        self.processed_pins.add(message_id)
        
        # Get group details
        group_id = str(chat_id)
        group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
        
        # Extract message text
        message_text = message.text or message.message or ""
        if not message_text and message.caption:
            message_text = message.caption
            
        # Skip empty messages
        if not message_text:
            return
        
        logger.info(f"📌 Pinned message in {group_name} ({group_id})")
        
        # Process message to detect CAs
        source_info = f"{group_name} (Pinned)"
        ca_results = self.detector.process_message(message_text, source_info)
        
        # Send notifications for each CA
        for ca_data in ca_results:
            await self.send_notification(ca_data, source_info, message_text)
        
    except Exception as e:
        logger.error(f"❌ Error handling pinned message by ID: {e}")
    
    async def start_monitoring(self):
        """Start monitoring channels and groups"""
        try:
            # Initialize client
            if not await self.init_client():
                return False
            
            # Setup event handlers
            await self.setup_handlers()
            
            # Initialize entity details
            await self.load_entity_details()
            
            # Log monitored entities
            logger.info(f"👥 Monitoring {len(config.MONITOR_GROUPS)} groups for pinned messages")
            logger.info(f"📢 Monitoring {len(config.MONITOR_CHANNELS)} channels for new messages")
            
            # Set running flag for heartbeat
            self.running = True
            self.start_time = datetime.now()
            
            # Start heartbeat in background
            asyncio.create_task(self.heartbeat())
            
            # Notify owner
            try:
                await self.client.send_message(config.OWNER_ID, "🚀 Solana CA Monitor Bot has started!")
                await self.client.send_message('me', "🚀 Solana CA Monitor Bot has started!")
            except:
                logger.warning("⚠️ Could not send startup notification")
            
            logger.success("✅ Bot started successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting bot: {e}")
            return False
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        try:
            self.running = False
            
            # Notify owner
            try:
                await self.client.send_message(config.OWNER_ID, "🛑 Solana CA Monitor Bot has stopped!")
                await self.client.send_message('me', "🛑 Solana CA Monitor Bot has stopped!")
            except:
                pass
            
            # Disconnect client
            if self.client:
                await self.client.disconnect()
                
            logger.info("🛑 Bot stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping bot: {e}")
    
    async def run(self):
        """Run the bot"""
        try:
            # Start monitoring
            if not await self.start_monitoring():
                return
            
            # Keep bot running
            logger.info("🔄 Bot is running... Press Ctrl+C to stop")
            
            # Run forever
            while self.running:
                await asyncio.sleep(1)
                
        except KeyboardInterrupt:
            logger.info("🛑 Received stop signal")
            
        except Exception as e:
            logger.error(f"❌ Runtime error: {e}")
            
        finally:
            # Clean shutdown
            await self.stop_monitoring()

# For direct execution
async def main():
    """Main entry point"""
    logger.info("🚀 Starting Solana CA Monitor Bot")
    
    # Check if bot is enabled
    if not config.BOT_ENABLED:
        logger.warning("⚠️ Bot is disabled in config. Set BOT_ENABLED=true to enable.")
        return
    
    # Create and run bot
    bot = TelegramMonitorBot()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())