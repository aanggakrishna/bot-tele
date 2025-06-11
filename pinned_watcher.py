from telethon import TelegramClient
from telethon.tl.functions.channels import GetFullChannelRequest
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
GROUP_USERNAME = os.getenv("GROUP_USERNAME")  # contoh: "nama_group_kamu"

client = TelegramClient('session', API_ID, API_HASH)

async def check_pinned():
    try:
        entity = await client.get_entity(GROUP_USERNAME)
        full_channel = await client(GetFullChannelRequest(channel=entity))
        pinned_msg_id = full_channel.full_chat.pinned_msg_id

        if pinned_msg_id:
            pinned_msg = await client.get_messages(entity, ids=pinned_msg_id)
            print("Pinned message:", pinned_msg.message)
        else:
            print("Tidak ada pinned message.")
    except Exception as e:
        print("Error:", e)

async def main():
    await client.start()
    while True:
        await check_pinned()
        print("✅ Heartbeat...")
        await asyncio.sleep(5)

with client:
    client.loop.run_until_complete(main())
