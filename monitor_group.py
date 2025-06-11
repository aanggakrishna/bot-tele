from telethon import TelegramClient, events
import asyncio
import config
from trade import execute_trade

client = TelegramClient('session', config.API_ID, config.API_HASH)

def extract_ca(text):
    lines = text.splitlines()
    for line in lines:
        if 32 <= len(line.strip()) <= 44 and line.strip().isalnum():
            return line.strip()
    return None

@client.on(events.ChatAction(chats=[config.GROUP_ID]))
async def handler(event):
    if event.pinned:
        message = await event.get_message()
        sender = await event.get_user()
        if sender.username == config.ADMIN_USERNAME:
            print("✅ Pinned message from admin detected!")
            print("Message:", message.text)
            ca = extract_ca(message.text)
            if ca:
                print("🎯 CA detected:", ca)
                execute_trade(ca)
            else:
                print("❌ CA not found.")

# Heartbeat log (pengecekan supaya kita tahu bot hidup)
async def heartbeat():
    while True:
        print("⏳ Bot aktif, menunggu pinned message...")
        await asyncio.sleep(10)

async def main():
    await client.start()
    print("✅ Bot sudah terkoneksi ke Telegram.")
    await asyncio.gather(
        client.run_until_disconnected(),
        heartbeat()
    )

asyncio.run(main())
