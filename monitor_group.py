import asyncio
import time
import logging
import re
from telethon import TelegramClient, events
import config
from trade import buy_token

# Setup logging ke file dan console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)

client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)

# Fungsi parsing address Solana dari message
def extract_ca(text):
    pattern = r'([1-9A-HJ-NP-Za-km-z]{32,44})'
    match = re.search(pattern, text)
    return match.group(1) if match else None

@client.on(events.NewMessage(chats=config.GROUP_ID, func=lambda e: e.message.pinned))
async def pinned_handler(event):
    message = event.message
    logging.info(f"📌 Pinned message: {message.text}")
    
    ca = extract_ca(message.text)
    if ca:
        logging.info(f"🎯 Dapat CA: {ca}")
        await buy_token(ca)
    else:
        logging.warning("❌ Tidak ditemukan contract address.")

# Heartbeat loop setiap 2 detik
async def heartbeat():
    while True:
        logging.info("💓 Bot running... menunggu pinned message...")
        await asyncio.sleep(2)

async def main():
    await client.start()
    await asyncio.gather(
        client.run_until_disconnected(),
        heartbeat()
    )

if __name__ == '__main__':
    asyncio.run(main())
