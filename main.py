import re
import asyncio
import os
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import MessageService, MessageActionPinMessage
from telethon.tl.types import UpdatePinnedMessage

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
@client.on(events.Raw)
async def on_raw_update(update):
    if isinstance(update, UpdatePinnedMessage):
        try:
            chat_id = update.peer.channel_id if hasattr(update.peer, 'channel_id') else update.peer.chat_id
            full_chat_id = -1000000000000 + chat_id  # Format ID lengkap

            if full_chat_id not in MONITOR_GROUPS:
                return  # Skip jika grup tidak dimonitor

            # Ambil isi pinned message
            pinned_msg_id = update.message_id
            msg = await client.get_messages(full_chat_id, ids=pinned_msg_id)

            if msg:
                sender = await msg.get_sender()
                chat = await client.get_entity(full_chat_id)
                chat_title = getattr(chat, 'title', 'Unknown')
                sender_name = sender.username or sender.first_name or "Unknown"
                text = msg.message or "(no text)"

                print("===================================")
                print(f"📌 Pinned message in: {chat_title} ({full_chat_id})")
                print(f"👤 Sender           : {sender_name}")
                print(f"📝 Message          : {text}")
                print("===================================")

                await detect_and_forward_ca(msg)
            else:
                print(f"❌ Failed to fetch pinned message in chat {full_chat_id}")

        except Exception as e:
            print(f"❌ Error in raw pinned handler: {e}")
            logging.error(f"❌ Error in raw pinned handler: {e}")
# Handler untuk pesan baru di channel
@client.on(events.NewMessage(chats=MONITOR_CHANNELS))
async def handler_new_channel_message(event):
    await detect_and_forward_ca(event)

# Handler untuk pinned message di grup
@client.on(events.MessageEdited(chats=MONITOR_GROUPS))
async def handler_pinned_message(event):
    message = event.message

    # Cek apakah ini service message dan isinya adalah pin
    if isinstance(message, MessageService) and isinstance(message.action, MessageActionPinMessage):
        try:
            chat = await event.get_chat()
            chat_title = getattr(chat, 'title', 'Unknown Group')

            # Ambil pesan yang di-pin
            pinned_msg_id = message.action.message_id
            pinned_msg = await client.get_messages(chat.id, ids=pinned_msg_id)

            if pinned_msg:
                sender = await pinned_msg.get_sender()
                sender_name = sender.username or sender.first_name or "Unknown"
                text = pinned_msg.message or "(no text)"

                print("===================================")
                print(f"📌 Pinned message in: {chat_title}")
                print(f"👤 Sender           : {sender_name}")
                print(f"📝 Message          : {text}")
                print("===================================")

                # Cek apakah mengandung CA
                await detect_and_forward_ca(pinned_msg)

            else:
                print(f"❌ Pinned message not found in {chat_title}")

        except Exception as e:
            logging.error(f"❌ Error handling pinned message: {e}")
            print(f"❌ Error handling pinned message: {e}")

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