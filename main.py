# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 21.04.2024                    #
# ========================================= #

import discord
from discord.ext import commands
import asyncio
import config
import wavelink
import logging
import database

# Outputs logs to console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class MusicMonkey(commands.Bot):
    # Establishes connection to the node.
    async def setup_hook(self):
        # Define the Lavalink nodes
        nodes = [
            wavelink.Node(identifier="MainMonkey", uri=f'http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}',
                          password=config.LAVALINK_PASSWORD),
            wavelink.Node(identifier="SecondaryMonkey", uri=f'http://{config.LAVALINK_HOST2}:{config.LAVALINK_PORT2}',
                          password=config.LAVALINK_PASSWORD2),
            wavelink.Node(identifier="ThirdMonkey", uri=f'http://{config.LAVALINK_HOST3}:{config.LAVALINK_PORT3}',
                          password=config.LAVALINK_PASSWORD3)
        ]

        # Connect to the defined Lavalink node.
        await wavelink.Pool.connect(nodes=nodes, client=self)

        # Declare and load the wanted extensions to the Discord Bot.
        extensions = ['music', 'musicprofile', 'recommend', 'help', 'broadcast']
        for extension in extensions:
            await self.load_extension(extension)

        # Sync the slash commands with Discord.
        await self.tree.sync()

        # Set up the database.
        await database.setup_database()

        print("All commands synced successfully.")

    async def on_ready(self):
        print(f'Logged in as {self.user} and ready!')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='/play | /help'))


async def main():
    # Sets permissions for the bot.
    intents = discord.Intents.default()
    intents.members = True
    intents.voice_states = True

    # Instantiate the bot
    bot = MusicMonkey(command_prefix='/', intents=intents)

    # Start the bot
    await bot.start(config.TOKEN)


if __name__ == '__main__':
    asyncio.run(main())
