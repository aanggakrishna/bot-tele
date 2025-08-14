import os
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events
import logging
from ca_detector import CADetector

# --- Load .env ---
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
OWNER_ID = int(os.getenv("OWNER_ID"))       # Saved message
TO_USER_ID = int(os.getenv("TO_USER_ID"))   # Hanya CA
MONITOR_CHANNELS = [int(c) for c in os.getenv("MONITOR_CHANNELS", "").split(",") if c.strip()]
# Users to monitor (IDs)
MONITOR_USERS = [int(u) for u in os.getenv("MONITOR_USERS", "").split(",") if u.strip()]

# --- Logging ke file ---
logging.basicConfig(
    filename="log.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Inisialisasi Telethon ---
client = TelegramClient("monitor_bot", API_ID, API_HASH)

# --- Detector untuk CA (PumpFun, Moonshot, Native, dll) ---
detector = CADetector()

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

        # 2. Deteksi CA menggunakan CADetector (lebih akurat)
        ca_results = detector.process_message(text, f"{chat_title} (Channel)")
        if ca_results:
            # 3a. Kirim deteksi CA ke OWNER (detail per platform)
            for ca in ca_results:
                platform = ca['platform'].upper()
                address = ca['address']
                detailed = (
                    f"🚨 {platform} CA DETECTED!\n\n"
                    f"🔗 `{address}`\n\n"
                    f"📊 Source: {chat_title} (Channel)\n"
                    f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"📝 Message:\n{text[:297] + '...' if len(text) > 300 else text}"
                )
                await client.send_message(OWNER_ID, detailed)

            # 3b. Kirim hanya CA ke TO_USER
            only_ca = "\n".join([c['address'] for c in ca_results])
            await client.send_message(TO_USER_ID, only_ca)

            # 3c. Log terminal
            print("===================================")
            print(f"📡 Channel       : {chat_title}")
            print(f"👤 Sender        : {sender_name}")
            print(f"🧪 CA Found      :\n{only_ca}")
            print("===================================")
            logging.info(f"✅ CA detected from {sender_name} in {chat_title}: {only_ca}")
        else:
            print(f"[INFO] No CA found in message from {chat_title}")
            logging.info(f"No CA in message from {chat_title}")

    except Exception as e:
        print(f"❌ Error: {e}")
        logging.error(f"❌ Exception: {e}")

# --- Handler untuk pesan baru dari USER yang dipantau ---
if MONITOR_USERS:
    @client.on(events.NewMessage(from_users=MONITOR_USERS))
    async def handle_user_message(event):
        try:
            msg = event.message
            text = msg.message or ''
            sender = await msg.get_sender()
            chat = await event.get_chat()
            sender_name = sender.username or sender.first_name or "Unknown"
            chat_title = getattr(chat, 'title', getattr(chat, 'first_name', f"Chat {event.chat_id}"))

            # Deteksi CA dengan CADetector
            ca_results = detector.process_message(text, f"{sender_name} (User) in {chat_title}")
            if ca_results:
                # Kirim detail ke OWNER (Saved Messages)
                for ca in ca_results:
                    platform = ca['platform'].upper()
                    address = ca['address']
                    detailed = (
                        f"🚨 {platform} CA DETECTED!\n\n"
                        f"🔗 `{address}`\n\n"
                        f"📊 Source: {sender_name} (User) in {chat_title}\n"
                        f"🕒 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                        f"📝 Message:\n{text[:297] + '...' if len(text) > 300 else text}"
                    )
                    await client.send_message(OWNER_ID, detailed)

                # Kirim hanya CA ke TO_USER
                only_ca = "\n".join([c['address'] for c in ca_results])
                await client.send_message(TO_USER_ID, only_ca)

                logging.info(f"✅ CA from monitored user {sender_name} in {chat_title}: {only_ca}")
            else:
                logging.info(f"No CA in message from monitored user {sender_name} in {chat_title}")
        except Exception as e:
            print(f"❌ Error (user handler): {e}")
            logging.error(f"❌ Exception (user handler): {e}")

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
    if MONITOR_USERS:
        print("Monitoring users:")
        for u in MONITOR_USERS:
            try:
                entity = await client.get_entity(u)
                name = getattr(entity, 'username', None) or getattr(entity, 'first_name', 'Unknown')
                print(f"🔹 {name} ({u})")
            except Exception:
                print(f"🔹 (Unknown user {u}) ({u})")
    logging.info("Bot started")
    await asyncio.gather(client.run_until_disconnected(), heartbeat())

if __name__ == "__main__":
    asyncio.run(main())
