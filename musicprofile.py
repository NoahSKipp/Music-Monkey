# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 07.05.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import database
import wavelink

class MusicProfile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        track = wavelink.Playable
        requester_id = getattr(track.extras, "requester_id", None)
        track_id = wavelink.Playable.identifier
        guild_id = payload.player.guild_id

        if requester_id:
            await database.increment_plays(requester_id, track_id, guild_id)

    @app_commands.command(name='profile', description='Displays a music profile for you or another user')
    @app_commands.describe(user="The user whose music profile you want to view")
    async def music_profile(self, interaction: discord.Interaction, user: discord.User = None):
        if user is None:
            user = interaction.user

        user_id = user.id
        profile = await database.get_user_stats(user_id)
        if profile:
            embed = discord.Embed(title=f"🎶 {user.display_name}'s Music Profile 🎶", color=discord.Color.random())
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="🎤 Top Artist", value=profile['top_artist'], inline=False)
            embed.add_field(name="🎵 Top Song", value=profile['top_song'], inline=False)
            embed.add_field(name="🔢 Total Songs Played", value=str(profile['total_songs_played']), inline=True)
            embed.add_field(name="⏳ Total Hours Played", value=f"{profile['total_hours_played']:.2f} hours",
                            inline=True)

            embed.set_footer(text="Music Profile", icon_url=self.bot.user.display_avatar.url)
            embed.timestamp = discord.utils.utcnow()

            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(f"🚫 No music profile found for {user.display_name}.",
                                                    ephemeral=True)

    @app_commands.command(name='leaderboard', description='Show the music leaderboard for this server')
    async def leaderboard(self, interaction: discord.Interaction):
        try:
            leaderboard_data = await database.get_leaderboard(interaction.guild_id)
            if not leaderboard_data:
                await interaction.response.send_message("No data available yet.")
                return

            embed = discord.Embed(title="🎵 Music Leaderboard 🎵", description="Top music players in the server!",
                                  color=discord.Color.dark_gold())

            for idx, (user_id, count) in enumerate(leaderboard_data, start=1):
                user = await self.bot.fetch_user(user_id)
                if idx == 1:
                    medal = "🥇"
                elif idx == 2:
                    medal = "🥈"
                elif idx == 3:
                    medal = "🥉"
                else:
                    medal = f"{idx}."

                if idx == 1:
                    embed.set_thumbnail(url=user.avatar.url)

                name = f"{medal} {user.display_name}"
                value = f"🎶 Plays: {count}"
                embed.add_field(name=name, value=value, inline=False)

            embed.set_footer(text="Leaderboard updated")
            embed.timestamp = discord.utils.utcnow()

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"Error retrieving leaderboard: {e}", ephemeral=False)

async def setup(bot):
    await bot.add_cog(MusicProfile(bot))
