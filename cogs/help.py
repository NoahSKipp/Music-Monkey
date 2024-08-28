# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 08.05.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.help_service import HelpService


class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_service = HelpService(bot)

    @app_commands.command(name='help', description='See all commands')
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.help_service.send_help_message(interaction)

    async def select_callback(self, interaction: discord.Interaction):
        await self.help_service.select_callback(interaction)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
