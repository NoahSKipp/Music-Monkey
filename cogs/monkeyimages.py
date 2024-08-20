# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.monkey_service import MonkeyService
from utils.embeds import create_error_embed
from utils.logging import get_logger

logger = get_logger(__name__)

class MonkeyImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = MonkeyService(bot)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        logger.error(f"Command error: {error}")
        embed = create_error_embed("An error occurred while processing the command.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="monkey", description="Send a random picture of a monkey")
    async def monkey(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.service.get_monkey_image(interaction)

    @monkey.error
    async def monkey_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

async def setup(bot):
    await bot.add_cog(MonkeyImages(bot))
