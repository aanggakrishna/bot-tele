import asyncio
from telethon import TelegramClient
from config import config

async def test_channel():
    client = TelegramClient('test', config.API_ID, config.API_HASH)
    await client.start()
    
    channel_id = -1001988420013
    
    try:
        # Get channel info
        entity = await client.get_entity(channel_id)
        print(f"✅ Channel: {entity.title}")
        print(f"📊 Members: {getattr(entity, 'participants_count', 'Unknown')}")
        
        # Get recent messages
        messages = await client.get_messages(channel_id, limit=10)
        print(f"📨 Recent messages: {len(messages)}")
        
        for i, msg in enumerate(messages):
            if msg.message:
                print(f"{i+1}. {msg.message[:100]}...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test_channel())