import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')
client = TelegramClient('test_channel', API_ID, API_HASH)

async def test_channel_messages():
    """Test getting recent messages from channels"""
    await client.start()
    
    # Your channel ID from .env
    channel_id = -1001988420013
    
    try:
        # Get entity info
        entity = await client.get_entity(channel_id)
        print(f"✅ Channel: {entity.title}")
        print(f"📢 Type: {'Broadcast Channel' if entity.broadcast else 'Unknown'}")
        print("=" * 50)
        
        # Get recent messages
        print("🔍 Getting recent messages...")
        messages = await client.get_messages(channel_id, limit=10)
        
        print(f"📨 Found {len(messages)} recent messages:")
        print("=" * 50)
        
        for i, msg in enumerate(messages, 1):
            if hasattr(msg, 'message') and msg.message:
                message_text = msg.message
            elif hasattr(msg, 'text') and msg.text:
                message_text = msg.text
            else:
                message_text = "[No text content]"
            
            message_date = msg.date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(msg, 'date') else 'Unknown'
            
            print(f"{i:2d}. 📅 {message_date}")
            print(f"    📝 {message_text[:100]}...")
            print()
        
    except Exception as e:
        print(f"❌ Error accessing channel {channel_id}: {e}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_channel_messages())