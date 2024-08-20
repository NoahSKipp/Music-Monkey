# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 07.05.2024                    #
# ========================================= #

import discord
from utils.embeds import create_basic_embed, create_error_embed
from utils.voting_checks import has_voted
from utils.interaction_checks import restriction_check
from utils.logging import get_logger
from database import database as db

logger = get_logger(__name__)


class ProfileService:
    def __init__(self, bot):
        self.bot = bot

    async def show_profile(self, interaction: discord.Interaction, user: discord.User = None):
        # Perform the restriction check to ensure the user has permission to use this command
        if not await restriction_check(interaction):
            return

        # Check if the user has voted; if not, prompt them to do so
        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        try:
            if user is None:
                user = interaction.user  # Default to the interaction's user if no user is specified

            user_id = user.id
            profile = await db.get_user_stats(user_id)  # Retrieve user stats from the database
            if profile:
                # Create and populate an embed with the user's music profile details
                embed = create_basic_embed(
                    title=f"🎶 {user.display_name}'s Music Profile 🎶",
                    description=""
                )
                embed.set_thumbnail(url=user.display_avatar.url)
                embed.add_field(name="🎤 Top Artist", value=profile['top_artist'], inline=False)
                embed.add_field(name="🎵 Top Song", value=profile['top_song'], inline=False)
                embed.add_field(name="🔢 Total Songs Played", value=str(profile['total_songs_played']), inline=True)
                embed.add_field(name="⏳ Total Hours Played", value=f"{profile['total_hours_played']:.2f} hours",
                                inline=True)

                embed.set_footer(text="Music Profile", icon_url=self.bot.user.display_avatar.url)
                embed.timestamp = discord.utils.utcnow()

                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                # Handle the case where no profile data is found for the user
                await interaction.followup.send(
                    embed=create_error_embed(f"No music profile found for {user.display_name}."))
        except Exception as e:
            # Log the error and inform the user if something goes wrong
            logger.error(f"Error retrieving music profile: {e}")
            await interaction.followup.send(
                embed=create_error_embed("An error occurred while retrieving the music profile."))

    async def show_leaderboard(self, interaction: discord.Interaction):
        # Perform the restriction check to ensure the user has permission to use this command
        if not await restriction_check(interaction):
            return

        # Check if the user has voted; if not, prompt them to do so
        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        try:
            leaderboard_data = await db.get_leaderboard(interaction.guild_id)  # Retrieve leaderboard data from the database
            if not leaderboard_data:
                await interaction.followup.send(embed=create_error_embed("No data available yet."))
                return

            # Create and populate an embed with the server's music leaderboard
            embed = create_basic_embed(title="🎵 Music Leaderboard 🎵", description="Top music players in the server!")

            for idx, (user_id, count) in enumerate(leaderboard_data, start=1):
                user = await self.bot.fetch_user(user_id)
                if idx == 1:
                    embed.set_thumbnail(url=user.display_avatar.url)

                # Add medals for top positions and format the leaderboard entries
                medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
                name = f"{medal} {user.display_name}"
                value = f"🎶 Plays: {count}"
                embed.add_field(name=name, value=value, inline=False)

            embed.set_footer(text="Leaderboard updated")
            embed.timestamp = discord.utils.utcnow()

            await interaction.followup.send(embed=embed)
        except Exception as e:
            # Log the error and inform the user if something goes wrong
            logger.error(f"Error retrieving leaderboard: {e}")
            await interaction.followup.send(
                embed=create_error_embed("An error occurred while retrieving the leaderboard."))
