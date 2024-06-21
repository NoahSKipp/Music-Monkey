# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.05.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import database
from permissions import can_use_updates_commands
import logging


class BroadcastCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.creator_ids = ['338735185900077066', '99624063655215104']  # Discord-ID of the users who should be able
        # to use this function

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is a direct message and is from one of the bot creators
        if message.guild is None and str(message.author.id) in self.creator_ids:
            await self.relay_message_to_servers(message.content)

    async def relay_message_to_servers(self, content):
        embed = discord.Embed(
            title="📰 News & Updates",
            description=content,
            color=discord.Color.blue()
        )
        embed.set_footer(text="MusicMonkey • Enhancing your music experience")
        embed.set_author(name="Dev Team", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        for guild in self.bot.guilds:
            updates_status = await database.get_updates_status(guild.id)
            updates_channel_id = await database.get_updates_channel(guild.id)

            if updates_status == 0:  # Check if updates are disabled
                continue  # Skip this guild if updates are disabled

            if updates_channel_id:
                channel = guild.get_channel(updates_channel_id)
                if channel:
                    await self.send_embed_to_channel(channel, embed, guild.name)
                    continue

            # Fall back to the old method if no updates channel is set or updates are enabled
            channel_names = ["general", "main-channel", "main"]
            for channel in guild.text_channels:
                if channel.name in channel_names:
                    await self.send_embed_to_channel(channel, embed, guild.name)
                    break

    async def send_embed_to_channel(self, channel, embed, guild_name):
        try:
            await channel.send(embed=embed)
            print(f"Message sent successfully to {guild_name}")
            await asyncio.sleep(2)  # Delay to prevent hitting rate limits
        except discord.Forbidden:
            print(f"Permission denied to send message to {channel.name} in {guild_name}")
        except discord.HTTPException as e:
            print(f"Failed to send message to {channel.name} in {guild_name}: {e}")
            if e.status == 429:  # Handle rate limit
                retry_after = int(e.response.headers.get('Retry-After', 5))
                await asyncio.sleep(retry_after)
                await self.send_embed_to_channel(channel, embed, guild_name)  # Retry sending the message

    # Lets a server moderator enable or disable the bot broadcasts.
    @app_commands.command(name="updates", description="Enable or disable updates for this server")
    @app_commands.choices(choice=[
        app_commands.Choice(name="enable", value="enable"),
        app_commands.Choice(name="disable", value="disable"),
    ])
    async def updates(self, interaction: discord.Interaction, choice: str):
        if can_use_updates_commands(interaction.user):
            await database.set_updates_status(interaction.guild_id, choice)
            await interaction.response.send_message(f"Updates have been {choice}d for this server.", ephemeral=True)
        else:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)

    # Lets a server moderator set the channel in which the bot broadcasts should be sent.
    @app_commands.command(name="updates_set", description="Set the current channel as the updates channel")
    async def updates_set(self, interaction: discord.Interaction):
        if can_use_updates_commands(interaction.user):
            await database.set_updates_channel(interaction.guild_id, interaction.channel_id)
            await interaction.response.send_message(f"This channel has been set as the updates channel.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(BroadcastCog(bot))
