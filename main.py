import asyncio
import time
import os
import json
import re
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel, Message, MessageService
from telethon.tl.functions.channels import GetFullChannelRequest

# Load environment variables
load_dotenv()

# Configuration
class Config:
    # Telegram Configuration
    API_ID = int(os.getenv('API_ID'))
    API_HASH = os.getenv('API_HASH')
    OWNER_ID = int(os.getenv('OWNER_ID'))
    TO_USER_ID = int(os.getenv('TO_USER_ID', '0'))
    
    # Monitor Groups and Channels
    MONITOR_GROUPS = [int(x.strip()) for x in os.getenv('MONITOR_GROUPS', '').split(',') if x.strip()]
    MONITOR_CHANNELS = [int(x.strip()) for x in os.getenv('MONITOR_CHANNELS', '').split(',') if x.strip()]
    
    # Bot Configuration
    BOT_ENABLED = os.getenv('BOT_ENABLED', 'true').lower() == 'true'
    
    # Platform Enables
    ENABLE_PUMPFUN = os.getenv('ENABLE_PUMPFUN', 'true').lower() == 'true'
    ENABLE_MOONSHOT = os.getenv('ENABLE_MOONSHOT', 'true').lower() == 'true'
    ENABLE_NATIVE = os.getenv('ENABLE_NATIVE', 'true').lower() == 'true'

config = Config()

# CA Detector Class
class CADetector:
    """Solana Contract Address (CA) detector"""
    
    # Regular expression patterns
    SOLANA_ADDRESS_PATTERN = r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b'
    
    # Known domains for platforms
    PUMPFUN_DOMAINS = ['pumpfun.io', 'pumpfun.fun', 'pump.fun']
    MOONSHOT_DOMAINS = ['moonshot.watch', 'moonshotwatch.io']
    
    def __init__(self):
        """Initialize CA detector"""
        self.patterns = {
            'solana': re.compile(self.SOLANA_ADDRESS_PATTERN)
        }
        
        # Stats
        self.stats = {
            'messages_processed': 0,
            'addresses_found': 0,
            'pumpfun_detected': 0,
            'moonshot_detected': 0, 
            'native_detected': 0
        }
    
    def detect_addresses(self, text):
        """Detect Solana addresses in text"""
        if not text:
            return []
        
        # Find all potential addresses
        addresses = self.patterns['solana'].findall(text)
        
        # Filter valid addresses (base58 check)
        valid_addresses = []
        for addr in addresses:
            # Simple validation: most Solana addresses are 32-44 chars, base58
            if 32 <= len(addr) <= 44 and self._is_base58(addr):
                valid_addresses.append(addr)
        
        self.stats['addresses_found'] += len(valid_addresses)
        return valid_addresses
    
    def _is_base58(self, value):
        """Check if a string is base58 encoded"""
        try:
            # Base58 allowed chars
            return all(c in '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz' for c in value)
        except:
            return False
    
    def detect_platform(self, text, addresses):
        """Detect which platform the CA belongs to"""
        if not addresses:
            return []
        
        results = []
        
        # Process each address
        for address in addresses:
            # Default platform is "native" Solana
            platform = "native"
            confidence = 0.5  # Default confidence
            
            # Check for PumpFun indicators
            if config.ENABLE_PUMPFUN and self._is_pumpfun(text, address):
                platform = "pumpfun"
                confidence = 0.8
                self.stats['pumpfun_detected'] += 1
            
            # Check for Moonshot indicators
            elif config.ENABLE_MOONSHOT and self._is_moonshot(text, address):
                platform = "moonshot"
                confidence = 0.8
                self.stats['moonshot_detected'] += 1
            
            # Only count native if enabled
            elif config.ENABLE_NATIVE:
                self.stats['native_detected'] += 1
            else:
                continue  # Skip this address if native detection disabled
            
            results.append({
                'address': address,
                'platform': platform,
                'confidence': confidence
            })
        
        return results
    
    def _is_pumpfun(self, text, address):
        """Check if the address is from PumpFun"""
        # Check for PumpFun domains
        for domain in self.PUMPFUN_DOMAINS:
            if domain.lower() in text.lower():
                return True
                
        # Check for PumpFun keywords
        pumpfun_keywords = ['pumpfun', 'pump.fun', 'pump fun', 'buy on pf', 'listed on pf', 'pump', 'pf']
        for keyword in pumpfun_keywords:
            if keyword.lower() in text.lower():
                return True
        
        return False
    
    def _is_moonshot(self, text, address):
        """Check if the address is from Moonshot"""
        # Check for Moonshot domains
        for domain in self.MOONSHOT_DOMAINS:
            if domain.lower() in text.lower():
                return True
                
        # Check for Moonshot keywords
        moonshot_keywords = ['moonshot', 'moon shot', 'moonshotwatch', 'moonshot watch']
        for keyword in moonshot_keywords:
            if keyword.lower() in text.lower():
                return True
        
        return False
    
    def process_message(self, text, source=None):
        """Process message to detect CAs and platform"""
        if not text:
            return []
        
        self.stats['messages_processed'] += 1
        
        # Detect addresses
        addresses = self.detect_addresses(text)
        if not addresses:
            return []
        
        # Detect platform for each address
        results = self.detect_platform(text, addresses)
        
        # Log results
        if results:
            logger.info(f"📊 Found {len(results)} Solana addresses from {source or 'unknown'}")
            for ca in results:
                logger.debug(f"🔍 {ca['platform']} CA: {ca['address']}")
        
        return results

