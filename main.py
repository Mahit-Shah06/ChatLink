import discord
from discord.ext import commands
from discord import ui
import json, os
from dotenv import load_dotenv
from encrypting_utils import crypting
from datetime import datetime
from openai_wrapper import AI
from memory_utils import Memory
from secretSantaMemory import MemAcc
import random

load_dotenv()

SESSION_ROLE_ID = int(os.getenv("SESSION_ROLE_ID"))

crypto = crypting()
ai = AI()
memory_handler = Memory()
ssm = MemAcc()

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

#Checks the user id to see the session owner
def is_session_owner(user_id, channel_id):
    if not os.path.exists("sessions.json"):
        return False

    with open("sessions.json", "r") as f:
        sessions = json.load(f)

    for uid, info in sessions.items():
        if info["channel_id"] == channel_id:
            return str(user_id) == uid

    return False


# Ensure apikeys.json exists
if not os.path.exists("apikeys.json"):
    with open("apikeys.json", "w") as f:
        json.dump({}, f)

def save_api_key(user_id, encrypted_key):
    with open("apikeys.json", "r") as f:
        data = json.load(f)

    data[str(user_id)] = encrypted_key.decode()

    with open("apikeys.json", "w") as f:
        json.dump(data, f, indent=4)

# ---------- PURGE MESSAGES ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def purge(ctx, count: int = 1):
    if count>50:
        count = 50
    await ctx.channel.purge(limit=count + 1)

