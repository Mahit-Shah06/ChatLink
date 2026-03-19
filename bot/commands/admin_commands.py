import discord
from discord.ext import commands
from bot.logging.log_types import LogType
from bot.logging.channel_resolver import CHANNEL_MAP
from bot.core.state_manager import state

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ---------- PURGE ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def purge(self, ctx, count: int = 1):
        """
        Delete last N messages (max 50)
        """
        count = min(count, 50)
        await ctx.channel.purge(limit=count + 1)

    # ---------- LOCK CHANNEL ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def lock(self, ctx):
        """
        Lock current channel (no one can send messages)
        """
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔒 Channel locked.")

    # ---------- UNLOCK CHANNEL ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def unlock(self, ctx):
        """
        Unlock current channel
        """
        overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.reply("🔓 Channel unlocked.")

    # ---------- ANNOUNCE ----------
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def announce(self, ctx, *, message: str):
        """
        Send announcement embed
        """
        embed = discord.Embed(
            title="📢 Announcement",
            description=message,
            color=0xffcc00
        )
        await ctx.send(embed=embed)

    # ---------- LOGS ----------
    @commands.command()
    @commands.has_permissions(administrator = True)
    async def setup_logs(self, ctx):
        category_name = "SERVER LOGS"

        overwrites = {
                ctx.guild.default_role: discord.PermissionOverwrite(view_channel = False),
                ctx.guild.me: discord.PermissionOverwrite(
                    view_channel=True, 
                    send_messages=True, 
                    embed_links=True
                )
        }

        for role in ctx.guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(view_channel = True)

        category = discord.utils.get(ctx.guild.categories, name = category_name)
        if not category:
            category  = await ctx.guild.create_category(category_name, overwrites = overwrites)

        for log_type, channel_name in CHANNEL_MAP.items():
            channel = discord.utils.get(category.text_channels, name = channel_name)
            if not channel:
                await ctx.guild.create_text_channel(channel_name, category = category)

            state.log_channels[log_type] = channel.id

            await ctx.send("Logs Category created")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def toggle_logs(self, ctx, log_type: LogType):
        """
        Toggles a specific log type and returns the new status.
        """
        # Ensure we use the correct instance name 'logger_instance'
        logger = self.bot.logger_instance
        
        # Update the toggle in memory
        current_state = logger.toggles.get(log_type, True)
        logger.toggles[log_type] = not current_state
        
        status = "ENABLED ✅" if not current_state else "DISABLED ❌"
        await ctx.send(f"Log type `{log_type.name}` has been toggled to: **{status}**")

    @commands.group(invoke_without_command=True)
    async def logs(self, ctx):
        """Help command for logs: Shows available types and current status."""
        types = ", ".join([t.name for t in LogType])
        embed = discord.Embed(title="📜 Logging System Help", color=discord.Color.blue())
        embed.add_field(name="Available Log Types", value=f"`{types}`")
        embed.add_field(name="Commands", value="`!setup_logs` - Initialize channels\n`!toggle_logs <TYPE>` - Enable/Disable", inline=False)
        await ctx.send(embed=embed)

    # ---------- Create Role ----------
    @commands.command()
    @commands.has_permissions(administrator = True)
    async def create_role(self, ctx, *, role_name: str):
        role = await ctx.guild.create_role(name = role_name)
        await ctx.send(f"✅ Created role **{role.name}**\n🆔 ID: `{role.id}`")

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
