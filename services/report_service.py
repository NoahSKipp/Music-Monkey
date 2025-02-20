# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 02.12.2024                    #
# ========================================= #

import discord
import config

GUILD_ID = config.DEV_GUILD_ID
CHANNEL_ID = config.DEV_REPORT_CHANNEL_ID

class ErrorReportModal(discord.ui.Modal, title="Submit Error Report"):
    error_message = discord.ui.TextInput(
        label="Error Message",
        style=discord.TextStyle.long,
        placeholder="Describe the error you encountered, including links to screenshots if possible.",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handles the submission of the modal."""
        embed = discord.Embed(
            title="New Error Report",
            description=self.error_message.value,
            color=discord.Color.red(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar.url)
        embed.timestamp = discord.utils.utcnow()

        guild = interaction.client.get_guild(GUILD_ID)
        if guild:
            channel = guild.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
                await interaction.response.send_message("Your error report has been submitted. Thank you!",
                                                        ephemeral=True)
            else:
                await interaction.response.send_message("Unable to find the reporting channel. Please try again later.",
                                                        ephemeral=True)
        else:
            await interaction.response.send_message("Unable to find the guild. Please try again later.", ephemeral=True)


async def handle_report_error(interaction: discord.Interaction):
    """Handles the /report_error command."""
    # Directly show the modal without deferring the interaction
    modal = ErrorReportModal()
    await interaction.response.send_modal(modal)


