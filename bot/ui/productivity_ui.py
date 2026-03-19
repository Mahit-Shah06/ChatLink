import discord
import os

class ProductivityRoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # Persistent

    @discord.ui.button(
        label="🔔 Get Reminders", 
        style=discord.ButtonStyle.success, 
        custom_id="prod_remind_btn"
    )
    async def toggle_reminder(self, interaction: discord.Interaction, button: discord.ui.button):
        role_id = int(os.getenv("PRODUCTIVITY_ROLE_ID"))
        role = interaction.guild.get_role(role_id)
        
        if not role:
            return await interaction.response.send_message("❌ Reminder role not found.", ephemeral=True)

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message("🔕 You will no longer receive daily reminders.", ephemeral=True)
        else:
            await interaction.user.add_roles(role)
            await interaction.response.send_message("🔔 You've joined the Productivity Gang! See you at 11 PM IST.", ephemeral=True)
