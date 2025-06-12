import os
import asyncio
from telethon import TelegramClient
from telethon.tl.types import Chat, Channel

async def get_telegram_group_ids():
    # Ambil API_ID dan API_HASH dari environment variables
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')
    
    if not api_id or not api_hash:
        print("Error: API_ID dan API_HASH harus diset sebagai environment variables")
        return
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: API_ID harus berupa angka")
        return
    
    # Buat client Telegram
    client = TelegramClient('session_name', api_id, api_hash)
    
    try:
        await client.start()
        print("Terhubung ke Telegram!")
        print("\nDAFTAR ID GRUP TELEGRAM:")
        print("=" * 50)
        
        # Ambil semua dialog
        dialogs = await client.get_dialogs()
        
        group_count = 0
        
        for dialog in dialogs:
            entity = dialog.entity
            
            # Hanya tampilkan grup dan supergroup
            if isinstance(entity, Chat):
                # Grup biasa
                print(f"Grup: {entity.title}")
                print(f"ID: {entity.id}")
                print("-" * 30)
                group_count += 1
                
            elif isinstance(entity, Channel) and entity.megagroup:
                # Supergroup
                print(f"Supergroup: {entity.title}")
                print(f"ID: {entity.id}")
                if hasattr(entity, 'username') and entity.username:
                    print(f"Username: @{entity.username}")
                print("-" * 30)
                group_count += 1
        
        print(f"\nTotal grup ditemukan: {group_count}")
        
        # Simpan ID grup ke file
        with open('group_ids.txt', 'w', encoding='utf-8') as f:
            f.write("DAFTAR ID GRUP TELEGRAM\n")
            f.write("=" * 50 + "\n\n")
            
            for dialog in dialogs:
                entity = dialog.entity
                
                if isinstance(entity, Chat):
                    f.write(f"Grup: {entity.title}\n")
                    f.write(f"ID: {entity.id}\n\n")
                    
                elif isinstance(entity, Channel) and entity.megagroup:
                    f.write(f"Supergroup: {entity.title}\n")
                    f.write(f"ID: {entity.id}\n")
                    if hasattr(entity, 'username') and entity.username:
                        f.write(f"Username: @{entity.username}\n")
                    f.write("\n")
        
        print(f"ID grup disimpan ke file 'group_ids.txt'")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await client.disconnect()

def main():
    print("Telegram Group ID Finder")
    print("=" * 30)
    asyncio.run(get_telegram_group_ids())

if __name__ == "__main__":
    main()