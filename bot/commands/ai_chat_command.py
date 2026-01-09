from discord.ext import commands
from bot.services.ai_chat_service import AIChatService


class AIChatCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ai = AIChatService()

    @commands.command(name="ai")
    async def ai(self, ctx: commands.Context, *, message: str = None):
        if not message:
            return await ctx.reply("Talk to me. Don’t just stare.")

        try:
            reply = self.ai.generate_reply(ctx.author.id, message)
            await ctx.reply(reply)
        except Exception as e:
            await ctx.reply("❌ AI failed. Skill issue.")
