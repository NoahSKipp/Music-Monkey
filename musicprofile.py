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

    async def has_voted(self, user: discord.User, guild: discord.Guild) -> bool:
        # Log guild and role checks
        print(f"Checking vote status for user {user.id} in guild {guild.id}")

        # Check if the command is used in the exempt guild
        if guild.id == config.EXEMPT_GUILD_ID:
            return True

        # Check if the user has the exempt role in the exempt guild
        exempt_guild = self.bot.get_guild(config.EXEMPT_GUILD_ID)
        if not exempt_guild:
            try:
                exempt_guild = await self.bot.fetch_guild(config.EXEMPT_GUILD_ID)
            except discord.NotFound:
                return False
            except discord.Forbidden:
                return False
            except Exception as e:
                return False

        try:
            exempt_member = await exempt_guild.fetch_member(user.id)
            if exempt_member:
                roles = [role.id for role in exempt_member.roles]
                print(f"Exempt member found in exempt guild with roles: {roles}")
                if config.EXEMPT_ROLE_ID in roles:
                    print(
                        f"User {user.id} has the exempt role {config.EXEMPT_ROLE_ID} in exempt guild {config.EXEMPT_GUILD_ID}.")
                    return True
        except discord.NotFound:
            return False
        except discord.Forbidden:
            return False
        except Exception as e:
            return False

        # If not exempt by guild or role, check vote status on Top.gg
        url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
        headers = {
            "Authorization": f"Bearer {config.TOPGG_TOKEN}",
            "X-Auth-Key": config.AUTHORIZATION_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    voted = data.get("voted") == 1
                    return voted
                else:
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
        await interaction.response.defer(ephemeral=True)

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                description=(
                    "This feature is available to our awesome voters.\n "
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. \n"
                    "As a bonus, Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642> "
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Unlock This Feature!", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

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
        await interaction.response.defer()

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                description=(
                    "This feature is available to our awesome voters.\n "
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. \n"
                    "As a bonus, Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642> "
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Unlock This Feature!", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return


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
