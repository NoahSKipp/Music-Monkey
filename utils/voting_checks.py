# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.08.2024                    #
# ========================================= #

import discord
import aiohttp
import config
import logging
from utils.embeds import create_basic_embed

async def has_voted(user: discord.User, guild: discord.Guild, bot, interaction: discord.Interaction) -> bool:
    logging.debug(f"Checking vote status for user {user.id} in guild {guild.id}")

    if guild.id == config.EXEMPT_GUILD_ID:
        return True
    if guild.id == 1229102559453777991:
        return True

    exempt_guild = bot.get_guild(config.EXEMPT_GUILD_ID)
    if not exempt_guild:
        try:
            exempt_guild = await bot.fetch_guild(config.EXEMPT_GUILD_ID)
        except (discord.NotFound, discord.Forbidden) as e:
            logging.error(f"Error fetching exempt guild: {e}")
            embed = create_basic_embed(
                title="Error",
                description="Could not verify exempt status due to an error.",
            )
            if not interaction.response.is_done():
                logging.debug("Sending response message due to error in fetching exempt guild.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                logging.debug("Sending follow-up message due to error in fetching exempt guild.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            return False

    if exempt_guild:
        try:
            exempt_member = await exempt_guild.fetch_member(user.id)
            if exempt_member:
                roles = [role.id for role in exempt_member.roles]
                if config.EXEMPT_ROLE_ID in roles:
                    logging.debug(f"User {user.id} has the exempt role {config.EXEMPT_ROLE_ID} in exempt guild {config.EXEMPT_GUILD_ID}.")
                    return True
        except (discord.NotFound, discord.Forbidden) as e:
            logging.error(f"Error fetching exempt member: {e}")
            embed = create_basic_embed(
                title="Error",
                description="Could not verify exempt status due to an error.",
            )
            if not interaction.response.is_done():
                logging.debug("Sending response message due to error in fetching exempt member.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                logging.debug("Sending follow-up message due to error in fetching exempt member.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            return False

    url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
    headers = {
        "Authorization": f"Bearer {config.TOPGG_TOKEN}",
        "X-Auth-Key": config.AUTHORIZATION_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("voted") == 1:
                    return True
            embed = create_basic_embed(
                title="Unlock This Feature!",
                description=(
                    "This feature is available to our awesome voters.\n" 
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk.\n "
                    "Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                )
            )
            if not interaction.response.is_done():
                logging.debug("Sending response message for non-voter.")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                logging.debug("Sending follow-up message for non-voter.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            return False

    return False

async def has_voted_sources(user: discord.User, guild: discord.Guild, bot, interaction: discord.Interaction) -> bool:
    logging.debug(f"Checking vote status for non-YouTube source for user {user.id} in guild {guild.id}")

    if guild.id == config.EXEMPT_GUILD_ID:
        return True
    if guild.id == 1229102559453777991:
        return True

    exempt_guild = bot.get_guild(config.EXEMPT_GUILD_ID)
    if not exempt_guild:
        try:
            exempt_guild = await bot.fetch_guild(config.EXEMPT_GUILD_ID)
        except (discord.NotFound, discord.Forbidden):
            pass  # Proceed to check voting status online if guild fetching fails

    try:
        exempt_member = await exempt_guild.fetch_member(user.id)
        if exempt_member:
            roles = [role.id for role in exempt_member.roles]
            if config.EXEMPT_ROLE_ID in roles:
                return True
    except (discord.NotFound, discord.Forbidden):
        pass  # Proceed to check voting status online if member fetching fails

    url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
    headers = {
        "Authorization": f"Bearer {config.TOPGG_TOKEN}",
        "X-Auth-Key": config.AUTHORIZATION_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("voted") == 1:
                    return True

            embed = create_basic_embed(
                title="Unlock This Feature!",
                description=(
                    "Playing tracks from sources other than Deezer is a special feature just for our awesome voters.\n "
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk.\n "
                    "Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642>"
                )
            )
            if not interaction.response.is_done():
                logging.debug("Sending response message for non-voter (source check).")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                logging.debug("Sending follow-up message for non-voter (source check).")
                await interaction.followup.send(embed=embed, ephemeral=True)

    return False
