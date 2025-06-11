from telethon import TelegramClient
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import PeerChat, PeerChannel
import asyncio
import re
import os
from trading_logic import buy_token

# Isi dengan data dari my.telegram.org
api_id = int(os.getenv("API_ID"))
api_hash = os.getenv("API_HASH")
session_name = "session"  # simpan session file
group_username = os.getenv("GROUP_USERNAME")  # contoh: 'RaydiumNewTokenGroup'

client = TelegramClient(session_name, api_id, api_hash)

def extract_ca(text):
    pattern = r'[1-9A-HJ-NP-Za-km-z]{32,44}'
    match = re.search(pattern, text)
    if match:
        return match.group(0)
    else:
        return None

async def get_pinned_message():
    try:
        entity = await client.get_entity(group_username)
        full_chat = await client(GetFullChatRequest(entity))
        pinned = full_chat.full_chat.pinned_msg_id

        if pinned:
            pinned_msg = await client.get_messages(entity, ids=pinned)
            print(f"Pinned message: {pinned_msg.text}")

            ca = extract_ca(pinned_msg.text)
            if ca:
                print(f"✅ CA ditemukan: {ca}")
                buy_token(ca)
            else:
                print("❌ Tidak ditemukan CA di pesan pinned")
        else:
            print("Belum ada pinned message.")
    except Exception as e:
        print(f"Error: {e}")

async def main():
    await client.start()
    print("✅ Bot pinned watcher berjalan...")

    while True:
        await get_pinned_message()
        print("✅ Heartbeat...")
        await asyncio.sleep(5)  # interval pengecekan 5 detik

if __name__ == "__main__":
    asyncio.run(main())
