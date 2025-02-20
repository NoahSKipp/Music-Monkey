# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 17.12.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.recap_service import RecapService

class Recap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = RecapService(bot)

    @app_commands.command(name="recap", description="View your personalized music recap!")
    async def recap(self, interaction: discord.Interaction):
        """Handle the /recap command."""
        await self.service.generate_recap(interaction)

async def setup(bot: commands.Bot):
    await bot.add_cog(Recap(bot))
