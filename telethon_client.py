from telethon import TelegramClient
from dotenv import load_dotenv
import os

# Load env
load_dotenv()

API_ID = int(os.getenv('TELEGRAM_API_ID'))
API_HASH = os.getenv('TELEGRAM_API_HASH')

# Buat session client
client = TelegramClient('session', API_ID, API_HASH)

async def main():
    me = await client.get_me()
    print(f"Berhasil login sebagai: {me.username} (ID: {me.id})")

with client:
    client.loop.run_until_complete(main())
