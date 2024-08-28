# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 15.08.2024                    #
# ========================================= #

import discord

def create_basic_embed(title: str, description: str, color: discord.Color = discord.Color.from_rgb(255, 202, 40)) -> discord.Embed:
    # Creates a basic embed with a title, description and color
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

def create_error_embed(error_message: str) -> discord.Embed:
    # Creates an embed to display an error message
    return create_basic_embed("Error", error_message, discord.Color.red())

def create_success_embed(success_message: str) -> discord.Embed:
    # Creates an embed to display a success message
    return create_basic_embed("Success", success_message, discord.Color.green())

def create_info_embed(info_message: str) -> discord.Embed:
    # Creates an embed to display an informational message
    embed = create_basic_embed("News & Updates", info_message, discord.Color.blue())
    embed.set_author(name="Dev Team")
    embed.set_footer(text="Configure how you want to receive these updates with /updates")
    return embed
