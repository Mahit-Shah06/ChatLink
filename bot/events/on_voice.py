from discord.ext import commands
from bot.logging.log_types import LogType

class VoiceLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            await self.bot.logger.log(
                member.guild,
                LogType.VOICE,
                "Voice Update",
                f"**User:** {member}\n"
                f"**From:** {before.channel}\n"
                f"**To:** {after.channel}"
            )

async def setup(bot):
    await bot.add_cog(VoiceLogger(bot))
