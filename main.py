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


class MusicMonkey(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.uptime = None  # Initialize uptime attribute
        self.creator_ids = ['338735185900077066', '99624063655215104']
        self.logger = get_logger(__name__)  # Initialize logger

    async def setup_hook(self):
        # Setup top.gg client and webhook


        # Lavalink node setup
        nodes = [

            wavelink.Node(identifier="2ndMonkey", uri=f'http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}',
                          password=config.LAVALINK_PASSWORD)
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
            'cogs.first_join'
        ]
        for extension in extensions:
            await self.load_extension(extension)

        self.uptime = discord.utils.utcnow()  # Set the uptime attribute when bot starts
        await db.setup_database()

    async def on_ready(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='/play | /help'))
        self.logger.info(f'Logged in as {self.user} and ready!')


async def main():
    setup_logging()  # Set up logging using our utils module
    intents = discord.Intents.default()
    intents.members = True

    bot = MusicMonkey(command_prefix='/', intents=intents, shard_count=1)
    await bot.start(config.TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
