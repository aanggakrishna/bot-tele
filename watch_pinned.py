from telethon import TelegramClient, events
from dotenv import load_dotenv
import os
import re

# Load env
load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')
GROUP_ID = int(os.getenv('GROUP_ID'))
OWNER_ID = int(os.getenv('OWNER_ID'))

client = TelegramClient('session', API_ID, API_HASH)

# Regex sederhana untuk deteksi Solana CA
SOLANA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

async def print_ready():
    group = await client.get_entity(GROUP_ID)
    print(f"Bot berjalan, menunggu pinned message dari grup: {group.title}")

async def send_owner_dm(message):
    await client.send_message(OWNER_ID, message)

@client.on(events.MessageEdited)
async def handler(event):
    if event.chat_id != GROUP_ID:
        return

    message = await event.get_message()

    # Pastikan hanya deteksi pinned message
    if not message.pinned:
        return

    text = message.message
    print(f"Isi pinned message: {text}")

    # Cari CA dengan regex
    match = SOLANA_REGEX.search(text)
    if match:
        ca = match.group(0)
        print(f"Ditemukan Solana CA: {ca}")

        await send_owner_dm(f"CA Solana ditemukan di pin: {ca}")
    else:
        print("Tidak ada Solana CA di pin ini.")


client.start()
client.loop.run_until_complete(print_ready())
client.run_until_disconnected()
