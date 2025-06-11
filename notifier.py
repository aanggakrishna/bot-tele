import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv
import os

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))
SESSION_NAME = "bot_session"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

async def send_dm(message):
    await client.start()
    await client.send_message(OWNER_ID, message)
    await client.disconnect()

def notify_owner(message):
    asyncio.run(send_dm(message))
