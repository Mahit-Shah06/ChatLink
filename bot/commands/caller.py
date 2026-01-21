import discord
from discord.ext import commands
from bot.ui.caller_ui import JoinCallView


class Caller(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="ring")
    async def ring(self, ctx, member: discord.Member):
        # Caller must be in a voice channel
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply(
                "❌ You must be in a voice channel to ring someone.",
                delete_after=5
            )

        voice_channel = ctx.author.voice.channel

        # Cannot ring yourself
        if member.id == ctx.author.id:
            return await ctx.reply(
                "❌ You cannot ring yourself.",
                delete_after=5
            )

        view = JoinCallView(
            guild_id=ctx.guild.id,
            channel_id=voice_channel.id
        )

        try:
            await member.send(
                embed=discord.Embed(
                    title="📞 Incoming Call",
                    description=(
                        f"**{ctx.author.display_name}** is calling you.\n\n"
                        f"Server: **{ctx.guild.name}**\n"
                        f"Channel: **{voice_channel.name}**"
                    ),
                    color=0x00ff99
                ),
                view=view
            )
            await ctx.reply(f"📨 Ring sent to **{member.display_name}**.")
        except discord.Forbidden:
            await ctx.reply(
                "❌ Cannot DM this user (DMs closed).",
                delete_after=5
            )


async def setup(bot):
    await bot.add_cog(Caller(bot))
