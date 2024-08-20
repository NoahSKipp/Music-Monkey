# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.05.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands
from services.broadcast_service import BroadcastService
from utils.interaction_checks import can_manage_roles


class BroadcastCog(commands.GroupCog, group_name="updates"):
    def __init__(self, bot):
        self.bot = bot
        self.service = BroadcastService(bot)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Log that a message was received
        self.service.logger.debug(
            f"Received message from {message.author} in {message.guild or 'DM'}: {message.content}")

        # Ensure that this is not the bot's own message
        if message.author.bot:
            return

        # Handle the broadcast message if it's from a creator in DMs
        await self.service.handle_creator_message(message)

    @app_commands.command(name="toggle", description="Enable or disable updates for this server")
    @app_commands.choices(choice=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
    ])
    async def updates(self, interaction: discord.Interaction, choice: str):
        if await can_manage_roles(interaction):
            await self.service.toggle_updates(interaction, choice)

    @app_commands.command(name="set", description="Set the current channel as the updates channel")
    async def updates_set(self, interaction: discord.Interaction):
        if await can_manage_roles(interaction):
            await self.service.set_updates_channel(interaction)


async def setup(bot):
    await bot.add_cog(BroadcastCog(bot))
