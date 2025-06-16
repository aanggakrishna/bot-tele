import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Telegram Configuration
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

# Initialize client
client = TelegramClient('channel_info_session', API_ID, API_HASH)

async def get_channel_info():
    """Get information about channels and groups you're subscribed to"""
    try:
        await client.start()
        print("✅ Logged in successfully!")
        
        # Get current user info
        me = await client.get_me()
        print(f"👤 Logged in as: {me.first_name} (@{me.username})")
        print("=" * 60)
        
        # Get all dialogs (conversations)
        print("🔍 Fetching all your channels and groups...")
        dialogs = await client.get_dialogs()
        
        channels = []
        supergroups = []
        groups = []
        
        for dialog in dialogs:
            entity = dialog.entity
            
            # Skip users/private chats
            if hasattr(entity, 'first_name'):
                continue
                
            # Get entity info
            entity_id = entity.id
            entity_title = getattr(entity, 'title', 'Unknown')
            entity_username = getattr(entity, 'username', None)
            participants_count = getattr(entity, 'participants_count', 0)
            
            # Determine type and format ID correctly
            if hasattr(entity, 'broadcast') and entity.broadcast:
                # It's a broadcast channel
                formatted_id = f"-100{entity_id}"
                channels.append({
                    'id': formatted_id,
                    'title': entity_title,
                    'username': entity_username,
                    'participants': participants_count,
                    'type': 'Channel'
                })
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                # It's a supergroup
                formatted_id = f"-100{entity_id}"
                supergroups.append({
                    'id': formatted_id,
                    'title': entity_title,
                    'username': entity_username,
                    'participants': participants_count,
                    'type': 'Supergroup'
                })
            else:
                # It's a regular group
                formatted_id = f"-{entity_id}"
                groups.append({
                    'id': formatted_id,
                    'title': entity_title,
                    'username': entity_username,
                    'participants': participants_count,
                    'type': 'Group'
                })
        
        # Display results
        print(f"\n📢 BROADCAST CHANNELS ({len(channels)}):")
        print("=" * 60)
        for i, channel in enumerate(channels, 1):
            print(f"{i:2d}. 📢 {channel['title']}")
            print(f"    🆔 ID: {channel['id']}")
            if channel['username']:
                print(f"    🔗 Username: @{channel['username']}")
            if channel['participants'] > 0:
                print(f"    👥 Subscribers: {channel['participants']:,}")
            print()
        
        print(f"\n👥 SUPERGROUPS ({len(supergroups)}):")
        print("=" * 60)
        for i, group in enumerate(supergroups, 1):
            print(f"{i:2d}. 👥 {group['title']}")
            print(f"    🆔 ID: {group['id']}")
            if group['username']:
                print(f"    🔗 Username: @{group['username']}")
            if group['participants'] > 0:
                print(f"    👥 Members: {group['participants']:,}")
            print()
        
        print(f"\n👥 REGULAR GROUPS ({len(groups)}):")
        print("=" * 60)
        for i, group in enumerate(groups, 1):
            print(f"{i:2d}. 👥 {group['title']}")
            print(f"    🆔 ID: {group['id']}")
            if group['username']:
                print(f"    🔗 Username: @{group['username']}")
            if group['participants'] > 0:
                print(f"    👥 Members: {group['participants']:,}")
            print()
        
        # Generate .env configuration
        print("\n🔧 CONFIGURATION FOR .env FILE:")
        print("=" * 60)
        
        all_sources = channels + supergroups + groups
        if all_sources:
            # Separate channels and groups for .env
            channel_ids = [ch['id'] for ch in channels]
            group_ids = [gr['id'] for gr in supergroups + groups]
            
            print("# Copy these lines to your .env file:")
            print()
            
            if group_ids:
                print(f"MONITOR_GROUPS={','.join(group_ids)}")
            
            if channel_ids:
                print(f"MONITOR_CHANNELS={','.join(channel_ids)}")
            
            print()
            print("# Individual IDs (for reference):")
            for source in all_sources:
                username_part = f" (@{source['username']})" if source['username'] else ""
                print(f"# {source['type']}: {source['title']}{username_part} = {source['id']}")
        
        print(f"\n✅ Found {len(all_sources)} total sources!")
        print("📝 Copy the MONITOR_GROUPS and MONITOR_CHANNELS lines to your .env file")
        
    except SessionPasswordNeededError:
        print("❌ Two-factor authentication is enabled. Please enter your password:")
        password = input("Password: ")
        await client.start(password=password)
        # Retry after authentication
        await get_channel_info()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        await client.disconnect()

async def search_specific_channel():
    """Search for a specific channel by username or name"""
    try:
        await client.start()
        
        search_query = input("\n🔍 Enter channel/group username (with @) or name to search: ").strip()
        
        if not search_query:
            print("❌ No search query provided")
            return
        
        print(f"🔍 Searching for: {search_query}")
        
        try:
            if search_query.startswith('@'):
                # Search by username
                entity = await client.get_entity(search_query)
            else:
                # Search by name in dialogs
                dialogs = await client.get_dialogs()
                entity = None
                
                for dialog in dialogs:
                    if hasattr(dialog.entity, 'title') and search_query.lower() in dialog.entity.title.lower():
                        entity = dialog.entity
                        break
                
                if not entity:
                    print(f"❌ No channel/group found with name containing: {search_query}")
                    return
            
            # Get entity info
            entity_id = entity.id
            entity_title = getattr(entity, 'title', 'Unknown')
            entity_username = getattr(entity, 'username', None)
            participants_count = getattr(entity, 'participants_count', 0)
            
            # Determine type and format ID correctly
            if hasattr(entity, 'broadcast') and entity.broadcast:
                entity_type = "Broadcast Channel"
                formatted_id = f"-100{entity_id}"
                emoji = "📢"
            elif hasattr(entity, 'megagroup') and entity.megagroup:
                entity_type = "Supergroup"
                formatted_id = f"-100{entity_id}"
                emoji = "👥"
            else:
                entity_type = "Regular Group"
                formatted_id = f"-{entity_id}"
                emoji = "👥"
            
            print(f"\n✅ Found {entity_type}:")
            print("=" * 40)
            print(f"{emoji} Name: {entity_title}")
            print(f"🆔 ID: {formatted_id}")
            if entity_username:
                print(f"🔗 Username: @{entity_username}")
            if participants_count > 0:
                print(f"👥 Members: {participants_count:,}")
            print(f"📋 Type: {entity_type}")
            
            print(f"\n🔧 Add this to your .env file:")
            if "Channel" in entity_type:
                print(f"MONITOR_CHANNELS={formatted_id}")
            else:
                print(f"MONITOR_GROUPS={formatted_id}")
                
        except Exception as e:
            print(f"❌ Could not find or access: {search_query}")
            print(f"Error: {e}")
    
    except Exception as e:
        print(f"❌ Error in search: {e}")
    
    finally:
        await client.disconnect()

def main():
    """Main menu"""
    print("🤖 Telegram Channel/Group Info Extractor")
    print("=" * 60)
    print("1. 📋 List all your channels and groups")
    print("2. 🔍 Search for specific channel/group")
    print("3. ❌ Exit")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == '1':
        asyncio.run(get_channel_info())
    elif choice == '2':
        asyncio.run(search_specific_channel())
    elif choice == '3':
        print("👋 Goodbye!")
        return
    else:
        print("❌ Invalid choice!")
        main()

if __name__ == "__main__":
    main()