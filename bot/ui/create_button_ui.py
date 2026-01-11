import discord, json, os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
SESSION_ROLE_ID = int(os.getenv("SESSION_ROLE_ID"))

class CreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create A Private Session", style=discord.ButtonStyle.primary)
    async def create(self, interaction: discord.Interaction, _):
        user = interaction.user
        guild = interaction.guild

        role = guild.get_role(SESSION_ROLE_ID)
        if not role:
            return await interaction.response.send_message("❌ Session role missing.", ephemeral=True)

        if role in user.roles:
            return await interaction.response.send_message("⚠️ You already have a session.", ephemeral=True)

        await user.add_roles(role)

        category = discord.utils.get(guild.categories, name="ChatGPT")
        if not category:
            return await interaction.response.send_message("❌ Category ChatGPT not found.", ephemeral=True)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True)
        }

        channel = await guild.create_text_channel(
            name=f"session-{user.name}",
            category=category,
            overwrites=overwrites
        )

        os.makedirs("storage", exist_ok=True)
        path = "storage/sessions.json"
        sessions = json.load(open(path)) if os.path.exists(path) else {}

        sessions[str(user.id)] = {
            "channel_id": channel.id,
            "toc": datetime.now().strftime("%H:%M:%S"),
            "doc": datetime.now().strftime("%Y-%m-%d")
        }

        json.dump(sessions, open(path, "w"), indent=4)

        await interaction.response.send_message(
            f"🧠 Session created: {channel.mention}",
            ephemeral=True
        )
