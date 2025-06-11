import asyncio
import re
import os
from telethon import TelegramClient, events
from dotenv import load_dotenv
from trading_logic import buy_token, monitor_trades

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
GROUP_ID = int(os.getenv("GROUP_ID"))
SESSION_NAME = "bot_session"

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

def extract_ca(text):
    match = re.search(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b', text)
    return match.group(0) if match else None

async def main_loop():
    last_pinned_id = None
    while True:
        try:
            entity = await client.get_entity(GROUP_ID)
            pinned = await client.get_pinned_message(entity)
            if pinned and pinned.id != last_pinned_id:
                ca_address = extract_ca(pinned.message)
                if ca_address:
                    print(f"CA ditemukan: {ca_address}")
                    buy_token(ca_address)
                last_pinned_id = pinned.id
            monitor_trades()
        except Exception as e:
            print(f"Error: {e}")
        print("✅ Heartbeat...")
        await asyncio.sleep(2)

async def main():
    await client.start()
    await main_loop()

if __name__ == "__main__":
    asyncio.run(main())
