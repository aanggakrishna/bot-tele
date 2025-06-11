import base58
import json

base58_key = input("Masukkan Private Key base58: ").strip()

decoded = base58.b58decode(base58_key)

if len(decoded) != 64:
    print("❌ Panjang private key salah! Harus 64 bytes setelah decode")
else:
    with open("wallet.json", "w") as f:
        json.dump(list(decoded), f)
    print("✅ wallet.json berhasil dibuat!")
