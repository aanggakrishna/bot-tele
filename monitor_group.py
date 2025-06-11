import config
import asyncio
from telethon import TelegramClient, events
from trade import buy_token

client = TelegramClient('session', config.API_ID, config.API_HASH)

def extract_contract_address(message_text):
    words = message_text.split()
    for word in words:
        if len(word) >= 32 and word[0].isupper():
            return word
    return None

async def send_dm(message):
    await client.send_message(config.OWNER_ID, message)

@client.on(events.ChatAction(chats=config.GROUP_ID))
async def handler(event):
    if event.pinned:
        message = await event.get_message()
        print("📌 Pinned message:", message.text)
        ca = extract_contract_address(message.text)
        if ca:
            print("CA ditemukan:", ca)
            buy_token(ca, lambda m: asyncio.run(send_dm(m)))
        else:
            print("❌ Tidak ada contract address")

async def main():
    await client.start()
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
