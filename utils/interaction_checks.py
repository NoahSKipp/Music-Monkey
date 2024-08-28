# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.08.2024                    #
# ========================================= #

import discord
import logging
from discord import Interaction
from database import database as db
from utils.embeds import create_error_embed

async def restriction_check(interaction: discord.Interaction) -> bool:
    # Checks if the user is restricted by DJ-only mode or specific command restrictions
    logging.debug(f'Restriction check for {interaction.user} in guild {interaction.guild_id}')

    dj_only = await db.get_dj_only_enabled(interaction.guild_id)
    dj_role_id = await db.get_dj_role(interaction.guild_id)
    restricted_commands = await db.get_restricted_commands(interaction.guild_id)

    if not dj_only:
        return True

    if restricted_commands is None:
        return True

    if interaction.command.name in restricted_commands:
        has_permissions = interaction.user.guild_permissions.manage_roles
        is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

        if has_permissions or is_dj:
            return True

        embed = create_error_embed(
            error_message="DJ-only mode is enabled. You need DJ privileges to use this command."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    return True

async def can_manage_roles(interaction: Interaction) -> bool:
    # Checks if a member has the 'Manage Roles' permission in the guild
    if interaction.user.guild_permissions.manage_roles:
        return True

    embed = create_error_embed(
        error_message="You do not have permission to use this command."
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)
    return False

def is_dj(member: discord.Member) -> bool:
    # Checks if a member has the 'DJ' role
    return any(role.name == 'DJ' for role in member.roles)

def can_use_updates_commands(member: discord.Member) -> bool:
    # Placeholder for checking if a member can use update commands
    return can_manage_roles()
