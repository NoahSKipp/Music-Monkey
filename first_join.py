# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 06.08.2024                    #
# ========================================= #

import discord
from discord.ext import commands

class FirstJoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Find the system channel or the first text channel
        if guild.system_channel:
            channel = guild.system_channel
        else:
            channel = next((chan for chan in guild.text_channels if chan.permissions_for(guild.me).send_messages), None)

        if channel:
            embed = discord.Embed(
                title="🎉 Hello from Music Monkey! 🎉",
                description=(
                    "Hey there! I'm **Music Monkey**, your new music buddy! <a:monkeyflip:1237140606296522762>\n\n"
                    "To get started, just join a voice channel and type `/play` to queue up your favorite tunes!\n\n"
                    "Need help? Use `/help` to see all my commands and learn how to access support resources.\n\n"
                    "Want to play music in multiple channels at the same time? You can get multiple instances of me for your server by requesting it in our [support server](https://discord.gg/6WqKtrXjhn) - it's completely free!\n\n"
                    "Make sure to join our [support server](https://discord.gg/6WqKtrXjhn) to report any issues, suggest new features, and stay up to date with the latest updates.\n\n"
                    "Can't wait to jam with you! 🎵"
                ),
                color=discord.Color.blue()
            )

            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(FirstJoin(bot))
