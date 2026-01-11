import discord
from discord.ext import commands
from discord import ui


class JoinCallView(ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=120)
        self.guild_id = guild_id
        self.channel_id = channel_id

    @ui.button(label="📞 Join Call", style=discord.ButtonStyle.success)
    async def join_call(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.client.get_guild(self.guild_id)
        if not guild:
            return await interaction.response.send_message(
                "❌ Server not found.", ephemeral=True
            )

        channel = guild.get_channel(self.channel_id)
        if not channel or not isinstance(channel, discord.VoiceChannel):
            return await interaction.response.send_message(
                "❌ Voice channel no longer exists.", ephemeral=True
            )

        if not interaction.user.voice:
            await interaction.response.send_message(
                "⚠️ You must join a voice channel first.", ephemeral=True
            )
            return

        await interaction.user.move_to(channel)
        await interaction.response.send_message(
            f"✅ Joined **{channel.name}**", ephemeral=True
        )


class Caller(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="ring")
    async def ring(self, ctx: commands.Context, member: discord.Member):
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.reply(
                "❌ You must be in a voice channel to ring someone.",
                delete_after=5
            )

        voice_channel = ctx.author.voice.channel

        view = JoinCallView(
            guild_id=ctx.guild.id,
            channel_id=voice_channel.id
        )

        try:
            await member.send(
                f"📞 **Incoming Call**\n"
                f"Server: **{ctx.guild.name}**\n"
                f"Channel: **{voice_channel.name}**",
                view=view
            )
            await ctx.reply(f"📨 Ringed {member.mention}")
        except discord.Forbidden:
            await ctx.reply("❌ User has DMs closed.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Caller(bot))
