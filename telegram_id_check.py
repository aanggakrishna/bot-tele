import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import User, Chat, Channel
from loguru import logger
from config import config

class TelegramIDChecker:
    def __init__(self):
        self.client = None
        self.ids_data = {
            'users': {},
            'groups': {},
            'channels': {},
            'last_updated': None
        }
        
    async def init_client(self):
        """Initialize Telegram client"""
        try:
            self.client = TelegramClient('id_checker_session', config.API_ID, config.API_HASH)
            await self.client.start()
            logger.info("✅ Telegram client initialized")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize client: {e}")
            return False
    
    async def get_my_info(self):
        """Get information about the current account"""
        try:
            me = await self.client.get_me()
            logger.info("👤 YOUR ACCOUNT INFO:")
            logger.info(f"   ID: {me.id}")
            logger.info(f"   Username: @{me.username if me.username else 'No username'}")
            logger.info(f"   Name: {me.first_name} {me.last_name or ''}")
            logger.info(f"   Phone: {me.phone}")
            
            self.ids_data['users']['me'] = {
                'id': me.id,
                'username': me.username,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'phone': me.phone,
                'is_self': True
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting account info: {e}")
    
    async def get_dialogs_info(self):
        """Get information about all dialogs (chats, groups, channels)"""
        try:
            logger.info("🔍 Scanning all dialogs...")
            
            async for dialog in self.client.iter_dialogs():
                entity = dialog.entity
                
                # Get basic info
                entity_id = entity.id
                entity_title = getattr(entity, 'title', None) or getattr(entity, 'first_name', 'Unknown')
                entity_username = getattr(entity, 'username', None)
                
                # Determine type and save accordingly
                if isinstance(entity, User):
                    if not entity.bot:  # Skip bots for now
                        self.ids_data['users'][entity_title] = {
                            'id': entity_id,
                            'username': entity_username,
                            'first_name': getattr(entity, 'first_name', ''),
                            'last_name': getattr(entity, 'last_name', ''),
                            'phone': getattr(entity, 'phone', ''),
                            'is_contact': getattr(entity, 'contact', False),
                            'is_self': False
                        }
                        logger.info(f"👤 User: {entity_title} (ID: {entity_id})")
                
                elif isinstance(entity, Chat):
                    self.ids_data['groups'][entity_title] = {
                        'id': entity_id,
                        'title': entity_title,
                        'participants_count': getattr(entity, 'participants_count', 0),
                        'type': 'group'
                    }
                    logger.info(f"👥 Group: {entity_title} (ID: {entity_id})")
                
                elif isinstance(entity, Channel):
                    if entity.broadcast:
                        # It's a channel
                        self.ids_data['channels'][entity_title] = {
                            'id': entity_id,
                            'title': entity_title,
                            'username': entity_username,
                            'subscribers_count': getattr(entity, 'participants_count', 0),
                            'type': 'channel'
                        }
                        logger.info(f"📢 Channel: {entity_title} (ID: {entity_id}) @{entity_username or 'No username'}")
                    else:
                        # It's a supergroup
                        self.ids_data['groups'][entity_title] = {
                            'id': entity_id,
                            'title': entity_title,
                            'username': entity_username,
                            'participants_count': getattr(entity, 'participants_count', 0),
                            'type': 'supergroup'
                        }
                        logger.info(f"👥 Supergroup: {entity_title} (ID: {entity_id}) @{entity_username or 'No username'}")
        
        except Exception as e:
            logger.error(f"❌ Error getting dialogs: {e}")
    
    async def search_specific_entity(self, query: str):
        """Search for specific entity by username or name"""
        try:
            logger.info(f"🔍 Searching for: {query}")
            
            # Try to get entity directly
            try:
                entity = await self.client.get_entity(query)
                entity_id = entity.id
                
                if isinstance(entity, User):
                    logger.info(f"👤 Found User: {entity.first_name} {entity.last_name or ''} (ID: {entity_id}) @{entity.username or 'No username'}")
                elif isinstance(entity, (Chat, Channel)):
                    logger.info(f"👥 Found Group/Channel: {entity.title} (ID: {entity_id}) @{getattr(entity, 'username', '') or 'No username'}")
                
                return entity
                
            except Exception:
                logger.warning(f"⚠️ Could not find entity directly: {query}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Error searching entity: {e}")
            return None
    
    def save_to_file(self, filename='telegram_ids.json'):
        """Save collected IDs to JSON file"""
        try:
            self.ids_data['last_updated'] = datetime.now().isoformat()
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.ids_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"💾 IDs saved to: {filename}")
            
            # Also create a readable summary
            self.create_summary_file()
            
        except Exception as e:
            logger.error(f"❌ Error saving file: {e}")
    
    def create_summary_file(self):
        """Create a readable summary file"""
        try:
            summary_lines = []
            summary_lines.append("=" * 60)
            summary_lines.append("📋 TELEGRAM IDs SUMMARY")
            summary_lines.append("=" * 60)
            summary_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            summary_lines.append("")
            
            # Your account
            if 'me' in self.ids_data['users']:
                me = self.ids_data['users']['me']
                summary_lines.append("👤 YOUR ACCOUNT:")
                summary_lines.append(f"   ID: {me['id']}")
                summary_lines.append(f"   Username: @{me['username'] or 'No username'}")
                summary_lines.append(f"   Name: {me['first_name']} {me['last_name'] or ''}")
                summary_lines.append("")
            
            # Groups
            if self.ids_data['groups']:
                summary_lines.append("👥 GROUPS & SUPERGROUPS:")
                for name, info in self.ids_data['groups'].items():
                    username_part = f" @{info['username']}" if info.get('username') else ""
                    summary_lines.append(f"   {name}: {info['id']}{username_part}")
                summary_lines.append("")
            
            # Channels
            if self.ids_data['channels']:
                summary_lines.append("📢 CHANNELS:")
                for name, info in self.ids_data['channels'].items():
                    username_part = f" @{info['username']}" if info.get('username') else ""
                    summary_lines.append(f"   {name}: {info['id']}{username_part}")
                summary_lines.append("")
            
            # Users (contacts)
            if len(self.ids_data['users']) > 1:  # More than just 'me'
                summary_lines.append("👤 USERS/CONTACTS:")
                for name, info in self.ids_data['users'].items():
                    if name != 'me':
                        username_part = f" @{info['username']}" if info.get('username') else ""
                        summary_lines.append(f"   {name}: {info['id']}{username_part}")
                summary_lines.append("")
            
            # Save summary
            with open('telegram_ids_summary.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(summary_lines))
            
            logger.info("📄 Summary saved to: telegram_ids_summary.txt")
            
        except Exception as e:
            logger.error(f"❌ Error creating summary: {e}")
    
    async def close(self):
        """Close client connection"""
        if self.client:
            await self.client.disconnect()
            logger.info("✅ Client disconnected")

async def main():
    """Main function"""
    logger.info("🔍 TELEGRAM ID CHECKER")
    logger.info("=" * 40)
    
    checker = TelegramIDChecker()
    
    try:
        # Initialize client
        if not await checker.init_client():
            return
        
        # Get your account info
        await checker.get_my_info()
        
        # Get all dialogs
        await checker.get_dialogs_info()
        
        # Ask if user wants to search for specific entities
        print("\n🔍 Do you want to search for specific groups/channels?")
        print("   Enter usernames or names (one per line, empty line to finish):")
        
        while True:
            query = input("Search: ").strip()
            if not query:
                break
            
            await checker.search_specific_entity(query)
        
        # Save results
        checker.save_to_file()
        
        # Show summary
        print("\n" + "=" * 60)
        print("✅ SCAN COMPLETE!")
        print("📁 Files created:")
        print("   - telegram_ids.json (detailed JSON data)")
        print("   - telegram_ids_summary.txt (readable summary)")
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Main error: {e}")
    
    finally:
        await checker.close()

if __name__ == "__main__":
    asyncio.run(main())