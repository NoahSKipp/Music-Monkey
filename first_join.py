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
        self.creator_ids = ['338735185900077066']  # Ensure these IDs are correct

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        # Send a welcome message to the system channel or the first text channel
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

            # Create buttons for Support, Website, and Vote
            view = discord.ui.View()
            support_button = discord.ui.Button(label="Support", url="https://discord.gg/6WqKtrXjhn", style=discord.ButtonStyle.link)
            website_button = discord.ui.Button(label="Website", url="https://getmusicmonkey.com", style=discord.ButtonStyle.link)
            vote_button = discord.ui.Button(label="Vote", url="https://top.gg/bot/1228071177239531620/vote", style=discord.ButtonStyle.link)

            # Add buttons to the view
            view.add_item(support_button)
            view.add_item(website_button)
            view.add_item(vote_button)

            # Send the embed with the buttons
            await channel.send(embed=embed, view=view)

        # Send a DM to the bot creator with the guild name, guild ID, and user count
        for creator_id in self.creator_ids:
            try:
                user = await self.bot.fetch_user(int(creator_id))
                if user:
                    await user.send(
                        f"Bot joined a new guild:\n"
                        f"**Guild Name:** {guild.name}\n"
                        f"**Guild ID:** {guild.id}\n"
                        f"**Member Count:** {guild.member_count}"
                    )
            except discord.Forbidden:
                print(f"Cannot send DM to user {creator_id}.")
            except discord.HTTPException as e:
                print(f"HTTPException occurred: {e}")

async def setup(bot):
    await bot.add_cog(FirstJoin(bot))
