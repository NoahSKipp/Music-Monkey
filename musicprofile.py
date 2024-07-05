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
import aiohttp
import config


class MusicProfile(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def has_voted(self, user_id: int) -> bool:
        url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user_id}"
        headers = {
            "Authorization": f"Bearer {config.TOPGG_TOKEN}",
            "X-Auth-Key": config.AUTHORIZATION_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("voted") == 1
                else:
                    print(f"Failed to check vote status: {response.status}")
                    return False

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
        if not await self.has_voted(interaction.user.id):
            await interaction.response.send_message(
                "Hey there, music lover! 🎶 This feature is available to our awesome voters. 🌟 Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. As a bonus, Server Boosters and giveaway winners get to skip this step and enjoy all the tunes! 🎉 Thanks for keeping the party going! 🙌",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

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

            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            await interaction.followup.send(f"🚫 No music profile found for {user.display_name}.", ephemeral=True)

    @app_commands.command(name='leaderboard', description='Show the music leaderboard for this server')
    async def leaderboard(self, interaction: discord.Interaction):
        if not await self.has_voted(interaction.user.id):
            await interaction.response.send_message(
                "Hey there, music lover! 🎶 This feature is available to our awesome voters. 🌟 Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. As a bonus, Server Boosters and giveaway winners get to skip this step and enjoy all the tunes! 🎉 Thanks for keeping the party going! 🙌",
                ephemeral=True
            )
            return

        await interaction.response.defer()

        try:
            leaderboard_data = await database.get_leaderboard(interaction.guild_id)
            if not leaderboard_data:
                await interaction.followup.send("No data available yet.")
                return

            embed = discord.Embed(title="🎵 Music Leaderboard 🎵", description="Top music players in the server!",
                                  color=discord.Color.blue())

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
                    embed.set_thumbnail(url=user.display_avatar.url)

                name = f"{medal} {user.display_name}"
                value = f"🎶 Plays: {count}"
                embed.add_field(name=name, value=value, inline=False)

            embed.set_footer(text="Leaderboard updated")
            embed.timestamp = discord.utils.utcnow()

            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(f"Error retrieving leaderboard: {e}", ephemeral=False)


async def setup(bot):
    await bot.add_cog(MusicProfile(bot))
