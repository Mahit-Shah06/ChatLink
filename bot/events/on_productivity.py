import os
from discord.ext import commands
from bot.services.productivity_service import ProductivityService

class ProductivityTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ProductivityService()

    def is_tracker_channel(self, channel_id):
        return str(channel_id) == os.getenv("PRODUCTIVITY_CHANNEL_ID")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not self.is_tracker_channel(message.channel.id):
            return

        await message.add_reaction("✅")
        await self.service.save_entry(message.author.id, message.content, "SENT")

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if after.author.bot or not self.is_tracker_channel(after.channel.id):
            return

        await self.service.save_entry(after.author.id, f"EDITED: {after.content}", "EDIT")

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not self.is_tracker_channel(message.channel.id):
            return

        await self.service.save_entry(message.author.id, f"DELETED: {message.content}", 'DELETE')

async def setup(bot):
    await bot.add_cog(ProductivityTracker(bot))

