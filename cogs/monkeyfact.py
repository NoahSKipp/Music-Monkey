# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.07.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from services.monkey_service import MonkeyService
from utils.logging import get_logger

# Get the logger for this module
logger = get_logger(__name__)

class MonkeyFactCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.monkey_service = MonkeyService(bot)

    @app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='fact', description='Get a random fact about monkeys.')
    async def fact(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            await self.monkey_service.get_monkey_fact(interaction)
        except Exception as e:
            logger.error(f"Error processing monkey fact command: {e}")
            await self.error_handler(interaction, e)

    async def error_handler(self, interaction: Interaction, error: app_commands.AppCommandError):
        from utils.embeds import create_error_embed

        if isinstance(error, app_commands.CommandOnCooldown):
            embed = create_error_embed(
                error_message=f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            embed = create_error_embed(
                error_message="An error occurred while processing the command."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @fact.error
    async def fact_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        logger.error(f"Command error in 'fact': {error}")
        await self.error_handler(interaction, error)

async def setup(bot):
    await bot.add_cog(MonkeyFactCog(bot))
