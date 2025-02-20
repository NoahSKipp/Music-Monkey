# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 02.12.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from services.report_service import handle_report_error

class ReportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="report", description="Submit an error report.")
    async def report(self, interaction: discord.Interaction):
        await handle_report_error(interaction)

async def setup(bot):
    await bot.add_cog(ReportCog(bot))
