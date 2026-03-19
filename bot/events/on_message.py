import discord
from discord.ext import commands
from bot.core.state_manager import state
from bot.logging.log_types import LogType

class MessageListeners(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot: return
        if message.content.startswith("!"): return

        state.update(LogType.MESSAGE, message.channel.id, {
            "title": "📥 Message Sent",
            "description": f"**User:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Content:** {message.content or 'No text'}",
        })

        print(f"DEBUG: Signaling logger for MESSAGE log in {message.guild.name}")
        print(message.content)
        await self.bot.logger_instance.process_event(message.guild, LogType.MESSAGE, message.channel.id)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot: return

        content = message.content if message.content else "Content not found (message too old)"

        state.update(LogType.MESSAGE, message.channel.id, {
            "title": "🗑️ Message Deleted",
            "description": f"**User:** {message.author.mention}\n**Channel:** {message.channel.mention}\n**Content:** {content}",
        })

        await self.bot.logger_instance.process_event(message.guild, LogType.MESSAGE, message.channel.id)

async def setup(bot):
    await bot.add_cog(MessageListeners(bot))
