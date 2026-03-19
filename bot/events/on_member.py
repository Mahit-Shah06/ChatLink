from discord.ext import commands
from bot.core.state_manager import state
from bot.logging.log_types import LogType

class MemberEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        state.update(LogType.MEMBER, member.guild.id, {
            "title": "Member joined",
            "description": f"**User:** {member.name} ({member.id})" 
        })

        await self.bot.logger_instance.process_event(member.guild, LogType.MEMBER, member.guild.id)

    @commands.Cog.listener()
    async def on_member_lave(self, member):
        state.update(LogType.MEMBER, member.guild.id, {
            "title": "Member left",
            "description": f"**User:** {member.name}#{member.discriminator}"
        })

        await self.bot.logger_instance.process_event(member.guild, LogType.MEMBER, member.guild.id)

async def setup(bot):
    await bot.add_cog(MemberEvents(bot))
