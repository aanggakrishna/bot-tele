import config
import time
import logging
from telethon import TelegramClient, events
from trade import buy_token

logging.basicConfig(filename='logs/bot.log', level=logging.INFO, format='%(asctime)s - %(message)s')

client = TelegramClient('session', config.API_ID, config.API_HASH)

last_pin_id = None

@client.on(events.NewMessage(chats=config.GROUP_ID))
async def handler(event):
    global last_pin_id
    if event.message.pinned:
        if event.message.id != last_pin_id:
            last_pin_id = event.message.id
            message = event.message.message
            logging.info(f"Pinned Message: {message}")
            print(f"Pinned Message: {message}")
            ca = extract_ca(message)
            if ca:
                buy_token(ca)

def extract_ca(text):
    for word in text.split():
        if len(word) == 44:
            return word
    return None

client.start()
print("🚀 Bot is running...")
logging.info("Bot is running...")

while True:
    client.run_until_disconnected()
    time.sleep(2)
