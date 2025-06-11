from telethon.sync import TelegramClient
import config

client = TelegramClient('session', config.API_ID, config.API_HASH)
client.start()
print("✅ Session berhasil dibuat dan tersimpan di file 'session.session'")
