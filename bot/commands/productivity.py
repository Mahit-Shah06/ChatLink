import discord
from discord.ext import commands
import matplotlib.pyplot as plt
import io
import os
from dotenv import set_key
from bot.ui.productivity_ui import ProductivityRoleView

class ProductivityCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def tracker_start(self, ctx):
        """Initializes the channel and sends the reminder signup button."""
        channel_id = str(ctx.channel.id)
        set_key(".env", "PRODUCTIVITY_CHANNEL_ID", channel_id)
        os.environ["PRODUCTIVITY_CHANNEL_ID"] = channel_id
        
        embed = discord.Embed(
            title="📈 Productivity Tracking Active",
            description=(
                f"Tracking enabled in {ctx.channel.mention}.\n\n"
                "**Click the button below** to get the reminder role for 11 PM IST pings!"
            ),
            color=0x00ff88
        )
        await ctx.send(embed=embed, view=ProductivityRoleView())

    @commands.command()
    async def chart(self, ctx, member: discord.Member = None, start: str = None, end: str = None):
        """Usage: !chart [@user] [start_date] [end_date]"""
        target = member or ctx.author
        
        # Parse dates using the service logic
        start_dt, end_dt = self.bot.productivity_service.parse_dates(start, end)
        
        if not start_dt:
            return await ctx.send("❌ Invalid date format. Please use YYYY-MM-DD.")

        # Fetch data as a DataFrame
        df = await self.bot.productivity_service.get_stats_dataframe(target.id, start_dt, end_dt)
        
        if df is None or df.empty:
            return await ctx.send(f"❌ No data found for {target.display_name} between {start_dt.date()} and {end_dt.date()}.")

        # Process data: Group by date and get average score
        daily_avg = df.groupby('date')['score'].mean()

        # Generate Plot
        plt.figure(figsize=(10, 5))
        plt.plot(daily_avg.index.astype(str), daily_avg.values, marker='o', color='#00ff99', linewidth=2)
        plt.title(f"Productivity Trend: {target.display_name}", color='white')
        plt.xlabel("Date", color='white')
        plt.ylabel("Score (1-10)", color='white')
        plt.xticks(rotation=45, color='white')
        plt.yticks(color='white')
        plt.grid(True, linestyle='--', alpha=0.3)
        plt.ylim(0, 11)

        # Save to buffer to send as a Discord File
        buf = io.BytesIO()
        plt.savefig(buf, format='png', facecolor='#2c2f33', bbox_inches='tight')
        buf.seek(0)
        plt.close()

        file = discord.File(buf, filename="productivity_chart.png")
        await ctx.send(f"📊 **Productivity Trend for {target.mention}** ({start_dt.date()} to {end_dt.date()})", file=file)

    @commands.command()
    async def leaderboard(self, ctx, start: str = None, end: str = None):
        """Usage: !leaderboard [start_date] [end_date]"""
        start_dt, end_dt = self.bot.productivity_service.parse_dates(start, end)
        
        if not start_dt:
            return await ctx.send("❌ Invalid date format. Please use YYYY-MM-DD.")

        df = await self.bot.productivity_service.get_stats_dataframe(None, start_dt, end_dt)
        
        if df is None or df.empty:
            return await ctx.send("The leaderboard is empty for this period.")

        # Aggregate average scores per user
        lb = df.groupby('user_id')['score'].mean().sort_values(ascending=False).head(10)
        
        embed = discord.Embed(
            title=f"🏆 Productivity Leaderboard",
            description=f"Showing top performers from **{start_dt.date()}** to **{end_dt.date()}**",
            color=0x00ff99
        )

        for i, (user_id, avg_score) in enumerate(lb.items(), 1):
            user = self.bot.get_user(user_id)
            name = user.display_name if user else f"User {user_id}"
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "👤"
            embed.add_field(
                name=f"{medal} {i}. {name}", 
                value=f"Average Score: **{avg_score:.1f}/10**", 
                inline=False
            )

        await ctx.send(embed=embed)

    # ---------- Prouctivity Role ----------
    @commands.command()
    @commands.has_permissions(administrator = True)
    async def productivity_role(self, ctx, role: discord.Role):
        role_id = str(role.id)

        set_key(".env", "PRODUCTIVITY_ROLE_ID", role_id)

        os.environ["PRODUCTIVITY_ROLE_ID"] = role_id

        await ctx.send(f"✅ Set {role.mention} (`{role_id}`) as the **Productivity Reminder Role**.")

async def setup(bot):
    await bot.add_cog(ProductivityCommands(bot))