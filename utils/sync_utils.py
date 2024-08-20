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
    elif message.content.lower() == "sync guilds":
        if message.guild:
            await bot.tree.sync(guild=message.guild)
            await message.channel.send("Guild command tree synced successfully.")
            print("Manual guild sync triggered.")
    else:
        # Forward the message to the bot creator if it wasn't a sync command
        creator = bot.get_user(338735185900077066)
        if creator:
            forward_message = (
                f"Message from {message.author} (ID: {message.author.id}):\n\n"
                f"{message.content}"
            )
            try:
                await creator.send(forward_message)
                await message.channel.send("Your message has been received.")
            except discord.HTTPException as e:
                print(f"Failed to send message to {creator.name}: {e}")
