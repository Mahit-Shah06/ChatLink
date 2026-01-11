from discord.ext import commands
import discord

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command("help")

    @commands.command()
    async def help(self, ctx):
        embed = discord.Embed(title="📖 Bot Commands", color=0x00ffaa)

        embed.add_field(name="Session", value=
            "`!cb` create session\n"
            "`!delete` delete session\n"
            "`!gp @user` grant access\n"
            "`!rp @user` revoke access\n"
            "`!rpall` revoke all", inline=False)

        embed.add_field(name="AI", value=
            "`!capi` add API keys\n"
            "Chat inside your session channel", inline=False)

        embed.add_field(name="Admin", value=
            "`!purge n` delete messages", inline=False)

        embed.add_field(name="Secret Santa", value=
            "`!ssadd`, `!ssbegin`, `!ssmems`, `!ssremoveall`", inline=False)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))
