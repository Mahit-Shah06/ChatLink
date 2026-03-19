import discord
import os
from discord.ext import tasks, commands
from datetime import datetime

class ProductivityTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_reminder.start()

    def cog_unload(self):
        self.daily_reminder.cancel()

    @tasks.loop(minutes=1)
    async def daily_reminder(self):
        now = datetime.utcnow()
        # 11:00 PM IST is 17:30 UTC
        if now.hour == 17 and now.minute == 30:
            channel_id = os.getenv("PRODUCTIVITY_CHANNEL_ID")
            role_id = os.getenv("PRODUCTIVITY_ROLE_ID")
            
            if channel_id and role_id:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(f"🔔 <@&{role_id}> **Time for the daily log!** What did you achieve today?")

async def setup(bot):
    await bot.add_cog(ProductivityTasks(bot))
