# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.08.2024                    #
# ========================================= #

import discord


async def sync_commands(bot, message: discord.Message):
    if message.content.lower() == "sync global":
        await bot.tree.sync()
        await message.channel.send("Global command tree synced successfully.")
        print("Manual global sync triggered.")

