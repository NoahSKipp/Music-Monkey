# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 06.08.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from services.firstjoin_service import FirstJoinService


class FirstJoin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = FirstJoinService(bot)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.service.handle_guild_join(guild)


async def setup(bot):
    await bot.add_cog(FirstJoin(bot))
