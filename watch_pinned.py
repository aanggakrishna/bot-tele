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

async def send_owner_dm(message):
    await client.send_message(OWNER_ID, message)

@client.on(events.ChatAction)
async def handler(event):
    if event.chat_id != GROUP_ID:
        return

    # Cek apakah event adalah pin message
    if event.pinned:
        print("Ada message baru di-pin")

        if event.message:
            text = event.message.message
            print(f"Isi message: {text}")

            # Cari CA dengan regex
            match = SOLANA_REGEX.search(text)
            if match:
                ca = match.group(0)
                print(f"Ditemukan Solana CA: {ca}")

                await send_owner_dm(f"CA Solana ditemukan di pin: {ca}")

                # --> Di sinilah nanti logika pembelian akan dipanggil.
                # untuk sekarang cukup kirim notifikasi saja dulu

            else:
                print("Tidak ada Solana CA di pin ini.")

client.start()
print("Bot berjalan, menunggu pinned message...")
client.run_until_disconnected()
