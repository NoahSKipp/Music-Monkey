# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.05.2024                    #
# ========================================= #

import discord
from discord.ext import commands


class BroadcastCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.creator_ids = ['338735185900077066',
                           "99624063655215104"]  # Discord-ID of the user who should be able to use this function

    @commands.Cog.listener()
    async def on_message(self, message):
        # Check if the message is a direct message and is from one of the bot creators
        if message.guild is None and str(message.author.id) in self.creator_ids:
            await self.relay_message_to_servers(message.content)

    async def relay_message_to_servers(self, content):
        # Create the embed message
        embed = discord.Embed(
            title="📰  News & Updates",
            description=content,
            color=discord.Color.blue()
        )
        # Set footer with bot info
        embed.set_footer(
            text="MusicMonkey • Enhancing your music experience",
        )
        # Set author
        embed.set_author(name="Dev Team", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        # Define channel names to check
        channel_names = ["general", "main-channel", "main"]

        # Loop through guilds and text channels to send the embed message
        for guild in self.bot.guilds:
            for channel in guild.text_channels:
                if channel.name in channel_names:
                    try:
                        # Send embed message to channels matching the specified names
                        await channel.send(embed=embed)
                    except discord.Forbidden:
                        # Print if the bot lacks permissions to send the message
                        print(f"Permission denied to send message to {channel.name} in {guild.name}")
                    except discord.HTTPException as e:
                        # Print if an HTTP exception occurs while sending the message
                        print(f"Failed to send message to {channel.name} in {guild.name}: {e}")


# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(BroadcastCog(bot))