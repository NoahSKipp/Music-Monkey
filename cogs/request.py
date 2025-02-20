# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 19.12.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.request_service import handle_request_feature

class RequestCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="request", description="Submit a feature request.")
    async def request(self, interaction: discord.Interaction):
        await handle_request_feature(interaction)

async def setup(bot):
    await bot.add_cog(RequestCog(bot))
