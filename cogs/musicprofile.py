# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 07.05.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.profile_service import ProfileService
from utils.embeds import create_error_embed
from utils.logging import get_logger

class MusicProfile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = ProfileService(bot)
        self.logger = get_logger(__name__)  # Initialize the logger

    @app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='profile', description='Displays a music profile for you or another user')
    @app_commands.describe(user="The user whose music profile you want to view")
    async def music_profile(self, interaction: discord.Interaction, user: discord.User = None):
        await interaction.response.defer(ephemeral=True)
        await self.service.show_profile(interaction, user)  # Pass interaction to service method

    @music_profile.error
    async def music_profile_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='leaderboard', description='Show the music leaderboard for this server')
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.service.show_leaderboard(interaction)  # Pass interaction to service method

    @leaderboard.error
    async def leaderboard_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        try:
            if isinstance(error, app_commands.CommandOnCooldown):
                embed = create_error_embed(
                    f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
                )
                self.logger.warning(f"Command cooldown triggered by {interaction.user}: {interaction.command.name}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                self.logger.error(f"Error in command '{interaction.command.name}': {str(error)}")
                embed = create_error_embed(
                    "An error occurred while processing the command."
                )

                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error occurred in error handler: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=create_error_embed("A severe error occurred."),
                                                        ephemeral=True)
            else:
                await interaction.followup.send(embed=create_error_embed("A severe error occurred."), ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicProfile(bot))
