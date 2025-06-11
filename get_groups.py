from telethon import TelegramClient
from dotenv import load_dotenv
import os

# Load dari file .env
load_dotenv()

# Ambil dari environment
api_id = int(os.getenv('API_ID'))
api_hash = os.getenv('API_HASH')

# Inisialisasi client
client = TelegramClient('session_name', api_id, api_hash)

async def main():
    await client.start()

    async for dialog in client.iter_dialogs():
        if dialog.is_group:
            print(f"Group Name: {dialog.name} | Group ID: {dialog.id}")

with client:
    client.loop.run_until_complete(main())