# Telegram Monitor Bot Class
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
            # Initialize with default values
            self.entity_details = {
                'groups': {str(id): f"Group {id}" for id in config.MONITOR_GROUPS},
                'channels': {str(id): f"Channel {id}" for id in config.MONITOR_CHANNELS}
            }
            
            # Update with fresh data and test permissions
            for group_id in config.MONITOR_GROUPS:
                try:
                    logger.info(f"🔍 Loading group {group_id}...")
                    group = await self.client.get_entity(group_id)
                    self.entity_details['groups'][str(group_id)] = getattr(group, 'title', f"Group {group_id}")
                    
                    # Test if we can read messages
                    try:
                        test_messages = await self.client.get_messages(group_id, limit=1)
                        logger.success(f"✅ Group: {self.entity_details['groups'][str(group_id)]} ({group_id}) - Can read messages")
                    except Exception as perm_e:
                        logger.error(f"❌ Group {group_id} - Cannot read messages: {perm_e}")
                        
                    # Check group type
                    logger.info(f"   Group type: {type(group).__name__}")
                    logger.info(f"   Group attributes: {[attr for attr in dir(group) if not attr.startswith('_')]}")
                    
                except Exception as e:
                    logger.error(f"❌ Could not load group {group_id}: {e}")
            
            for channel_id in config.MONITOR_CHANNELS:
                try:
                    channel = await self.client.get_entity(channel_id)
                    self.entity_details['channels'][str(channel_id)] = getattr(channel, 'title', f"Channel {channel_id}")
                    logger.info(f"✅ Loaded channel: {self.entity_details['channels'][str(channel_id)]} ({channel_id})")
                except Exception as e:
                    logger.warning(f"⚠️ Could not load channel {channel_id}: {e}")
            
        except Exception as e:
            logger.error(f"❌ Error loading entity details: {e}")
    
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
            try:
                await self.client.send_message(config.OWNER_ID, detailed_message)
                logger.info(f"📨 Detailed notification sent to OWNER_ID: {config.OWNER_ID}")
            except Exception as e:
                logger.error(f"❌ Failed to send to OWNER_ID: {e}")
            
            # Send only CA to configured user (TO_USER_ID) if different from owner
            if config.TO_USER_ID and config.TO_USER_ID != config.OWNER_ID:
                try:
                    # Try to get the entity first to ensure it exists
                    try:
                        user_entity = await self.client.get_entity(config.TO_USER_ID)
                        logger.debug(f"✅ Found TO_USER_ID entity: {getattr(user_entity, 'username', 'No username')}")
                    except Exception as entity_error:
                        logger.warning(f"⚠️ Cannot find TO_USER_ID entity: {entity_error}")
                        logger.info(f"💡 TO_USER_ID {config.TO_USER_ID} needs to start a conversation with the bot first")
                        # Skip sending to TO_USER_ID but continue with other notifications
                        raise entity_error
                    
                    # Simple message with just the CA
                    simple_message = f"{address}"
                    await self.client.send_message(config.TO_USER_ID, simple_message)
                    logger.info(f"📨 CA only sent to TO_USER_ID: {config.TO_USER_ID}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to send to TO_USER_ID: {e}")
                    logger.info(f"💡 Tip: User {config.TO_USER_ID} should send a message to the bot account first")
            
            # Save detailed message to "Saved Messages"
            try:
                await self.client.send_message('me', detailed_message)
                logger.info("📨 Notification saved to Saved Messages")
            except Exception as e:
                logger.error(f"❌ Failed to save to Saved Messages: {e}")
            
            logger.success(f"✅ Notification sent for {platform} CA: {address[:8]}...")
            
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
            
            # Get group details
            group_id = str(event.chat_id)
            group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
            
            await self.process_pinned_message(event.message, group_id, group_name)
            
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
            if config.MONITOR_CHANNELS:
                @self.client.on(events.NewMessage(chats=config.MONITOR_CHANNELS))
                async def channel_handler(event):
                    await self.handle_new_channel_message(event)
                logger.info(f"✅ Channel handler registered for {len(config.MONITOR_CHANNELS)} channels")
            
            # Monitor ALL messages in groups dengan logging detail
            if config.MONITOR_GROUPS:
                @self.client.on(events.NewMessage(chats=config.MONITOR_GROUPS))
                async def group_message_handler(event):
                    try:
                        # LOG SETIAP MESSAGE YANG MASUK
                        group_id = str(event.chat_id)
                        group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
                        
                        logger.info(f"🔔 NEW MESSAGE in {group_name} ({group_id})")
                        logger.info(f"   Message Type: {type(event.message).__name__}")
                        logger.info(f"   Message ID: {event.message.id if event.message else 'None'}")
                        
                        if event.message:
                            logger.info(f"   Has pinned attr: {hasattr(event.message, 'pinned')}")
                            if hasattr(event.message, 'pinned'):
                                logger.info(f"   Is pinned: {event.message.pinned}")
                            
                            # Log message text preview
                            text = event.message.text or event.message.message or ""
                            if not text and event.message.caption:
                                text = event.message.caption
                            logger.info(f"   Text preview: {text[:50]}...")
                        
                        # Check if this is a service message
                        if isinstance(event.message, MessageService):
                            logger.info(f"🔧 SERVICE MESSAGE: {type(event.message.action).__name__}")
                            await self.handle_service_message(event)
                        else:
                            # Check if regular message is pinned
                            if hasattr(event.message, 'pinned') and event.message.pinned:
                                logger.info("📌 PINNED MESSAGE DETECTED!")
                                await self.handle_pinned_message(event)
                            
                            # Check all messages for CAs
                            await self.check_message_for_ca(event)
                            
                    except Exception as e:
                        logger.error(f"❌ Error in group message handler: {e}")
                        import traceback
                        logger.error(f"Traceback: {traceback.format_exc()}")
                
                # Monitor message edits
                @self.client.on(events.MessageEdited(chats=config.MONITOR_GROUPS))
                async def edit_handler(event):
                    try:
                        group_id = str(event.chat_id)
                        group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
                        
                        logger.info(f"✏️ MESSAGE EDITED in {group_name} ({group_id})")
                        
                        if hasattr(event.message, 'pinned') and event.message.pinned:
                            logger.info("📌 EDITED MESSAGE IS PINNED!")
                            await self.handle_pinned_message(event)
                    except Exception as e:
                        logger.error(f"❌ Error in edit handler: {e}")
                
                logger.info(f"✅ Group handlers registered for {len(config.MONITOR_GROUPS)} groups")
            
            logger.success("✅ All event handlers registered")
            
        except Exception as e:
            logger.error(f"❌ Failed to setup handlers: {e}")
    # Tambahkan method untuk test CA detection secara manual
    async def test_ca_detection(self):
        """Test CA detection with the specific message"""
        test_messages = [
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN dasdhasjdasd dasdhasjd adjadasd",
            "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
            "Test: JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN with extra text"
        ]
        
        logger.info("🧪 Testing CA detection...")
        
        for i, test_text in enumerate(test_messages, 1):
            logger.info(f"Test {i}: {test_text}")
            ca_results = self.detector.process_message(test_text, f"Test {i}")
            
            if ca_results:
                logger.success(f"✅ Test {i} successful! Found {len(ca_results)} CAs:")
                for ca in ca_results:
                    logger.info(f"   - {ca['platform']}: {ca['address']}")
            else:
                logger.warning(f"❌ Test {i} failed! No CAs detected")
        
        return len(test_messages)
    # Tambahkan method untuk check pinned messages manually
    async def check_current_pins(self):
        """Check current pinned messages in all monitored groups"""
        logger.info("🔍 Checking current pinned messages...")
        
        for group_id in config.MONITOR_GROUPS:
            try:
                group_name = self.entity_details['groups'].get(str(group_id), f"Group {group_id}")
                logger.info(f"Checking pins in {group_name} ({group_id})")
                
                # Method 1: Try to get entity and check for pinned message ID
                try:
                    entity = await self.client.get_entity(group_id)
                    if hasattr(entity, 'pinned_msg_id') and entity.pinned_msg_id:
                        logger.info(f"   Found pinned message ID: {entity.pinned_msg_id}")
                        pinned_msg = await self.client.get_messages(group_id, ids=entity.pinned_msg_id)
                        if pinned_msg:
                            await self.process_pinned_message(pinned_msg, str(group_id), group_name)
                    else:
                        logger.info(f"   No pinned message ID found in entity")
                except Exception as e:
                    logger.debug(f"   Method 1 failed: {e}")
                
                # Method 2: Get recent messages and check for pinned ones
                try:
                    messages = await self.client.get_messages(group_id, limit=50)
                    pinned_found = False
                    
                    for msg in messages:
                        if hasattr(msg, 'pinned') and msg.pinned:
                            logger.info(f"   Found pinned message in recent messages: ID {msg.id}")
                            await self.process_pinned_message(msg, str(group_id), group_name)
                            pinned_found = True
                            break
                    
                    if not pinned_found:
                        logger.info(f"   No pinned messages found in recent 50 messages")
                        
                except Exception as e:
                    logger.debug(f"   Method 2 failed: {e}")
                    
            except Exception as e:
                logger.error(f"❌ Error checking pins for {group_id}: {e}")
    async def handle_service_message(self, event):
        """Handle service messages (like pin notifications)"""
        try:
            if not isinstance(event.message, MessageService):
                return
                
            # Get group details
            group_id = str(event.chat_id)
            group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
            
            action_type = type(event.message.action).__name__
            logger.info(f"🔧 SERVICE MESSAGE in {group_name}: {action_type}")
            
            # Log all attributes of the action
            action = event.message.action
            logger.debug(f"   Action attributes: {dir(action)}")
            
            # Check different types of pin actions
            if hasattr(action, 'message'):
                logger.info(f"   Action has message attribute")
                if action.message:
                    logger.info(f"   Message ID: {action.message.id}")
                    try:
                        pinned_msg_id = action.message.id
                        pinned_msg = await self.client.get_messages(event.chat_id, ids=pinned_msg_id)
                        
                        if pinned_msg and not isinstance(pinned_msg, list):
                            logger.success(f"🔍 Successfully retrieved pinned message!")
                            await self.process_pinned_message(pinned_msg, group_id, group_name)
                        else:
                            logger.warning(f"❌ Could not retrieve pinned message")
                            
                    except Exception as e:
                        logger.error(f"❌ Error processing pin action: {e}")
                else:
                    logger.info(f"   Action.message is None")
            else:
                logger.info(f"   Action has no message attribute")
                
            # Check if action type contains "pin"
            if "pin" in action_type.lower():
                logger.info(f"🎯 This looks like a pin-related action!")
                
        except Exception as e:
            logger.error(f"❌ Error handling service message: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    async def process_pinned_message(self, message, group_id, group_name):
        """Process a pinned message"""
        try:
            # Skip if already processed
            message_id = message.id
            if message_id in self.processed_pins:
                return
            
            # Mark as processed
            self.processed_pins.add(message_id)
            
            # Extract message text
            message_text = message.text or message.message or ""
            if not message_text and message.caption:
                message_text = message.caption
                
            # Skip empty messages
            if not message_text:
                return
            
            logger.info(f"📌 Processing pinned message in {group_name} ({group_id})")
            logger.debug(f"📝 Message text: {message_text[:100]}...")
            
            # Process message to detect CAs
            source_info = f"{group_name} (Pinned)"
            ca_results = self.detector.process_message(message_text, source_info)
            
            # Send notifications for each CA
            for ca_data in ca_results:
                await self.send_notification(ca_data, source_info, message_text)
            
            if not ca_results:
                logger.debug(f"🔍 No CA detected in pinned message from {group_name}")
                
        except Exception as e:
            logger.error(f"❌ Error processing pinned message: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    async def check_message_for_ca(self, event):
        """Check any message for CA (fallback method)"""
        try:
            if not event.message or isinstance(event.message, MessageService):
                return
                
            # Get group details
            group_id = str(event.chat_id)
            group_name = self.entity_details['groups'].get(group_id, f"Group {group_id}")
            
            # Extract message text
            message_text = event.message.text or event.message.message or ""
            if not message_text and event.message.caption:
                message_text = event.message.caption
                
            # Skip empty messages
            if not message_text:
                return
            
            # Only process if message contains potential CA
            if re.search(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', message_text):
                logger.debug(f"🔍 Potential CA found in {group_name}, checking...")
                
                # Process message to detect CAs
                source_info = f"{group_name} (Group Message)"
                ca_results = self.detector.process_message(message_text, source_info)
                
                # Send notifications for each CA
                for ca_data in ca_results:
                    await self.send_notification(ca_data, source_info, message_text)
                    
        except Exception as e:
            logger.error(f"❌ Error checking message for CA: {e}")
    async def start_monitoring(self):
        """Start monitoring channels and groups"""
        try:
            # Initialize client
            if not await self.init_client():
                return False
            
            # Setup event handlers
            await self.setup_handlers()
            
            # Test CA detection
            await self.test_ca_detection()
            
            # Check current pinned messages
            await self.check_current_pins()
            
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
                logger.info("📨 Startup notification sent")
            except Exception as e:
                logger.warning(f"⚠️ Could not send startup notification: {e}")
            
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
                logger.info("📨 Stop notification sent")
            except Exception as e:
                logger.warning(f"⚠️ Could not send stop notification: {e}")
            
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
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            
        finally:
            # Clean shutdown
            await self.stop_monitoring()

# Main function
async def main():
    """Main entry point"""
    logger.info("=" * 50)
    logger.info("🚀 Solana CA Monitor Bot")
    logger.info("=" * 50)
    
    # Check if bot is enabled
    if not config.BOT_ENABLED:
        logger.warning("⚠️ Bot is disabled in config. Set BOT_ENABLED=true to enable.")
        return
    
    # Check configuration
    if not config.API_ID or not config.API_HASH:
        logger.error("❌ API_ID and API_HASH must be configured in .env")
        return
        
    if not config.OWNER_ID:
        logger.error("❌ OWNER_ID must be configured in .env")
        return
        
    if not config.MONITOR_CHANNELS and not config.MONITOR_GROUPS:
        logger.error("❌ No channels or groups configured to monitor")
        return
    
    logger.info(f"📋 Configuration:")
    logger.info(f"   👤 Owner ID: {config.OWNER_ID}")
    logger.info(f"   👤 To User ID: {config.TO_USER_ID}")
    logger.info(f"   👥 Groups: {config.MONITOR_GROUPS}")
    logger.info(f"   📢 Channels: {config.MONITOR_CHANNELS}")
    logger.info(f"   🔧 PumpFun: {config.ENABLE_PUMPFUN}")
    logger.info(f"   🔧 Moonshot: {config.ENABLE_MOONSHOT}")
    logger.info(f"   🔧 Native: {config.ENABLE_NATIVE}")
    
    # Create and run bot
    bot = TelegramMonitorBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Startup error: {e}")