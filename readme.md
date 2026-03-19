# 📘 ChatLink Bot

**ChatLink** is a modular, feature-rich Discord bot designed to bridge the gap between users and AI while providing robust server management tools. It features private AI chat sessions (OpenAI & Gemini), secure API key management, comprehensive logging, and fun community utilities.

---

## ✨ Features

### 🤖 **AI & Private Sessions**
* **Private Chat Channels:** Users can create isolated channels to chat with AI (OpenAI or Gemini).
* **Secure Key Storage:** User API keys are encrypted and stored locally—owners don't see them.
* **Session Management:** Owners can grant (`!gp`) or revoke (`!rp`) access to their private session for other users.

### 🛡️ **Moderation & Admin**
* **Logging System:** Automatic logs for messages, voice activity, member joins/leaves, and admin commands.
* **Channel Control:** `!lock` and `!unlock` channels instantly.
* **Purge:** Bulk delete messages to keep channels clean.
* **Announcements:** Send formatted embedded announcements.

### 🎉 **Fun & Utilities**
* **Secret Santa:** fully automated Secret Santa organizer (Add users, generate pairs, DM participants).
* **Call/Ring:** "Ring" a user to invite them to your voice channel with a clickable button.

---

## 🛠️ Installation & Setup

### 1. Prerequisites
* Python 3.11 or higher
* A Discord Bot Token (from the [Discord Developer Portal](https://discord.com/developers/applications))
* A MongoDB key

### 2. Clone the Repository
```bash
git clone [https://github.com/mahit-shah06/chatlink.git](https://github.com/mahit-shah06/chatlink.git)
cd chatlink
python -m venv venv
```
### 3. Add env variables
```
nano .env
```
Add:
* Discord Token
* MongoDB TOken
* Master key for encrypting/decrypting data
* Role ID for AI seession (not mandatory)
### 4. Run it
```bash
source venv/bin/activate
pip install -r requirements.txt
python -m spacy download en_core_web_sm
python main.py
```
