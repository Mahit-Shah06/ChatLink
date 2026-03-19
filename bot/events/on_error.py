import discord
from discord.ext import commands
from bot.logging.log_types import LogType
from bot.core.state_manager import state

class ErrorLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        # Ignore non-existent commands to save space
        if isinstance(error, commands.CommandNotFound):
            return

        state.update(LogType.ERROR, ctx.guild.id, {
            "title": "⚠️ Command Error",
            "description": (
                f"**User:** {ctx.author.mention}\n"
                f"**Command:** `!{ctx.command.name if ctx.command else 'Unknown'}`\n"
                f"**Error:** ```py\n{str(error)}\n```"
            )
        })

        await self.bot.logger_instance.process_event(ctx.guild, LogType.ERROR, ctx.guild.id)

async def setup(bot):
    await bot.add_cog(ErrorLogger(bot))