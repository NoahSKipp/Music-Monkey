import discord
from discord.ext import commands
import asyncio
import config
import wavelink
import logging
import database

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class MyBot(commands.Bot):
    async def setup_hook(self):
        # Define the Lavalink nodes
        nodes = [
            wavelink.Node(identifier="MainMonkey", uri=f'http://{config.LAVALINK_HOST2}:{config.LAVALINK_PORT2}', password=config.LAVALINK_PASSWORD2),
        ]

        # Connect to the defined Lavalink node
        await wavelink.Pool.connect(nodes=nodes, client=self)
        # Load the music module
        await self.load_extension('music')
        # Load the recommend module
        await self.load_extension('recommend')
        # Load the help module
        await self.load_extension('help')
        # Load the music profile mpodule
        await self.load_extension('musicprofile')
        # Sync the slash commands with Discord
        await self.tree.sync()
        # Set up the database
        await database.setup_database()
        # Load database settings on startup
        self.guild_settings = await database.fetch_all_guild_settings()

        print("All commands synced successfully.")

    async def on_ready(self):
        print(f'Logged in as {self.user} and ready!')
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='/play | /help'))

async def main():
    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True

    # Instantiate the bot
    bot = MyBot(command_prefix='/', intents=intents)

    # Start the bot
    await bot.start(config.TOKEN)

if __name__ == '__main__':
    asyncio.run(main())
