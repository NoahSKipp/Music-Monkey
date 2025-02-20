# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 19.12.2024                    #
# ========================================= #

import discord
import config

GUILD_ID = config.GUILD_ID
CHANNEL_ID = config.DEV_REQUEST_CHANNEL_ID

class FeatureRequestModal(discord.ui.Modal, title="Submit Feature Request"):
    request_message = discord.ui.TextInput(
        label="Feature Request",
        style=discord.TextStyle.long,
        placeholder="Describe the feature you'd like to see implemented.",
        required=True,
        max_length=1000,
    )

    async def on_submit(self, interaction: discord.Interaction):
        """Handles the submission of the modal."""
        embed = discord.Embed(
            title="New Feature Request",
            description=self.request_message.value,
            color=discord.Color.blue(),
        )
        embed.set_author(name=interaction.user, icon_url=interaction.user.avatar.url)
        embed.timestamp = discord.utils.utcnow()

        guild = interaction.client.get_guild(GUILD_ID)
        if guild:
            channel = guild.get_channel(CHANNEL_ID)
            if channel:
                await channel.send(embed=embed)
                await interaction.response.send_message("Your feature request has been submitted. Thank you!",
                                                        ephemeral=True)
            else:
                await interaction.response.send_message("Unable to find the feature request channel. Please try again later.",
                                                        ephemeral=True)
        else:
            await interaction.response.send_message("Unable to find the guild. Please try again later.", ephemeral=True)


async def handle_request_feature(interaction: discord.Interaction):
    """Handles the /request_feature command."""
    # Directly show the modal without deferring the interaction
    modal = FeatureRequestModal()
    await interaction.response.send_modal(modal)