# ---------- API ----------
class APIKeyModal(ui.Modal, title="Enter Your OpenAI API Key"):

    api_key = ui.TextInput(
        label="OpenAI API Key",
        placeholder="sk-xxxxxxxxxxxxxxxxx",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        encrypted = crypto.encrypting(self.api_key.value)
        save_api_key(interaction.user.id, encrypted)

        await interaction.response.send_message(
            "🔐 Your API key has been **securely encrypted and stored**.",
            ephemeral=True,
            delete_after=5
        )

class APIKeyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Enter API Key", style=discord.ButtonStyle.primary)
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        modal = APIKeyModal()
        await interaction.response.send_modal(modal)

@bot.command()
@commands.has_permissions(administrator=True)
async def capi(ctx):
    embed = discord.Embed(
        title="🔑 API Key Setup",
        description="Click the button below to securely enter your OpenAI API key.\n\n"
                    "Your API key will be **encrypted** and only used for your private sessions.",
        color=0x00ff99
    )

    view = APIKeyView()
    await ctx.send(embed=embed, view=view)

@capi.error
async def capi_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need **administrator** permissions to use `!capi`.")

# ---------- CREATE SESSION VIEW ----------
class CreateView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Create A Private Session", style=discord.ButtonStyle.primary)
    async def create_session(self, interaction: discord.Interaction, button: ui.Button):

        user = interaction.user
        guild = interaction.guild

        session_role = guild.get_role(SESSION_ROLE_ID)
        if session_role is None:
            return await interaction.response.send_message(
                "❌ ERROR: Role with that ID does not exist.",
                ephemeral=True,
                delete_after=5
            )

        # Check if user already has a session
        if session_role in user.roles:

            if os.path.exists("sessions.json"):
                with open("sessions.json", "r") as f:
                    sessions = json.load(f)
            else:
                sessions = {}

            user_id = str(user.id)
            if user_id in sessions:
                ch_id = sessions[user_id]["channel_id"]
                channel = guild.get_channel(ch_id)

                return await interaction.response.send_message(
                    f"⚠️ You already have an active session → {channel.mention}",
                    ephemeral=True,
                    delete_after=5
                )

            return await interaction.response.send_message(
                "⚠️ You already have the session role, but no session record was found.",
                ephemeral=True,
                delete_after=5
            )

        # Create session
        await user.add_roles(session_role)

        # Load sessions.json
        if os.path.exists("sessions.json"):
            with open("sessions.json", "r") as f:
                sessions = json.load(f)
        else:
            sessions = {}

        # Category
        category = discord.utils.get(guild.categories, name="ChatGPT")
        if not category:
            return await interaction.response.send_message(
                "❌ ERROR: Category **ChatGPT** not found.",
                ephemeral=True,
                delete_after=5
            )

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            session_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        channel = await guild.create_text_channel(
            name=f"session-{user.name}",
            category=category,
            overwrites=overwrites
        )

        now = datetime.now()

        sessions[str(user.id)] = {
            "channel_id": channel.id,
            "toc": now.strftime("%H:%M:%S"),
            "doc": now.strftime("%Y-%m-%d")
        }

        with open("sessions.json", "w") as f:
            json.dump(sessions, f, indent=4)

        await interaction.response.send_message(
            f"🧠 Your private ChatLink session has been created: {channel.mention}",
            ephemeral=True,
            delete_after=5
        )

# ---------- ON MESSAGE ----------
@bot.event
async def on_message(message):

    if message.author.bot:
        return

    await bot.process_commands(message)

    if message.content.startswith("!"):
        return

    if message.channel.category is None:
        return

    if message.channel.category.name != "ChatGPT":
        return

    channel_id = message.channel.id

    if not os.path.exists("sessions.json"):
        return

    with open("sessions.json", "r") as f:
        sessions = json.load(f)

    owner_id = None
    for user_id, info in sessions.items():
        if info["channel_id"] == channel_id:
            owner_id = user_id
            break

    if owner_id is None:
        return

    with open("apikeys.json", "r") as f:
        keys = json.load(f)

    if owner_id not in keys:
        await message.channel.send(
            "❌ No API key found for the session owner.",
            delete_after=5
        )
        return

    encrypted_key = keys[owner_id]
    api_key = crypto.decrypting(encrypted_key.encode())

    memory = memory_handler.get_memory(channel_id)

    memory.append({
        "role": "user",
        "content": message.content
    })

    try:
        reply = ai.response(memory, api_key)
    except Exception as e:
        await message.channel.send(f"⚠️ API Error: {e}")
        return

    memory.append({
        "role": "assistant",
        "content": reply
    })

    memory_handler.save_memory(channel_id, memory)

    await message.channel.send(reply)

# ---------- CB BUTTON ----------
@bot.command()
@commands.has_permissions(administrator=True)
async def cb(ctx):
    embed = discord.Embed(
        title="Start Chat",
        description="Click the button below to create a private session with ChatGPT",
        color=0x00ff99
    )

    view = CreateView()
    await ctx.send(embed=embed, view=view)

# Delete command
@bot.command()
async def delete(ctx):
    channel_id = ctx.channel.id
    user = ctx.author

    # Check ownership
    if not is_session_owner(user.id, channel_id):
        return await ctx.reply("❌ You are **not** the owner of this session.", delete_after=5)

    # Load sessions.json
    with open("sessions.json", "r") as f:
        sessions = json.load(f)

    # Remove from sessions.json
    del sessions[str(user.id)]

    with open("sessions.json", "w") as f:
        json.dump(sessions, f, indent=4)

    # Remove session role
    session_role = ctx.guild.get_role(SESSION_ROLE_ID)
    if session_role in user.roles:
        await user.remove_roles(session_role)

    # Delete memory file
    mem_path = f"memory/session_{channel_id}.json"
    if os.path.exists(mem_path):
        os.remove(mem_path)

    # Delete channel
    await ctx.channel.delete()

# gp command
@bot.command()
async def gp(ctx, member: discord.Member):
    channel = ctx.channel

    # Owner check
    if not is_session_owner(ctx.author.id, channel.id):
        return await ctx.reply("❌ Only the **session owner** can grant access.")

    overwrites = channel.overwrites_for(member)
    overwrites.view_channel = True
    overwrites.send_messages = True
    overwrites.read_message_history = True

    await channel.set_permissions(member, overwrite=overwrites)

    await ctx.reply(f"✅ {member.mention} has been **granted access**.")    

#rp command
@bot.command()
async def rp(ctx, member: discord.Member):
    channel = ctx.channel

    # Owner check
    if not is_session_owner(ctx.author.id, channel.id):
        return await ctx.reply("❌ Only the **session owner** can revoke access.")

    await channel.set_permissions(member, overwrite=None)

    await ctx.reply(f"🗑️ {member.mention}'s access has been **revoked**.")

#rp all command
@bot.command()
async def rpall(ctx):
    channel = ctx.channel
    author = ctx.author

    # Owner check
    if not is_session_owner(author.id, channel.id):
        return await ctx.reply("❌ Only the **session owner** can revoke everyone.", delete_after=5)

    for member, perms in list(channel.overwrites.items()):
        if isinstance(member, discord.Member) and member != author:
            await channel.set_permissions(member, overwrite=None)

    await ctx.reply("🚫 All access has been **revoked** (except yours).")

#ssadd command
@bot.command()
async def ssadd(ctx, member: discord.Member = None):
    if member is None:
        member = ctx.author
    if ssm.add_member(member):
        await ctx.reply(f"✅ {member.mention} has been **added to the group**.")   
    else:
        print(member)
        return await ctx.reply(""f"⚠️ {member.mention} is already added.")

#ss members name
@bot.command()
async def ssmems(ctx):
    entries = ssm.get_entries()

    if not entries:
        return await ctx.reply("🎄 No participants added yet.")

    msg = "\n".join([f"• {name}" for _, name in entries])
    await ctx.reply(f"🎁 **Participants ({len(entries)}):**\n{msg}")

#begin secret santa
@bot.command()
@commands.has_permissions(administrator=True)
async def ssbegin(ctx):
    entries = ssm.get_entries()

    if len(entries) < 2:
        return await ctx.reply("❌ Need at least **2 participants** to start Secret Santa.")

    ids = [uid for uid, _ in entries]
    names = {uid: name for uid, name in entries}

    shuffled = ids[:]

    while True:
        random.shuffle(shuffled)
        if all(a != b for a, b in zip(ids, shuffled)):
            break

    failed = []

    for giver_id, receiver_id in zip(ids, shuffled):
        try:
            user = await bot.fetch_user(giver_id)
            receiver_name = names[receiver_id]

            await user.send(
                f"🎅 **FINAL Secret Santa Assignment** 🎁\n"
                f"⚠️ Please ignore the previous Secret Santa message. It was sent in error.\n"
                f"There will be no changes after you have recieved this name\n"
                f"You are the Secret Santa for **{receiver_name}**!\n\n"
                f"🤫 Don’t tell anyone."
            )

        except Exception:
            failed.append(names[giver_id])

    with open("SSresults.txt", "w") as f:
        for giver, receiver in zip(ids, shuffled):
            f.write(f"{names[giver]} -> {names[receiver]}\n")

    if failed:
        await ctx.reply(
            f"🎄 Secret Santa started!\n"
            f"⚠️ Could not DM: {', '.join(failed)}"
        )
    else:
        await ctx.reply("🎄 **Secret Santa started successfully!** All DMs sent.")

@bot.command()
@commands.has_permissions(administrator=True)
async def ssremoveall(ctx):
    ssm.clear()
    await ctx.reply("🗑️ **All Secret Santa participants have been removed.**")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.reply("❌ Invalid command. Use `!help` to see available commands.")
        return

bot.run(os.getenv("DISCORD_TOKEN"))
