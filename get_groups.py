from telethon.sync import TelegramClient
import config

client = TelegramClient('session', config.API_ID, config.API_HASH)
client.start()

dialogs = client.get_dialogs()

for dialog in dialogs:
    print(f"Name: {dialog.name} - ID: {dialog.id} - Type: {type(dialog.entity)}")
