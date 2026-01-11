import discord
from datetime import datetime
from bot.logging.log_types import LogType

COLORS = {
    LogType.MESSAGE: discord.Color.blue(),
    LogType.COMMAND: discord.Color.green(),
    LogType.VOICE: discord.Color.purple(),
    LogType.MEMBER: discord.Color.orange(),
    LogType.ADMIN: discord.Color.red(),
    LogType.ERROR: discord.Color.dark_red(),
}

def build_embed(title: str, description: str, log_type: LogType):
    embed = discord.Embed(
        title=title,
        description=description[:4000],
        color=COLORS.get(log_type, discord.Color.dark_grey()),
        timestamp=datetime.utcnow()
    )
    return embed
