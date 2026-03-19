import discord
from discord.ext import commands
from bot.logging.log_types import LogType
from bot.core.state_manager import state

class CommandLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command(self, ctx):
        # Store command execution details in memory
        state.update(LogType.COMMAND, ctx.guild.id, {
            "title": "💻 Command Executed",
            "description": (
                f"**User:** {ctx.author.mention} ({ctx.author.id})\n"
                f"**Command:** `!{ctx.command.name}`\n"
                f"**Channel:** {ctx.channel.mention}"
            )
        })
        
        # Signal the logger instance
        await self.bot.logger_instance.process_event(ctx.guild, LogType.COMMAND, ctx.guild.id)

async def setup(bot):
    await bot.add_cog(CommandLogger(bot))