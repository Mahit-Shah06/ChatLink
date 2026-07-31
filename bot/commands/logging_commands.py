import logging

import discord
from discord.ext import commands

from bot.core.state_manager import state
from bot.logging.channel_resolver import CHANNEL_MAP
from bot.logging.log_types import LogType

log = logging.getLogger("chatlink.logsetup")


class ServerLogging(commands.Cog):
    """Server logging setup and control.

    Split out of AdminCommands. The command names are unchanged — !setup_logs,
    !toggle_logs, !logs — but they now live in a cog of their own, so help
    files them under "Server Logging" instead of burying them in a list of
    moderation tools.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup_logs(self, ctx):
        """Create the log category and channels, hidden from everyone but admins."""
        guild = ctx.guild
        category_name = "SERVER LOGS"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(
                view_channel=True, send_messages=True, embed_links=True
            ),
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

        # logger.py caches channel lookups by name; new channels invalidate that.
        if hasattr(self.bot, "logger_instance"):
            self.bot.logger_instance.invalidate_cache(guild.id)

        summary = ", ".join(f"#{c}" for c in created) if created else "all already existed"
        embed = discord.Embed(
            title="✅ Logging setup complete",
            description=f"**Server:** {guild.name}\n**Created:** {summary}",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Run !logs to see what's currently enabled")
        await ctx.send(embed=embed)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def toggle_logs(self, ctx, log_type: str):
        """Turn one log type on or off. Try: !toggle_logs MESSAGE"""
        try:
            lt = LogType[log_type.upper()]
        except KeyError:
            valid = ", ".join(f"`{t.name}`" for t in LogType)
            return await ctx.send(f"❌ Unknown log type. Valid options: {valid}")

        new_state = state.toggle(ctx.guild.id, lt)
        status = "enabled ✅" if new_state else "disabled ❌"
        await ctx.send(f"`{lt.name}` logging is now **{status}**.")

    @commands.command()
    async def logs(self, ctx):
        """Show which logs are on and where they're being sent."""
        guild = ctx.guild
        rows, missing = [], 0

        for lt in LogType:
            enabled = state.is_enabled(guild.id, lt)
            channel_id = state.get_log_channel(guild.id, lt)
            channel = guild.get_channel(channel_id) if channel_id else None

            if channel:
                destination = channel.mention
            else:
                destination = "*not set up*"
                missing += 1

            rows.append(f"{'✅' if enabled else '❌'} `{lt.name:<8}` → {destination}")

        active = sum(1 for lt in LogType if state.is_enabled(guild.id, lt))

        embed = discord.Embed(
            title="📜 Logging status",
            description="\n".join(rows),
            color=discord.Color.green() if active else discord.Color.greyple(),
        )

        if missing:
            embed.add_field(
                name="Not configured",
                value=f"{missing} log type(s) have no channel. Run `!setup_logs`.",
                inline=False,
            )

        embed.add_field(
            name="Controls",
            value="`!setup_logs` — create the channels\n"
                  "`!toggle_logs <TYPE>` — switch one on or off",
            inline=False,
        )
        embed.set_footer(text=f"{active} of {len(LogType)} log types active in {guild.name}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ServerLogging(bot))
