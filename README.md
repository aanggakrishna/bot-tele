# Telegram Solana CA Monitor Bot

A lightweight Telegram monitor that detects Solana Contract Addresses (CA) from channels, groups, and specific users, then forwards them to your Saved Messages (owner) and/or a target user.

## Features
- Monitor multiple channels, groups, and users (by ID)
- Detect Solana CA (32–44 chars, Base58)
- Platform hints: PumpFun, Moonshot, or Native
- Forward full details to OWNER_ID, and send CA-only to TO_USER_ID
- Read URLs from inline buttons (to detect pump.fun/moonshot links)
- Simple logging to `log.txt` with extra debug prints

## Project Structure
- main.py — main runner (monitor channels and users)
- ca_detector.py — CA detection and platform classification
- config.py — environment config loader
- telegram_id_check.py — helper to get/verify Telegram IDs
- env.example — example environment file
- requirements.txt — Python dependencies

## Prerequisites
- Python 3.9+ (recommended 3.10+)
- A Telegram API ID and API Hash (from https://my.telegram.org)

## Setup
1) Create and activate a virtual environment (optional but recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows PowerShell
```

2) Install dependencies:

```bash
pip install -r requirements.txt
```

3) Prepare environment variables:

```bash
cp env.example .env
# Edit .env and fill your values
```

Minimum required in .env:

```
API_ID=your_api_id
API_HASH=your_api_hash
OWNER_ID=your_telegram_user_id
TO_USER_ID=target_user_id_to_receive_CA_only

# Comma-separated lists, leave empty if not used
MONITOR_CHANNELS=
MONITOR_GROUPS=
MONITOR_USERS=
```

Optional and defaults:

```
BOT_ENABLED=true
ENABLE_CHANNEL_MONITORING=true
ENABLE_GROUP_MONITORING=true
ENABLE_USER_MONITORING=true
SELECT_MODE_ON_STARTUP=false

# Solana / trading (optional for detection only)
RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_PRIVATE_KEY_BASE58=
PRIVATE_KEY_PATH=
ENABLE_REAL_TRADING=false
AMOUNT_TO_BUY_SOL=0.01
SLIPPAGE_BPS=500
STOP_LOSS_PERCENT=0.52
TAKE_PROFIT_PERCENT=0.75
MAX_PURCHASES_ALLOWED=2
JUPITER_API_URL=https://quote-api.jup.ag/v6

# Platform toggles
ENABLE_PUMPFUN=true
ENABLE_MOONSHOT=true
ENABLE_RAYDIUM=true
ENABLE_BIRDEYE=true
ENABLE_NATIVE=true
```

Tips:
- For basic CA forwarding, it’s enough to set API_ID, API_HASH, OWNER_ID, TO_USER_ID, and your monitor lists.
- If `ENABLE_NATIVE=true`, the bot will forward a valid Base58 CA even without pump.fun/moonshot hints.

## Getting IDs
Use the helper to discover or check IDs:

```bash
python telegram_id_check.py
```

Then fill MONITOR_CHANNELS, MONITOR_GROUPS, and MONITOR_USERS in `.env` with comma-separated numeric IDs.

## Run

```bash
python main.py
```

- The first run will prompt a login for Telegram (phone number and code).
- The bot writes logs into `log.txt` and prints helpful debug information to the console.

## Troubleshooting
- No CA detected but you’re sure it exists:
  - Ensure `ENABLE_NATIVE=true` in `.env`, then restart.
  - If you want platform classification, include keywords/links like `pump.fun` or `moonshot`.
  - A valid Solana CA is Base58 and 32–44 characters long (no 0, O, I, l).
- Environment variables not taking effect:
  - Make sure you edited `.env` (not `env.example`) and restarted the process.
- Access or permission issues:
  - Confirm your account can read the monitored chats.

## Safety
- Never commit `.env` or share your API credentials.
- Be careful with real trading flags; the bot can be used for detection and forwarding only.

---
Happy monitoring!