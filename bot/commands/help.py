import logging

import discord
from discord.ext import commands

log = logging.getLogger("chatlink.help")

# Display names for the cogs. A cog missing from here still shows up, using its
# class name — the list is presentation only, never a filter, so a new cog can
# never go missing from help by being forgotten here.
COG_META = {
    "ServerLogging": ("\U0001F4DC", "Server Logging", 20),
    "AdminCommands": ("\U0001F6E1\uFE0F", "Moderation & Utility", 30),
    "SecretSanta":   ("\U0001F381", "Secret Santa", 40),
    "Caller":        ("\U0001F4DE", "Voice", 50),
    "Retard":        ("\U0001F3B2", "Fun", 60),
    "Help":          ("\u2753", "Help", 99),
}
DEFAULT_META = ("⚙️", "Other", 90)


class Help(commands.Cog):
    """Command reference.

    Built by walking the commands the bot has actually registered, rather than
    from a hardcoded list. The old version advertised !cb, !gp, !rp and !capi,
    none of which were loaded — anyone following it got silence. A generated
    help cannot drift from reality.
    """

    def __init__(self, bot):
        self.bot = bot
        bot.remove_command("help")

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _meta(cog_name: str):
        return COG_META.get(cog_name, DEFAULT_META)

    @staticmethod
    def _signature(command: commands.Command) -> str:
        params = []
        for name, param in command.clean_params.items():
            optional = param.default is not param.empty
            params.append(f"[{name}]" if optional else f"<{name}>")
        return f"`!{command.qualified_name}{' ' + ' '.join(params) if params else ''}`"

    @staticmethod
    def _summary(command: commands.Command) -> str:
        text = command.short_doc or command.help or "No description yet."
        return text.strip().split("\n")[0]

    @staticmethod
    def _needs_admin(command: commands.Command) -> bool:
        for check in getattr(command, "checks", []):
            if "has_permissions" in repr(check) or "administrator" in repr(check):
                return True
        return False

    def _visible_commands(self):
        seen = set()
        for command in self.bot.walk_commands():
            if command.hidden or command.qualified_name in seen:
                continue
            seen.add(command.qualified_name)
            yield command

    # ------------------------------------------------------------ commands
    @commands.hybrid_command(name="help")
    async def help_command(self, ctx, command: str = None):
        """Show every available command, or details for one of them."""
        if command:
            return await self._send_detail(ctx, command)
        await self._send_overview(ctx)

    async def _send_overview(self, ctx):
        groups: dict[str, list[commands.Command]] = {}
        for cmd in self._visible_commands():
            cog_name = cmd.cog_name or "Other"
            groups.setdefault(cog_name, []).append(cmd)

        embed = discord.Embed(
            title="ChatLink commands",
            description=(
                "Prefix every command with `!`, or use the slash version.\n"
                "Run `!help <command>` for details on any one of them."
            ),
            color=0x00FFAA,
        )

        ordered = sorted(groups.items(), key=lambda kv: (self._meta(kv[0])[2], kv[0]))
        total = 0
        for cog_name, cmds in ordered:
            emoji, label, _ = self._meta(cog_name)
            lines = []
            for cmd in sorted(cmds, key=lambda c: c.qualified_name):
                admin = " 🛡️" if self._needs_admin(cmd) else ""
                lines.append(f"`!{cmd.qualified_name}`{admin} — {self._summary(cmd)}")
                total += 1
            embed.add_field(name=f"{emoji} {label}", value="\n".join(lines), inline=False)

        embed.set_footer(text=f"{total} commands available · 🛡️ = admin only")
        await ctx.send(embed=embed)

    async def _send_detail(self, ctx, name: str):
        cmd = self.bot.get_command(name.lstrip("!").strip())
        if cmd is None or cmd.hidden:
            embed = discord.Embed(
                title="No such command",
                description=f"`{name}` isn't a command. Run `!help` to see what is.",
                color=0xFF5555,
            )
            return await ctx.send(embed=embed)

        emoji, label, _ = self._meta(cmd.cog_name or "Other")
        embed = discord.Embed(
            title=f"!{cmd.qualified_name}",
            description=(cmd.help or cmd.short_doc or "No description yet.").strip(),
            color=0x00FFAA,
        )
        embed.add_field(name="Usage", value=self._signature(cmd), inline=False)

        if cmd.aliases:
            embed.add_field(
                name="Also known as",
                value=", ".join(f"`!{a}`" for a in cmd.aliases),
                inline=False,
            )
        if self._needs_admin(cmd):
            embed.add_field(name="Permissions", value="Administrator", inline=False)

        embed.set_footer(text=f"{emoji} {label}")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Help(bot))
