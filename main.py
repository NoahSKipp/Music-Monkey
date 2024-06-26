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
import logging
import database

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


class MusicMonkey(commands.AutoShardedBot):
    async def setup_hook(self):
        # Setup top.gg client and webhook
        self.dblclient = topgg.DBLClient(self, config.TOPGG_TOKEN, autopost=True)
        self.webhook_manager = topgg.WebhookManager(self).dbl_webhook(route="/dblwebhook", auth_key="Test1!")

        # Lavalink node setup
        nodes = [
            wavelink.Node(identifier="1stMonkey", uri=f'http://{config.LAVALINK_HOST}:{config.LAVALINK_PORT}',
                          password=config.LAVALINK_PASSWORD)
        ]
        await wavelink.Pool.connect(nodes=nodes, client=self)

        # Load extensions
        extensions = ['music', 'musicprofile', 'recommend', 'help', 'broadcast']
        for extension in extensions:
            await self.load_extension(extension)

        await self.tree.sync()
        await database.setup_database()
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name='/play | /help'))
        print("All commands synced successfully.")

    async def on_ready(self):
        print(f'Logged in as {self.user} and ready!')
        await self.webhook_manager.run(20418)


async def main():
    intents = discord.Intents.default()
    intents.members = True

    bot = MusicMonkey(command_prefix='/', intents=intents, shard_count=4)
    await bot.start(config.TOKEN)


if __name__ == '__main__':
    asyncio.run(main())

