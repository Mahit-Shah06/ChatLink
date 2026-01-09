import discord
from discord import ui
from bot.services.api_key_service import APIKeyService

api_keys = APIKeyService()


class APIKeyModal(ui.Modal, title="Enter Your OpenAI API Key"):

    api_key = ui.TextInput(
        label="OpenAI API Key",
        placeholder="sk-xxxxxxxxxxxxxxxxx",
        style=discord.TextStyle.short,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        api_keys.save_key(interaction.user.id, self.api_key.value)

        await interaction.response.send_message(
            "🔐 Your API key has been securely saved.",
            ephemeral=True,
            delete_after=5
        )


class APIKeyView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Enter API Key", style=discord.ButtonStyle.primary)
    async def enter_key(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(APIKeyModal())
