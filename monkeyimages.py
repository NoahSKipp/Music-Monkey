# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import random
import database as db
import logging

class MonkeyImages(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')
        await db.enter_guild(interaction.guild_id)
        await db.enter_user(interaction.user.id, interaction.guild_id)
        dj_only = await db.get_dj_only_enabled(interaction.guild_id)
        dj_role_id = await db.get_dj_role(interaction.guild_id)

        if not dj_only:
            return True

        has_permissions = interaction.user.guild_permissions.manage_roles
        is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

        if has_permissions or is_dj:
            return True

        await interaction.response.send_message(
            "DJ-only mode is enabled. You need DJ privileges to use this.",
            ephemeral=True
        )
        return False

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error occurred while processing the command.",
                ephemeral=True
            )

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="monkey", description="Send a random picture of a monkey")
    async def monkey(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        width = 500
        height = 350
        random_value = random.randint(1, 1000)  # Generate a random value between 1 and 1000

        url = f"https://placemonkeys.com/{width}/{height}?random={random_value}"

        embed = discord.Embed(
            title="Here's a random monkey picture for you! <a:monkeyflip:1237140606296522762>",
            color=discord.Color.gold()
        )
        embed.set_image(url=url)
        await interaction.followup.send(embed=embed, ephemeral=False)

    @monkey.error
    async def monkey_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

async def setup(bot):
    await bot.add_cog(MonkeyImages(bot))
