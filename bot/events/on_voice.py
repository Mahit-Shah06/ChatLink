from discord.ext import commands
from bot.logging.log_types import LogType
from bot.core.state_manager import state

class VoiceLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Only log if the user actually switched channels, joined, or left
        if before.channel == after.channel: 
            return
        
        # 1. Update the Memory
        state.update(LogType.VOICE, member.guild.id, {
            "title": "🔊 Voice Update",
            "description": (
                f"**User:** {member.mention}\n"
                f"**Action:** {'Joined' if after.channel else 'Left'} "
                f"{after.channel.name if after.channel else before.channel.name}"
            )
        })
        
        # 2. SIGNAL THE LOGGER (This was missing)
        await self.bot.logger_instance.process_event(member.guild, LogType.VOICE, member.guild.id)

async def setup(bot):
    await bot.add_cog(VoiceLogger(bot))
