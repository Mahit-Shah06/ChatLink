📘 ChatLink Bot — Setup & Run Guide

A modular Discord bot with:

Private AI chat sessions (OpenAI / Gemini ready)

Admin & session controls

Logging infrastructure

Expandable foundation for GATE preparation system

🧩 Requirements

Python ≥ 3.11

Git

Discord Bot Token

Linux / macOS (Windows notes included)

📂 Project Structure (simplified)
ChatLink/
├── bot/
│   ├── commands/
│   ├── services/
│   ├── events/
│   ├── ui/
│   └── main.py
├── ai/
├── memory/
├── security/
├── storage/
├── requirements.txt
├── .env
└── main.py

🔑 Environment Variables

Create a .env file in the project root:

DISCORD_TOKEN=your_discord_bot_token_here
SESSION_ROLE_ID=123456789012345678


SESSION_ROLE_ID = Role given to users who own a private AI session

🐍 Virtual Environment Setup
1️⃣ Create venv (only once)
python3 -m venv venv

2️⃣ Activate venv
Linux / macOS
source venv/bin/activate

Windows (PowerShell)
venv\Scripts\Activate.ps1


You should now see:

(venv) $

3️⃣ Install dependencies
pip install -r requirements.txt

▶️ Running the Bot

Always run from project root:

python3 main.py


or

python main.py


If everything is correct, you’ll see:

✅ Loaded bot.commands.help
✅ Loaded bot.commands.admin_commands
...
🤖 Logged in as ChatLink

🛠️ First-Time Discord Setup Checklist
✔ Required Discord Setup

Create a category named ChatGPT

Create a role for session owners

Copy role ID → put in .env

Give bot:

Manage Channels

Manage Roles

Send Messages

Embed Links

Read Message History

🧪 Test Commands
Command	Description
!cb	Create private AI session
!capi	Add OpenAI / Gemini API key
!gp @user	Grant session access
!rp @user	Revoke access
!rpall	Revoke everyone
!delete	Delete your session
!purge 10	Delete messages (admin)
!ssadd	Secret Santa add
!help	Command list
🧠 Storage Notes

Session data → storage/sessions/

API keys → storage/apikeys.json (encrypted)

Logs → storage/logs/ (planned)

Memory per session → auto-managed

Never delete storage/ while bot is running

🚨 Common Errors
Bot won’t start?

Check .env

Check Python version

Check venv activated

Commands don’t load?

File name mismatch

Missing setup(bot) in command file

AI not responding?

API key not added

Wrong model

Rate limit reached
