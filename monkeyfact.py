# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import logging
import config
import aiohttp

# API key for Google Gemini
genai.configure(api_key=config.GEMINI)

class MonkeyFactCog(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        discord.utils.setup_logging(level=logging.INFO)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.followup.send(
                f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "An error occurred while processing the command.",
                ephemeral=True
            )

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='fact', description='Get a random fact about monkeys.')
    async def fact(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            # Prompt to generate a random fact about monkeys
            prompt = "Tell me a random fact about monkeys."

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]

            model = genai.GenerativeModel(model_name="gemini-1.0-pro", safety_settings=safety_settings)
            convo = model.start_chat(history=[])
            convo.send_message(prompt)
            response = convo.last.text

            embed = discord.Embed(
                title="Monkey Fact <a:monkeyflip:1237140606296522762>",
                description=response,
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
        except Exception as e:
            await self.error_handler(interaction, e)

    @fact.error
    async def fact_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

async def setup(bot):
    await bot.add_cog(MonkeyFactCog(bot))
