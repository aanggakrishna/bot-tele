import re
import asyncio
import os
from datetime import datetime
from telethon import TelegramClient, events
import logging
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))
TO_USER_ID = int(os.getenv("TO_USER_ID"))
MONITOR_GROUPS = [int(g) for g in os.getenv("MONITOR_GROUPS").split(",") if g.strip()]
MONITOR_CHANNELS = [int(c) for c in os.getenv("MONITOR_CHANNELS").split(",") if c.strip()]

# Logging configuration
logging.basicConfig(
    filename='log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = TelegramClient('monitor_bot', API_ID, API_HASH)

# Regex to detect Solana Contract Address (base58-like string)
CA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# Fungsi untuk mendeteksi dan mengirim jika ada CA
async def detect_and_forward_ca(event):
    text = event.message.message if event.message else ''
    matches = CA_REGEX.findall(text)

    if matches:
        ca_list = "\n".join(matches)
        sender = await event.get_sender()
        sender_name = sender.username or sender.first_name or "Unknown"

        chat = await event.get_chat()
        chat_title = getattr(chat, 'title', 'Private Chat')

        log_msg = f"[CA DETECTED] From: {sender_name} | Chat: {chat_title} | Matches: {ca_list}"
        logging.info(log_msg)

        # Print ke terminal
        print("===================================")
        print(f"📡 CA Detected!")
        print(f"📍 Group/Channel : {chat_title}")
        print(f"👤 Sender        : {sender_name}")
        print(f"🧾 CA(s)         :\n{ca_list}")
        print("===================================")

        # Kirim notifikasi ke OWNER
        await client.send_message(
            OWNER_ID,
            f"🚨 *CA Detected!*\n"
            f"👤 From: {sender_name}\n"
            f"🏷️ In: {chat_title}\n\n"
            f"{text}",
            parse_mode='markdown'
        )

        # Kirim hanya CA ke TO_USER
        await client.send_message(TO_USER_ID, ca_list)

# Handler untuk pesan baru di channel
@client.on(events.NewMessage(chats=MONITOR_CHANNELS))
async def handler_new_channel_message(event):
    await detect_and_forward_ca(event)

# Handler untuk pinned message di grup
@client.on(events.MessageEdited(chats=MONITOR_GROUPS))
async def handler_pinned_message(event):
    if event.message.pinned:
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Unknown Group')
            logging.info(f"📌 Pinned message detected in {chat_title} ({event.chat_id})")
            print(f"📌 Pinned message in {chat_title}")
            await detect_and_forward_ca(event)
        except Exception as e:
            logging.error(f"❌ Error processing pinned message: {e}")
            print(f"❌ Error processing pinned message: {e}")

# Fungsi heartbeat (jalan tiap 2 detik)
async def heartbeat():
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[HEARTBEAT] {now}")
        logging.info("[HEARTBEAT]")
        await asyncio.sleep(2)

# Fungsi untuk log daftar grup & channel yang dimonitor
async def log_monitor_info():
    print("===================================")
    print(f"📅 Start Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 Monitoring:")

    for gid in MONITOR_GROUPS:
        try:
            entity = await client.get_entity(gid)
            name = getattr(entity, 'title', getattr(entity, 'username', 'Unknown'))
        except Exception as e:
            name = f"(Unknown group {gid})"
            logging.warning(f"Could not get group name for {gid}: {e}")
        print(f"🔸 Group         : {name} ({gid})")

    for cid in MONITOR_CHANNELS:
        try:
            entity = await client.get_entity(cid)
            name = getattr(entity, 'title', getattr(entity, 'username', 'Unknown'))
        except Exception as e:
            name = f"(Unknown channel {cid})"
            logging.warning(f"Could not get channel name for {cid}: {e}")
        print(f"🔹 Channel       : {name} ({cid})")

    print("❤️ Heartbeat     : Running every 2s")
    print("===================================")

# Fungsi utama
async def main():
    await client.start()
    print("🔌 Bot is starting...")
    logging.info("Bot started.")
    await log_monitor_info()
    await asyncio.gather(client.run_until_disconnected(), heartbeat())

if __name__ == '__main__':
    asyncio.run(main())