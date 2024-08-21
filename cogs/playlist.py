# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 13.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
from services.playlist_service import PlaylistService
from utils.embeds import create_error_embed
from utils.logging import get_logger

logger = get_logger(__name__)

class Playlist(commands.GroupCog, group_name="playlist"):
    def __init__(self, bot):
        self.bot = bot
        self.service = PlaylistService(bot)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="create", description="Create a new playlist")
    @app_commands.describe(name="Name of the playlist", privacy="Privacy of the playlist (Public/Private)")
    async def create(self, interaction: discord.Interaction, name: str, privacy: str = "public"):
        await interaction.response.defer(ephemeral=True)
        await self.service.create_playlist(interaction, name, privacy)

    @create.error
    async def create_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="add", description="Add a song to a playlist")
    @app_commands.describe(name="Name of the playlist", query="Song to add")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def add(self, interaction: discord.Interaction, name: str, query: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.add_song_to_playlist(interaction, name, query)

    @add.error
    async def add_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="remove", description="Remove a song from a playlist")
    @app_commands.describe(name="Name of the playlist", query="Song to remove")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def remove(self, interaction: discord.Interaction, name: str, query: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.remove_song_from_playlist(interaction, name, query)

    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="dedupe", description="Remove duplicate songs from a playlist")
    @app_commands.describe(name="Name of the playlist")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def dedupe(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.dedupe_playlist(interaction, name)

    @dedupe.error
    async def dedupe_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="view", description="View a playlist")
    @app_commands.describe(name="Name of the playlist")
    async def view(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.view_playlist(interaction, name)

    @view.error
    async def view_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="guildview", description="View all playlists in the current guild")
    async def guildview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.service.view_guild_playlists(interaction)

    @guildview.error
    async def guildview_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="edit", description="Edit a playlist's settings")
    @app_commands.describe(name="Name of the playlist")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def edit(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.edit_playlist(interaction, name)

    @edit.error
    async def edit_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="invite", description="Invite a user to a playlist")
    @app_commands.describe(name="Name of the playlist", user="User to invite")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def invite(self, interaction: discord.Interaction, name: str, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        await self.service.invite_user_to_playlist(interaction, name, user)

    @invite.error
    async def invite_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="invites", description="View your playlist invites")
    async def invites(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await self.service.view_user_invites(interaction)

    @invites.error
    async def invites_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="play", description="Play all songs from a playlist")
    @app_commands.describe(name="Name of the playlist")
    @app_commands.autocomplete(name=PlaylistService.play_playlist_autocomplete)
    async def play(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.play_playlist(interaction, name)

    @play.error
    async def play_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name="delete", description="Delete a playlist")
    @app_commands.describe(name="Name of the playlist")
    @app_commands.autocomplete(name=PlaylistService.playlist_autocomplete)
    async def delete(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        await self.service.delete_playlist(interaction, name)

    @delete.error
    async def delete_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Error handler for the entire cog
    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        embed = None
        if isinstance(error, app_commands.CommandOnCooldown):
            embed = create_error_embed(
                f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
            )
        else:
            # Log the error details using your custom logger
            logger.error(f"Error in command '{interaction.command.name}': {error}")
            logger.exception("An unexpected error occurred.")  # This logs the traceback

            embed = create_error_embed(
                "An error occurred while processing the command."
            )

        # Check if the interaction has already been responded to
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)


# Setup function to add this cog to the bot
async def setup(bot):
    await bot.add_cog(Playlist(bot))
