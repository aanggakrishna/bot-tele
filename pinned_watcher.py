import asyncio
import os
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.tl.functions.messages import GetFullChatRequest
from trading_logic import buy_token, monitor_trades

# Load ENV
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
SESSION = os.getenv("SESSION_NAME")
GROUP_ID = int(os.getenv("GROUP_ID"))

client = TelegramClient(SESSION, API_ID, API_HASH)

last_pinned_id = None

async def get_pinned_message():
    global last_pinned_id
    full_chat = await client(GetFullChatRequest(GROUP_ID))
    pinned_id = full_chat.full_chat.pinned_msg_id
    if pinned_id and pinned_id != last_pinned_id:
        message = await client.get_messages(GROUP_ID, ids=pinned_id)
        last_pinned_id = pinned_id
        return message
    return None

async def main():
    await client.start()
    print("✅ Bot pinned watcher berjalan...")
    
    while True:
        try:
            message = await get_pinned_message()
            if message:
                print(f"📌 Pinned message baru: {message.text}")
                # Misal CA kamu deteksi di sini
                if len(message.text) ==
