# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.05.2024                    #
# ========================================= #

import discord
import asyncio
from utils.logging import get_logger
from utils.embeds import create_info_embed, create_basic_embed
from database import database


class BroadcastService:
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)
        self.creator_ids = ['338735185900077066', '99624063655215104']  # Ensure these IDs are correct

    async def handle_creator_message(self, message: discord.Message):
        # Handle direct messages from creators, initiating a broadcast if the message starts with "broadcast:"
        if message.guild is None and str(message.author.id) in self.creator_ids:
            if message.content.lower().startswith("broadcast:"):
                broadcast_content = message.content[len("broadcast:"):].strip()
                await self.relay_message_to_servers(broadcast_content)
                await message.channel.send("Broadcast sent to all servers.")
                self.logger.info("Broadcast message sent by creator.")

    async def relay_message_to_servers(self, content: str):
        # Relay a broadcast message to all appropriate channels in each guild
        embed = create_info_embed(content)
        view = discord.ui.View()
        support_button = discord.ui.Button(label="Support", url="https://discord.gg/6WqKtrXjhn", style=discord.ButtonStyle.link)
        website_button = discord.ui.Button(label="Website", url="https://getmusicmonkey.com", style=discord.ButtonStyle.link)
        view.add_item(support_button)
        view.add_item(website_button)

        tasks = []
        for guild in self.bot.guilds:
            updates_status = await database.get_updates_status(guild.id)
            if updates_status == 0:
                self.logger.info(f"Updates are disabled for {guild.name}, skipping.")
                continue

            # Check if a specific updates channel is set
            updates_channel_id = await database.get_updates_channel(guild.id)
            if updates_channel_id:
                channel = guild.get_channel(updates_channel_id)
                if channel:
                    tasks.append(self.send_embed_to_channel(channel, embed, view, guild.name))
                    continue

            # Fallback to system channel if no specific updates channel is set
            channel = guild.system_channel
            if channel and channel.permissions_for(guild.me).send_messages:
                tasks.append(self.send_embed_to_channel(channel, embed, view, guild.name))
            else:
                self.logger.warning(f"No suitable channel found for {guild.name}, skipping.")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for guild, result in zip(self.bot.guilds, results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to send message to {guild.name}: {result}")

    async def send_embed_to_channel(self, channel: discord.TextChannel, embed: discord.Embed, view: discord.ui.View, guild_name: str):
        # Send an embed message to the specified channel, handling potential errors and rate limits
        try:
            await channel.send(embed=embed, view=view)
            self.logger.info(f"Message sent successfully to {guild_name} in channel {channel.name}.")
            await asyncio.sleep(2)  # Sleep to avoid rate limits
        except discord.Forbidden:
            self.logger.error(f"Permission denied to send message to {channel.name} in {guild_name}.")
        except discord.HTTPException as e:
            self.logger.error(f"HTTPException when sending message to {channel.name} in {guild_name}: {e}")
            if e.status == 429:
                retry_after = int(e.response.headers.get('Retry-After', 5))
                self.logger.info(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                await self.send_embed_to_channel(channel, embed, view, guild_name)

    async def toggle_updates(self, interaction: discord.Interaction, choice: str):
        # Toggle the updates setting for the guild
        await database.set_updates_status(interaction.guild_id, choice)
        self.logger.info(f"Updates have been {choice}d for guild {interaction.guild.name} by user {interaction.user}.")
        await interaction.response.send_message(
            embed=create_basic_embed("", f"Updates have been {choice}d for this server."), ephemeral=True
        )

    async def set_updates_channel(self, interaction: discord.Interaction):
        # Set the current channel as the updates channel for the guild
        await database.set_updates_channel(interaction.guild_id, interaction.channel_id)
        self.logger.info(f"Updates channel set to {interaction.channel.name} for guild {interaction.guild.name} by user {interaction.user}.")
        await interaction.response.send_message(
            embed=create_basic_embed("", "This channel has been set as the updates channel."), ephemeral=True
        )
