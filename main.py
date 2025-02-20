# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 21.04.2024                    #
# ========================================= #

import discord
from discord.ext import commands
import topgg
import asyncio
import config
import wavelink
from utils.logging import setup_logging, get_logger
from database import database as db
from utils.sync_utils import sync_commands  # Import the sync function from the new file
from utils.activity_handler import handle_activity_change


class MusicMonkey(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uptime = None  # Initialize uptime attribute
        self.creator_ids = ['338735185900077066', '99624063655215104']
        self.logger = get_logger(__name__)  # Initialize logger
        self.member_cache = {}  # Initialize the member cache

    async def setup_hook(self):
        # Setup top.gg client and webhook
        self.dblclient = topgg.DBLClient(self, config.TOPGG_TOKEN, autopost=True)
        self.webhook_manager = topgg.WebhookManager(self).dbl_webhook(route="/dblwebhook",
                                                                      auth_key=config.AUTHORIZATION_KEY)

        # Lavalink node setup
        nodes = [
            wavelink.Node(identifier="2ndMonkey", uri=f'http://{config.LAVALINK_HOST2}:{config.LAVALINK_PORT2}',
                          password=config.LAVALINK_PASSWORD2),
            wavelink.Node(identifier="DigitalOcean", uri=f'http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}',
                          password=config.LAVALINK_PASSWORD),
            wavelink.Node(identifier="3rdMonkey", uri=f'http://{config.LAVALINK_HOST3}:{config.LAVALINK_PORT3}',
                          password=config.LAVALINK_PASSWORD3)
        ]
        await wavelink.Pool.connect(nodes=nodes, client=self)

        # Load necessary extensions
        extensions = [
            'cogs.music',
            'cogs.musicprofile',
            'cogs.recommend',
            'cogs.help',
            'cogs.broadcast',
            'cogs.playlist',
            'cogs.monkeyimages',
            'cogs.monkeyfact',
            'cogs.admin_commands',
            'cogs.first_join',
            'cogs.report',
            'cogs.recap',
            'cogs.request'
        ]
        for extension in extensions:
            await self.load_extension(extension)

        self.uptime = discord.utils.utcnow()  # Set the uptime attribute when bot starts
        await db.setup_database()

        # Populate member cache
        await self.populate_member_cache()

    async def populate_member_cache(self):
        """Populate the member cache with all members in all guilds."""
        self.logger.info("Populating member cache...")
        for guild in self.guilds:
            try:
                await guild.chunk()
                for member in guild.members:
                    self.member_cache[member.id] = member
                self.logger.info(f"Cached {len(guild.members)} members from guild {guild.name} ({guild.id}).")
            except Exception as e:
                self.logger.error(f"Error caching members for guild {guild.name}: {e}")

    def get_cached_member(self, member_id: int):
        """Retrieve a member from the cache."""
        return self.member_cache.get(member_id)

    async def on_ready(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='/play | /help'))
        self.logger.info(f'Logged in as {self.user} and ready!')
        await self.webhook_manager.run(config.PORT)

    async def on_message(self, message: discord.Message):
        if message.author == self.user:
            return

        # Check if the message is a DM
        if isinstance(message.channel, discord.DMChannel):
            # Handle activity status change
            await handle_activity_change(self, message)

        # Check for sync commands in messages
        await sync_commands(self, message)


async def main():
    setup_logging()  # Set up logging using our utils module
    intents = discord.Intents.default()
    intents.members = True  # Enable member intent for caching members
    intents.guilds = True  # Ensure guild intent is enabled
    intents.messages = True  # For handling messages

    bot = MusicMonkey(command_prefix='/', intents=intents, shard_count=8)
    await bot.start(config.TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
