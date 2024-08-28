# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 07.05.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from services.recommend_service import RecommendService
from utils.embeds import create_error_embed
from utils.logging import get_logger

class RecommendCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.recommend_service = RecommendService(bot)
        self.logger = get_logger(__name__)  # Initialize the logger

    @app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='recommend', description='Get song recommendations based on the current queue.')
    async def recommend(self, interaction: Interaction):
        await self.recommend_service.recommend_songs(interaction)

    @recommend.error
    async def recommend_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    async def error_handler(self, interaction: Interaction, error: app_commands.AppCommandError):
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
    await bot.add_cog(RecommendCog(bot))
