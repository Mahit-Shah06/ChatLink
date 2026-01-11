from discord.ext import commands
from bot.logging.setup import Logger, LogType

def setup(bot: commands.Bot):
    logger = Logger(bot)

    @bot.event
    async def on_command(ctx: commands.Context):
        await logger.log(
            guild=ctx.guild,
            log_type=LogType.COMMAND,
            title="Command Used",
            user=ctx.author,
            channel=ctx.channel,
            description=f"Command: `{ctx.command}`"
        )
