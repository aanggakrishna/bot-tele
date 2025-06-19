import re
import asyncio
from telethon import TelegramClient, events
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Load from .env ---
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))
TO_USER_ID = int(os.getenv("TO_USER_ID"))
MONITOR_GROUPS = [int(g) for g in os.getenv("MONITOR_GROUPS").split(",") if g.strip()]
MONITOR_CHANNELS = [int(c) for c in os.getenv("MONITOR_CHANNELS").split(",") if c.strip()]

# --- Logging Setup ---
logging.basicConfig(
    filename='log.txt',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = TelegramClient('monitor_bot', API_ID, API_HASH)

# --- Regex untuk mencari Solana CA ---
CA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}\b')

# --- Fungsi untuk mendeteksi dan kirim jika ada CA ---
async def detect_and_forward_ca(event):
    text = event.message.message if event.message else ''
    matches = CA_REGEX.findall(text)

    if matches:
        ca_list = "\n".join(matches)
        sender = await event.get_sender()
        sender_name = sender.username or sender.first_name or "Unknown"
        log_msg = f"[CA DETECTED] From: {sender_name} | Matches: {ca_list}"
        logging.info(log_msg)

        # Notifikasi ke OWNER
        await client.send_message(OWNER_ID, f"🚨 CA Detected!\nFrom: {sender_name}\n\n{text}")

        # Kirim hanya CA ke TO_USER
        await client.send_message(TO_USER_ID, f"{ca_list}")

# --- Event Handler untuk pesan baru di CHANNEL ---
@client.on(events.NewMessage(chats=MONITOR_CHANNELS))
async def handler_new_channel_message(event):
    await detect_and_forward_ca(event)

# --- Event Handler untuk pin message di GROUP ---
@client.on(events.MessagePinned(chats=MONITOR_GROUPS))
async def handler_pinned_message(event):
    try:
        group_id = event.chat_id
        pinned_msg = event.message  # Ini adalah message yang dipin
        logging.info(f"📌 New pinned message in group {group_id}: {pinned_msg.id}")
        
        await detect_and_forward_ca(event)  # event.message sudah isi pinned msg
    except Exception as e:
        logging.error(f"❌ Error handling pinned message: {e}")

# --- Heartbeat setiap 2 detik ---
async def heartbeat():
    while True:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[HEARTBEAT] {now}")
        logging.info("[HEARTBEAT]")
        await asyncio.sleep(2)

async def log_monitor_info():
    print("===================================")
    print(f"📅 Start Time    : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📡 Monitoring:")
    
    for group_id in MONITOR_GROUPS:
        try:
            entity = await client.get_entity(group_id)
            name = entity.title if hasattr(entity, "title") else "Private Group"
            print(f"🔸 Group         : {name} ({group_id})")
        except Exception as e:
            print(f"⚠️  Failed to get group {group_id}: {e}")
    
    for channel_id in MONITOR_CHANNELS:
        try:
            entity = await client.get_entity(channel_id)
            name = entity.title if hasattr(entity, "title") else "Private Channel"
            print(f"🔹 Channel       : {name} ({channel_id})")
        except Exception as e:
            print(f"⚠️  Failed to get channel {channel_id}: {e}")
    
    print("❤️ Heartbeat     : Running every 2s")
    print("===================================")
# --- Main ---
async def main():
    await client.start()
    print("🔌 Bot is starting...")
    logging.info("Bot started.")

    await log_monitor_info()

    await asyncio.gather(
        client.run_until_disconnected(),
        heartbeat()
    )
