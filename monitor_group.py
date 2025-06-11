from telethon import TelegramClient, events
from telethon.tl.functions.messages import SendMessageRequest
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

async def send_dm(message):
    await client(SendMessageRequest(peer=config.OWNER_ID, message=message))

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
                try:
                    execute_trade(ca)
                    await send_dm(f"✅ Trade executed!\nCA: {ca}")
                except Exception as e:
                    await send_dm(f"❌ Trade failed!\nError: {str(e)}")
            else:
                print("❌ CA not found.")

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
