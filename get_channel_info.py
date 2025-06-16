import os
import asyncio
from datetime import datetime
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

def save_to_file(content, filename="channel_list.txt"):
    """Save content to file"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Results saved to: {filename}")
        return True
    except Exception as e:
        print(f"❌ Error saving to file: {e}")
        return False

async def get_channel_info():
    """Get information about channels and groups you're subscribed to"""
    output_content = []
    
    try:
        await client.start()
        print("✅ Logged in successfully!")
        
        # Get current user info
        me = await client.get_me()
        user_info = f"👤 Logged in as: {me.first_name} (@{me.username})"
        print(user_info)
        print("=" * 60)
        
        # Add to output
        output_content.append("🤖 TELEGRAM CHANNEL/GROUP INFO EXTRACTOR")
        output_content.append("=" * 60)
        output_content.append(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        output_content.append(user_info)
        output_content.append("=" * 60)
        output_content.append("")
        
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
        
        # Display and save BROADCAST CHANNELS
        channels_section = f"📢 BROADCAST CHANNELS ({len(channels)}):"
        print(f"\n{channels_section}")
        print("=" * 60)
        output_content.append(channels_section)
        output_content.append("=" * 60)
        
        for i, channel in enumerate(channels, 1):
            channel_info = []
            channel_line = f"{i:2d}. 📢 {channel['title']}"
            channel_info.append(channel_line)
            print(channel_line)
            
            id_line = f"    🆔 ID: {channel['id']}"
            channel_info.append(id_line)
            print(id_line)
            
            if channel['username']:
                username_line = f"    🔗 Username: @{channel['username']}"
                channel_info.append(username_line)
                print(username_line)
                
            if channel['participants'] > 0:
                subs_line = f"    👥 Subscribers: {channel['participants']:,}"
                channel_info.append(subs_line)
                print(subs_line)
            
            print()
            channel_info.append("")
            output_content.extend(channel_info)
        
        # Display and save SUPERGROUPS
        supergroups_section = f"👥 SUPERGROUPS ({len(supergroups)}):"
        print(f"\n{supergroups_section}")
        print("=" * 60)
        output_content.append("")
        output_content.append(supergroups_section)
        output_content.append("=" * 60)
        
        for i, group in enumerate(supergroups, 1):
            group_info = []
            group_line = f"{i:2d}. 👥 {group['title']}"
            group_info.append(group_line)
            print(group_line)
            
            id_line = f"    🆔 ID: {group['id']}"
            group_info.append(id_line)
            print(id_line)
            
            if group['username']:
                username_line = f"    🔗 Username: @{group['username']}"
                group_info.append(username_line)
                print(username_line)
                
            if group['participants'] > 0:
                members_line = f"    👥 Members: {group['participants']:,}"
                group_info.append(members_line)
                print(members_line)
            
            print()
            group_info.append("")
            output_content.extend(group_info)
        
        # Display and save REGULAR GROUPS
        groups_section = f"👥 REGULAR GROUPS ({len(groups)}):"
        print(f"\n{groups_section}")
        print("=" * 60)
        output_content.append("")
        output_content.append(groups_section)
        output_content.append("=" * 60)
        
        for i, group in enumerate(groups, 1):
            group_info = []
            group_line = f"{i:2d}. 👥 {group['title']}"
            group_info.append(group_line)
            print(group_line)
            
            id_line = f"    🆔 ID: {group['id']}"
            group_info.append(id_line)
            print(id_line)
            
            if group['username']:
                username_line = f"    🔗 Username: @{group['username']}"
                group_info.append(username_line)
                print(username_line)
                
            if group['participants'] > 0:
                members_line = f"    👥 Members: {group['participants']:,}"
                group_info.append(members_line)
                print(members_line)
            
            print()
            group_info.append("")
            output_content.extend(group_info)
        
        # Generate .env configuration
        config_section = "🔧 CONFIGURATION FOR .env FILE:"
        print(f"\n{config_section}")
        print("=" * 60)
        output_content.append("")
        output_content.append(config_section)
        output_content.append("=" * 60)
        
        all_sources = channels + supergroups + groups
        if all_sources:
            # Separate channels and groups for .env
            channel_ids = [ch['id'] for ch in channels]
            group_ids = [gr['id'] for gr in supergroups + groups]
            
            copy_line = "# Copy these lines to your .env file:"
            print(copy_line)
            print()
            output_content.append(copy_line)
            output_content.append("")
            
            if group_ids:
                groups_config = f"MONITOR_GROUPS={','.join(group_ids)}"
                print(groups_config)
                output_content.append(groups_config)
            
            if channel_ids:
                channels_config = f"MONITOR_CHANNELS={','.join(channel_ids)}"
                print(channels_config)
                output_content.append(channels_config)
            
            print()
            individual_line = "# Individual IDs (for reference):"
            print(individual_line)
            output_content.append("")
            output_content.append(individual_line)
            
            for source in all_sources:
                username_part = f" (@{source['username']})" if source['username'] else ""
                ref_line = f"# {source['type']}: {source['title']}{username_part} = {source['id']}"
                print(ref_line)
                output_content.append(ref_line)
        
        summary_line = f"\n✅ Found {len(all_sources)} total sources!"
        copy_instruction = "📝 Copy the MONITOR_GROUPS and MONITOR_CHANNELS lines to your .env file"
        print(summary_line)
        print(copy_instruction)
        
        output_content.append("")
        output_content.append(summary_line.strip())
        output_content.append(copy_instruction)
        
        # Save to file
        file_content = "\n".join(output_content)
        save_to_file(file_content, "channel_list.txt")
        
        # Also save just the .env config to separate file
        env_config = []
        env_config.append("# Telegram Bot Multi-Source Configuration")
        env_config.append(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        env_config.append("")
        
        if group_ids:
            env_config.append(f"MONITOR_GROUPS={','.join(group_ids)}")
        if channel_ids:
            env_config.append(f"MONITOR_CHANNELS={','.join(channel_ids)}")
        
        env_config.append("")
        env_config.append("# Individual source references:")
        for source in all_sources:
            username_part = f" (@{source['username']})" if source['username'] else ""
            env_config.append(f"# {source['type']}: {source['title']}{username_part} = {source['id']}")
        
        env_content = "\n".join(env_config)
        save_to_file(env_content, "monitor_sources.env")
        
        print(f"\n📁 Files created:")
        print(f"   📋 channel_list.txt - Complete list with details")
        print(f"   ⚙️ monitor_sources.env - Ready-to-use .env configuration")
        
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
            
            result_info = []
            result_info.append(f"🔍 SEARCH RESULT for '{search_query}'")
            result_info.append("=" * 40)
            result_info.append(f"📅 Search Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            result_info.append("")
            result_info.append(f"✅ Found {entity_type}:")
            result_info.append("=" * 40)
            result_info.append(f"{emoji} Name: {entity_title}")
            result_info.append(f"🆔 ID: {formatted_id}")
            
            print(f"\n✅ Found {entity_type}:")
            print("=" * 40)
            print(f"{emoji} Name: {entity_title}")
            print(f"🆔 ID: {formatted_id}")
            
            if entity_username:
                username_line = f"🔗 Username: @{entity_username}"
                print(username_line)
                result_info.append(username_line)
                
            if participants_count > 0:
                members_line = f"👥 Members: {participants_count:,}"
                print(members_line)
                result_info.append(members_line)
                
            type_line = f"📋 Type: {entity_type}"
            print(type_line)
            result_info.append(type_line)
            
            config_line = f"\n🔧 Add this to your .env file:"
            print(config_line)
            result_info.append("")
            result_info.append(config_line.strip())
            
            if "Channel" in entity_type:
                env_line = f"MONITOR_CHANNELS={formatted_id}"
                print(env_line)
                result_info.append(env_line)
            else:
                env_line = f"MONITOR_GROUPS={formatted_id}"
                print(env_line)
                result_info.append(env_line)
            
            # Save search result to file
            search_content = "\n".join(result_info)
            filename = f"search_result_{search_query.replace('@', '').replace(' ', '_')}.txt"
            if save_to_file(search_content, filename):
                print(f"\n💾 Search result saved to: {filename}")
                
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
    print("1. 📋 List all your channels and groups (save to file)")
    print("2. 🔍 Search for specific channel/group (save to file)")
    print("3. 📁 Show saved files")
    print("4. ❌ Exit")
    
    choice = input("\nSelect option (1-4): ").strip()
    
    if choice == '1':
        asyncio.run(get_channel_info())
    elif choice == '2':
        asyncio.run(search_specific_channel())
    elif choice == '3':
        show_saved_files()
    elif choice == '4':
        print("👋 Goodbye!")
        return
    else:
        print("❌ Invalid choice!")
        main()

def show_saved_files():
    """Show list of saved files"""
    print("\n📁 SAVED FILES:")
    print("=" * 40)
    
    files_to_check = [
        "channel_list.txt",
        "monitor_sources.env"
    ]
    
    # Also check for search result files
    import glob
    search_files = glob.glob("search_result_*.txt")
    files_to_check.extend(search_files)
    
    found_files = []
    for filename in files_to_check:
        if os.path.exists(filename):
            file_size = os.path.getsize(filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filename))
            found_files.append({
                'name': filename,
                'size': file_size,
                'modified': file_time
            })
    
    if found_files:
        for i, file_info in enumerate(found_files, 1):
            print(f"{i:2d}. 📄 {file_info['name']}")
            print(f"    📊 Size: {file_info['size']:,} bytes")
            print(f"    🕒 Modified: {file_info['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
            print()
    else:
        print("❌ No saved files found")
        print("💡 Run option 1 or 2 to generate files")
    
    input("\nPress Enter to continue...")
    main()

if __name__ == "__main__":
    main()