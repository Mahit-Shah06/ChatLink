from discord.ext import commands
import discord

class ServerIco(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="servericon")
    async def servericon(self, ctx):
        """Sends the server's icon."""
        guild = ctx.guild

        if not guild.icon:
            await ctx.send("❌ This server doesn't have an icon set.")
            return

        embed = discord.Embed(
            title=f"{guild.name}'s Server Icon",
            color=discord.Color.blurple()
        )
        embed.set_image(url=guild.icon.url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(name='pfp')
    async def pfp(self, ctx, user: discord.Member = None):
        """Sends a user's profile picture."""
        user = user or ctx.author  # defaults to the command caller if no user given

        embed = discord.Embed(
            title=f"{user.display_name}'s Profile Picture",
            color=discord.Color.blurple()
        )
        embed.set_image(url=user.display_avatar.with_size(4096).url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerIco(bot))