import discord, json, os
from discord.ext import commands

SESSION_FILE = "storage/sessions.json"

def is_owner(user_id, channel_id):
    if not os.path.exists(SESSION_FILE):
        return False
    sessions = json.load(open(SESSION_FILE))
    return sessions.get(str(user_id), {}).get("channel_id") == channel_id

class SessionPerms(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def gp(self, ctx, member: discord.Member):
        if not is_owner(ctx.author.id, ctx.channel.id):
            return await ctx.reply("❌ Only the session owner can grant access.")
        await ctx.channel.set_permissions(member, view_channel=True, send_messages=True)
        await ctx.reply(f"✅ {member.mention} granted access.")

    @commands.command()
    async def rp(self, ctx, member: discord.Member):
        if not is_owner(ctx.author.id, ctx.channel.id):
            return await ctx.reply("❌ Only the session owner can revoke access.")
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.reply(f"🗑️ {member.mention} access revoked.")

    @commands.command()
    async def rpall(self, ctx):
        if not is_owner(ctx.author.id, ctx.channel.id):
            return await ctx.reply("❌ Only the session owner.")
        for m in ctx.channel.overwrites:
            if isinstance(m, discord.Member) and m != ctx.author:
                await ctx.channel.set_permissions(m, overwrite=None)
        await ctx.reply("🚫 Everyone removed except you.")

    @commands.command()
    async def delete(self, ctx):
        if not is_owner(ctx.author.id, ctx.channel.id):
            return await ctx.reply("❌ Not your session.")

        sessions = json.load(open(SESSION_FILE))
        sessions.pop(str(ctx.author.id), None)
        json.dump(sessions, open(SESSION_FILE, "w"), indent=4)

        await ctx.channel.delete()

async def setup(bot):
    await bot.add_cog(SessionPerms(bot))
