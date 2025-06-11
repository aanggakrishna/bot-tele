import asyncio
import os
import re
from telethon import TelegramClient
from dotenv import load_dotenv

# Load env
load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
GROUP_ID = int(os.getenv('GROUP_ID'))
OWNER_ID = int(os.getenv('OWNER_ID'))

client = TelegramClient('session', API_ID, API_HASH)

# Regex sederhana Solana CA
SOLANA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

last_pinned_id = None

async def send_owner_dm(message):
    await client.send_message(OWNER_ID, message)

async def check_pinned():
    global last_pinned_id

    group = await client.get_entity(GROUP_ID)
    pinned_msg_id = group.pinned_msg_id

    if pinned_msg_id != last_pinned_id:
        last_pinned_id = pinned_msg_id
        if pinned_msg_id is not None:
            message = await client.get_messages(GROUP_ID, ids=pinned_msg_id)
            text = message.message
            print(f"\nPinned message baru: {text}")

            match = SOLANA_REGEX.search(text)
            if match:
                ca = match.group(0)
                print(f"Ditemukan Solana CA: {ca}")
                await send_owner_dm(f"CA Solana ditemukan: {ca}")
                # --> nanti logika buy dipanggil di sini
            else:
                print("Tidak ditemukan Solana CA di pinned ini.")
        else:
            print("Pinned message kosong.")
    else:
        print("Heartbeat...")

async def main():
    group = await client.get_entity(GROUP_ID)
    print(f"Bot berjalan, memantau group: {group.title}")

    while True:
        await check_pinned()
        await asyncio.sleep(2)  # heartbeat 2 detik

with client:
    client.loop.run_until_complete(main())
