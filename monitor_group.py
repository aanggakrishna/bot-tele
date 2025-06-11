from telethon import TelegramClient, events
from trade import execute_trade
import config

client = TelegramClient('session', config.API_ID, config.API_HASH)

def extract_ca(text):
    import re
    match = re.search(r'CA[:\s]+([A-Za-z0-9]{32,44})', text)
    if match:
        return match.group(1)
    return None

@client.on(events.ChatAction)
async def handler(event):
    if event.pinned:
        message = await event.get_message()
        sender = await event.get_user()
        if sender.username == config.ADMIN_USERNAME:
            print("✅ Ada pin baru dari admin!")
            print("Pesan:", message.text)
            ca = extract_ca(message.text)
            if ca:
                print("🎯 Contract Address ditemukan:", ca)
                execute_trade(ca)
            else:
                print("❌ Tidak ditemukan Contract Address.")
                
client.start()
print("Bot sedang berjalan...")
client.run_until_disconnected()
