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
        if isinstance(message.channel, discord.DMChannel) and str(message.author.id) in self.creator_ids:
            if message.content.lower().startswith("broadcast:"):
                broadcast_content = message.content[len("broadcast:"):].strip()
                await self.relay_message_to_servers(broadcast_content)
                await message.channel.send("Broadcast sent to all servers.")
                self.logger.info("Broadcast message sent by creator.")

    async def relay_message_to_servers(self, content: str):
        embed = create_info_embed(content)
        view = discord.ui.View()
        support_button = discord.ui.Button(label="Support", url="https://discord.gg/6WqKtrXjhn", style=discord.ButtonStyle.link)
        website_button = discord.ui.Button(label="Website", url="https://getmusicmonkey.com", style=discord.ButtonStyle.link)
        view.add_item(support_button)
        view.add_item(website_button)

        tasks = []
        failed_guilds = []

        for guild in self.bot.guilds:
            try:
                updates_status = await database.get_updates_status(guild.id)
                if updates_status == 0:
                    self.logger.info(f"Updates are disabled for {guild.name}, skipping.")
                    continue

                channel = self.find_preferred_channel(guild)
                if channel:
                    tasks.append(self.send_embed_to_channel(channel, embed, view, guild.name))
                else:
                    self.logger.warning(f"No suitable channel found for {guild.name}, skipping.")
                    failed_guilds.append(guild)
            except Exception as e:
                self.logger.error(f"Unexpected error in guild {guild.name}: {e}")
                failed_guilds.append(guild)

        # Process tasks in batches
        BATCH_SIZE = 50
        SLEEP_BETWEEN_BATCHES = 5

        for i in range(0, len(tasks), BATCH_SIZE):
            batch = tasks[i:i + BATCH_SIZE]
            self.logger.info(f"Processing batch {i // BATCH_SIZE + 1} ({len(batch)} guilds)...")
            results = await asyncio.gather(*batch, return_exceptions=True)

            for guild, result in zip(self.bot.guilds[i:i + BATCH_SIZE], results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to send message to {guild.name}: {result}")

            await asyncio.sleep(SLEEP_BETWEEN_BATCHES)

        # Retry failed guilds
        if failed_guilds:
            self.logger.info(f"Retrying failed guilds: {len(failed_guilds)}")
            await asyncio.sleep(5)
            for guild in failed_guilds:
                try:
                    channel = self.find_preferred_channel(guild)
                    if channel:
                        await self.send_embed_to_channel(channel, embed, view, guild.name)
                except Exception as e:
                    self.logger.error(f"Failed again for guild {guild.name}: {e}")

        self.logger.info("Broadcast completed.")

    def find_preferred_channel(self, guild):
        """Find a suitable channel for sending broadcast messages in the guild."""
        # Priority 1: System channel
        if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
            return guild.system_channel

        # Priority 2: Preferred channel names
        preferred_channel_names = ["general", "main", "main-chat", "welcome"]
        for channel_name in preferred_channel_names:
            channel = discord.utils.get(guild.text_channels, name=channel_name)
            if channel and channel.permissions_for(guild.me).send_messages:
                return channel

        # Priority 3: Any accessible channel
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                return channel

        return None  # No suitable channel found

    async def send_embed_to_channel(self, channel: discord.TextChannel, embed: discord.Embed, view: discord.ui.View, guild_name: str):
        """Send an embed message to the specified channel, handling potential errors and rate limits."""
        try:
            await channel.send(embed=embed, view=view)
            self.logger.info(f"Message sent successfully to {guild_name} in channel {channel.name}.")
            await asyncio.sleep(1)  # Throttle requests to avoid rate limits
        except discord.Forbidden:
            self.logger.warning(f"Permission denied for {channel.name} in {guild_name}. Skipping.")
        except discord.HTTPException as e:
            self.logger.error(f"HTTPException for {channel.name} in {guild_name}: {e}")
            if e.status == 429:  # Handle rate limits
                retry_after = int(e.response.headers.get('Retry-After', 5))
                self.logger.info(f"Rate limited. Retrying after {retry_after} seconds.")
                await asyncio.sleep(retry_after)
                await self.send_embed_to_channel(channel, embed, view, guild_name)

    async def toggle_updates(self, interaction: discord.Interaction, choice: str):
        """Toggle the updates setting for the guild."""
        await database.set_updates_status(interaction.guild_id, choice)
        self.logger.info(f"Updates have been {choice}d for guild {interaction.guild.name} by user {interaction.user}.")
        await interaction.response.send_message(
            embed=create_basic_embed("", f"Updates have been {choice}d for this server."), ephemeral=True
        )

    async def set_updates_channel(self, interaction: discord.Interaction):
        """Set the current channel as the updates channel for the guild."""
        await database.set_updates_channel(interaction.guild_id, interaction.channel_id)
        self.logger.info(
            f"Updates channel set to {interaction.channel.name} for guild {interaction.guild.name} by user {interaction.user}."
        )
        await interaction.response.send_message(
            embed=create_basic_embed("", "This channel has been set as the updates channel."), ephemeral=True
        )
