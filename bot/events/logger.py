import discord
from discord.ext import commands
from datetime import datetime

LOG_CATEGORY = "logs"

def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

class Logger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_log_channel(self, guild, name):
        category = discord.utils.get(guild.categories, name=LOG_CATEGORY)
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                guild.me: discord.PermissionOverwrite(view_channel=True)
            }
            category = await guild.create_category(LOG_CATEGORY, overwrites=overwrites)

        channel = discord.utils.get(category.channels, name=name)
        if not channel:
            channel = await guild.create_text_channel(name, category=category)

        return channel

    # ---------- MESSAGE LOGS ----------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        ch = await self.get_log_channel(message.guild, "message-logs")
        await ch.send(
            f"[{ts()}] #{message.channel} | {message.author}: {message.content}"
        )

    # ---------- VOICE LOGS ----------
    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        ch = await self.get_log_channel(member.guild, "voice-logs")

        if not before.channel and after.channel:
            await ch.send(f"[{ts()}] 🔊 {member} joined {after.channel}")
        elif before.channel and not after.channel:
            await ch.send(f"[{ts()}] 🔇 {member} left {before.channel}")
        elif before.channel != after.channel:
            await ch.send(f"[{ts()}] 🔄 {member} moved {before.channel} → {after.channel}")

    # ---------- MEMBER LOGS ----------
    @commands.Cog.listener()
    async def on_member_join(self, member):
        ch = await self.get_log_channel(member.guild, "member-logs")
        await ch.send(f"[{ts()}] ➕ {member} joined")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        ch = await self.get_log_channel(member.guild, "member-logs")
        await ch.send(f"[{ts()}] ➖ {member} left")

    # ---------- ADMIN COMMAND LOGS ----------
    @commands.Cog.listener()
    async def on_command(self, ctx):
        ch = await self.get_log_channel(ctx.guild, "admin-logs")
        await ch.send(
            f"[{ts()}] ⚙️ {ctx.author} used `{ctx.command}` in #{ctx.channel}"
        )

    # ---------- ERROR LOGS ----------
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ch = await self.get_log_channel(ctx.guild, "error-logs")
        await ch.send(f"[{ts()}] ❌ {error}")

async def setup(bot):
    await bot.add_cog(Logger(bot))
