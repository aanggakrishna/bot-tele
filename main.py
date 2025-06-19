import os
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
import logging

# --- Load .env ---
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))       # Saved message
TO_USER_ID = int(os.getenv("TO_USER_ID"))   # Hanya CA
MONITOR_CHANNELS = [int(c) for c in os.getenv("MONITOR_CHANNELS").split(",") if c.strip()]

# --- Logging ke file ---
logging.basicConfig(
    filename="log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Inisialisasi Telethon ---
client = TelegramClient("monitor_bot", API_ID, API_HASH)

# --- Regex Solana CA ---
CA_REGEX = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")

# --- Handler untuk pesan baru di channel ---
@client.on(events.NewMessage(chats=MONITOR_CHANNELS))
async def handle_channel_message(event):
    try:
        msg = event.message
        text = msg.message or ''
        sender = await msg.get_sender()
        chat = await event.get_chat()
        sender_name = sender.username or sender.first_name or "Unknown"
        chat_title = getattr(chat, 'title', f"Unknown channel {event.chat_id}")

        # 1. Kirim isi pesan ke saved message OWNER
        await client.send_message(OWNER_ID, f"📩 New message from {chat_title}:\n\n{text}")

        # 2. Cek apakah mengandung CA
        matches = CA_REGEX.findall(text)
        if matches:
            ca_list = "\n".join(matches)

            # 3a. Kirim deteksi CA ke OWNER
            await client.send_message(OWNER_ID, f"🚨 CA Detected in {chat_title}\nFrom: {sender_name}\n\n{ca_list}")

            # 3b. Kirim hanya CA ke TO_USER
            await client.send_message(TO_USER_ID, ca_list)

            # 3c. Log terminal
            print("===================================")
            print(f"📡 Channel       : {chat_title}")
            print(f"👤 Sender        : {sender_name}")
            print(f"🧪 CA Found      :\n{ca_list}")
            print("===================================")
            logging.info(f"✅ CA detected from {sender_name} in {chat_title}: {ca_list}")
        else:
            print(f"[INFO] No CA found in message from {chat_title}")
            logging.info(f"No CA in message from {chat_title}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"❌ Exception: {e}")

# --- Heartbeat log setiap 2 detik ---
async def heartbeat():
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[HEARTBEAT] {now}")
        logging.info("[HEARTBEAT]")
        await asyncio.sleep(2)

# --- Main ---
async def main():
    await client.start()
    print("✅ Bot is running...\nMonitoring channels:")
    for c in MONITOR_CHANNELS:
        try:
            entity = await client.get_entity(c)
            print(f"🔹 {getattr(entity, 'title', f'Unknown channel {c}')} ({c})")
        except Exception:
            print(f"🔹 (Unknown channel {c}) ({c})")
    logging.info("Bot started")
    await asyncio.gather(client.run_until_disconnected(), heartbeat())

if __name__ == "__main__":
    asyncio.run(main())
