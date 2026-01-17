import discord
from memory.api_key_service import APIKeyService

keys = APIKeyService()

class APIKeyModal(discord.ui.Modal):
    def __init__(self, provider):
        super().__init__(title=f"Add {provider} API Key")
        self.provider = provider
        self.key = discord.ui.TextInput(label="API Key", style=discord.TextStyle.long)
        self.add_item(self.key)

    async def on_submit(self, interaction):
        keys.save_key(interaction.user.id, self.provider, self.key.value)
        await interaction.response.send_message("✅ Saved", ephemeral=True)

class APIKeyView(discord.ui.View):
    @discord.ui.button(label="OpenAI", style=discord.ButtonStyle.primary)
    async def openai(self, i, _):
        await i.response.send_modal(APIKeyModal("openai"))

    @discord.ui.button(label="Gemini", style=discord.ButtonStyle.success)
    async def gemini(self, i, _):
        await i.response.send_modal(APIKeyModal("gemini"))
