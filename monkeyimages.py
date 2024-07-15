# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import random

class MonkeyImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="monkey", description="Send a random picture of a monkey")
    async def monkey(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        width = 500
        height = 350
        random_value = random.randint(1, 1000)  # Generate a random value between 1 and 1000

        url = f"https://placemonkeys.com/{width}/{height}?random={random_value}"

        embed = discord.Embed(
            title="Here's a random monkey picture for you! <a:monkeyflip:1237140606296522762>",
            color=discord.Color.green()
        )
        embed.set_image(url=url)
        await interaction.followup.send(embed=embed, ephemeral=False)

async def setup(bot):
    await bot.add_cog(MonkeyImages(bot))
