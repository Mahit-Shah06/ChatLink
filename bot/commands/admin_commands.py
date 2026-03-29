import discord
from discord.ext import commands
from bot.logging.log_types import LogType
from bot.logging.channel_resolver import CHANNEL_MAP
from bot.core.state_manager import state


class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, count: int = 1):
        count = min(count, 50)
        await ctx.channel.purge(limit=count + 1)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔒 Channel locked.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔓 Channel unlocked.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        embed = discord.Embed(title="📢 Announcement", description=message, color=0xffcc00)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_logs(self, ctx):
        guild = ctx.guild
        category_name = "SERVER LOGS"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, embed_links=True)
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True)

        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name, overwrites=overwrites)

        created = []
        for log_type, channel_name in CHANNEL_MAP.items():
            channel = discord.utils.get(category.text_channels, name=channel_name)
            if not channel:
                channel = await guild.create_text_channel(channel_name, category=category)
                created.append(channel_name)
            state.set_log_channel(guild.id, log_type, channel.id)

        summary = ", ".join(f"#{c}" for c in created) if created else "all already existed"
        embed = discord.Embed(
            title="✅ Logging Setup Complete",
            description=f"**Guild:** {guild.name}\n**Channels:** {summary}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def toggle_logs(self, ctx, log_type: str):
        try:
            lt = LogType[log_type.upper()]
        except KeyError:
            valid = ", ".join(t.name for t in LogType)
            await ctx.send(f"❌ Unknown log type. Valid: `{valid}`")
            return
        new_state = state.toggle(ctx.guild.id, lt)
        status = "ENABLED ✅" if new_state else "DISABLED ❌"
        await ctx.send(f"Log type `{lt.name}` is now **{status}** for **{ctx.guild.name}**")

    @commands.group(invoke_without_command=True)
    async def logs(self, ctx):
        types_status = []
        for lt in LogType:
            enabled = state.is_enabled(ctx.guild.id, lt)
            types_status.append(f"{'✅' if enabled else '❌'} `{lt.name}`")
        embed = discord.Embed(title="📜 Logging System", color=discord.Color.blue())
        embed.add_field(name=f"Log Types — {ctx.guild.name}", value="\n".join(types_status), inline=False)
        embed.add_field(name="Commands", value="`!setup_logs`\n`!toggle_logs <TYPE>`", inline=False)
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def create_role(self, ctx, *, role_name: str):
        role = await ctx.guild.create_role(name=role_name)
        await ctx.send(f"✅ Created role **{role.name}**\n🆔 ID: `{role.id}`")

    @commands.hybrid_command(name="servericon", description="Get the server's icon")
    async def servericon(self, ctx):
        if not ctx.guild.icon:
            await ctx.send("❌ This server doesn't have an icon set.")
            return
        embed = discord.Embed(title=f"{ctx.guild.name}'s Server Icon", color=discord.Color.blurple())
        embed.set_image(url=ctx.guild.icon.with_size(4096).url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="pfp", description="Get a user's profile picture")
    async def pfp(self, ctx, user: discord.Member = None):
        user = user or ctx.author
        embed = discord.Embed(title=f"{user.display_name}'s Profile Picture", color=discord.Color.blurple())
        embed.set_image(url=user.display_avatar.with_size(4096).url)
        embed.set_footer(text=f"Requested by {ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AdminCommands(bot))