from discord.ext import commands
import discord

class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.remove_command("help")

    @commands.hybrid_command()
    async def help(self, ctx):
        embed = discord.Embed(
            title="📖 ChatLink Bot Commands", 
            description="Use `!` before every command. Some commands require Admin permissions.",
            color=0x00ffaa
        )

        # Productivity Tracker (New)
        embed.add_field(name="📈 Productivity", value=
            "`!tracker_start` - Initialize current channel for tracking\n"
            "`!chart [@user]` - Show 7-day productivity trend\n"
            "`!leaderboard` - Compare top performers\n"
            "`!chart [start] [end]` - Custom range chart", inline=False)

        # Logging System
        embed.add_field(name="📜 Server Logging", value=
            "`!setup_logs` - Create log category & channels\n"
            "`!toggle_logs <type>` - Enable/Disable specific logs\n"
            "`!logs` - Show logging help & available types", inline=False)

        # Admin & Roles
        embed.add_field(name="🛡️ Admin & Roles", value=
            "`!purge [n]` - Delete last n messages\n"
            "`!create_role [name]` - Create role & get ID\n"
            "`!productivity_role [@role]` - Set the reminder role\n"
            "`!lock` / `!unlock` - Lock current channel", inline=False)

        # Sessions (Legacy)
        embed.add_field(name="📁 Session Management", value=
            "`!cb` - Create private session\n"
            "`!delete` - Delete current session\n"
            "`!gp @user` - Grant access\n"
            "`!rp @user` - Revoke access", inline=False)

        # AI & Utils
        embed.add_field(name="🤖 AI & Utils", value=
            "`!capi` - Manage AI API keys\n"
            "`!ssadd` / `!ssbegin` - Secret Santa commands\n"
            "`!retard @user` - Fun command", inline=False)

        embed.set_footer(text="ChatLink v2.0 | Ahmedabad, IN")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Help(bot))