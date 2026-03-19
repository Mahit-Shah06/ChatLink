import discord
from discord.ext import commands
from bot.logging.log_types import LogType
from bot.core.state_manager import state

class MemberEvents(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):
        state.update(LogType.MEMBER, member.guild.id, {
            "title": "📥 Member Joined",
            "description": f"**User:** {member.mention} ({member.id})\n**Account Created:** {member.created_at.strftime('%Y-%m-%d')}" 
        })
        await self.bot.logger_instance.process_event(member.guild, LogType.MEMBER, member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member): # Changed from 'lave' to 'remove'
        state.update(LogType.MEMBER, member.guild.id, {
            "title": "📤 Member Left",
            "description": f"**User:** {member.name}#{member.discriminator} ({member.id})"
        })
        await self.bot.logger_instance.process_event(member.guild, LogType.MEMBER, member.guild.id)

async def setup(bot):
    await bot.add_cog(MemberEvents(bot))