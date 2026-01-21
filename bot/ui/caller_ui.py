import discord

class JoinCallView(discord.ui.View):
    def __init__(self, guild_id: int, channel_id: int):
        super().__init__(timeout=300)

        self.guild_id = guild_id
        self.channel_id = channel_id

    @discord.ui.button(
        label="📞 Join Call",
        style=discord.ButtonStyle.success
    )
    async def join_call(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):
        url = f"https://discord.com/channels/{self.guild_id}/{self.channel_id}"
        await interaction.response.send_message(
            f"👉 Click here to join the call:\n{url}",
            ephemeral=True
        )
