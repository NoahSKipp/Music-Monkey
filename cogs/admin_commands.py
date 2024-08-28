# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 31.07.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from services.admin_service import AdminService
from utils.embeds import create_basic_embed, create_error_embed
from utils.logging import get_logger

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = AdminService(bot)
        self.logger = get_logger(__name__)  # Initialize the logger

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='botinfo', description='Displays bot information')
    async def botinfo(self, interaction: Interaction):
        await self.service.botinfo(interaction)

    @botinfo.error
    async def botinfo_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        try:
            if isinstance(error, app_commands.CommandOnCooldown):
                embed = create_error_embed(
                    error_message=f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
                )
                self.logger.warning(f"Command cooldown triggered by {interaction.user}: {interaction.command.name}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                self.logger.error(f"Error in command '{interaction.command.name}': {str(error)}")
                embed = create_error_embed(
                    error_message="An error occurred while processing the command."
                )

                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error occurred in error handler: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=create_error_embed("A severe error occurred."),
                                                        ephemeral=True)
            else:
                await interaction.followup.send(embed=create_error_embed("A severe error occurred."), ephemeral=True)

class DJCommands(commands.GroupCog, group_name="dj"):
    def __init__(self, bot):
        self.bot = bot
        self.service = AdminService(bot)  # Use the same service as AdminCommands
        self.logger = get_logger(__name__)  # Initialize the logger

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='list', description='Displays the list of DJ commands')
    async def restricted(self, interaction: Interaction):
        await self.service.restricted(interaction)

    @restricted.error
    async def restricted_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='add', description='Add a command to the DJ list')
    @app_commands.describe(command='Name of the command to restrict')
    @app_commands.autocomplete(command=AdminService.autocomplete_command)
    async def add(self, interaction: Interaction, command: str):
        await self.service.add_command(interaction, command)

    @add.error
    async def add_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='remove', description='Remove a command from the DJ restricted list')
    @app_commands.describe(command='Name of the command to unrestrict')
    @app_commands.autocomplete(command=AdminService.autocomplete_command)
    async def remove(self, interaction: Interaction, command: str):
        await self.service.remove_command(interaction, command)

    @remove.error
    async def remove_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='toggle', description='Toggle DJ-only command restrictions')
    async def toggle_dj_mode(self, interaction: Interaction):
        await self.service.toggle_dj_mode(interaction)

    @toggle_dj_mode.error
    async def toggle_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='set', description='Set a DJ role')
    @app_commands.describe(role='Select a DJ role')
    @app_commands.autocomplete(role=AdminService.autocomplete_role)
    async def set_dj_role(self, interaction: Interaction, role: str):
        await self.service.set_dj_role(interaction, role)

    @set_dj_role.error
    async def set_role_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        self.logger.error(
            f"Error encountered in command '{interaction.command.name}' invoked by '{interaction.user}': {error}")

        if isinstance(error, app_commands.CommandOnCooldown):
            self.logger.warning(
                f"Command '{interaction.command.name}' is on cooldown for {error.retry_after:.2f} seconds.")

            embed = create_error_embed(
                error_message=f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            self.logger.error(f"An unexpected error occurred in command '{interaction.command.name}': {str(error)}")

            embed = create_error_embed(
                error_message="An error occurred while processing the command."
            )

            if not interaction.response.is_done():
                self.logger.debug("Sending error response through interaction.response.send_message.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                self.logger.debug("Sending error response through interaction.followup.send.")
                await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
    await bot.add_cog(DJCommands(bot))
