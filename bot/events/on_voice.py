from discord.ext import commands
from bot.logging.log_types import LogType
from bot.core.state_manager import state

class VoiceLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if before.channel == after.channel: return
        
        state.update(LogType.VOICE, member.guild.id, {
            "title": "🔊 Voice Update",
            "user": member,
            "action": f"{'Joined' if after.channel else 'Left'} {after.channel or before.channel}"
        })
        await self.bot.logger.process_event(member.guild, LogType.VOICE, member.guild.id)

async def setup(bot):
    await bot.add_cog(VoiceLogger(bot))
