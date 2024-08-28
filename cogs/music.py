# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 21.04.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands, Interaction
from services.music_service import MusicService
from utils.embeds import create_error_embed
from utils.logging import get_logger

class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.service = MusicService(bot)
        self.logger = get_logger(__name__)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        await self.service.on_voice_state_update(member, before, after)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload):
        await self.service.on_wavelink_node_ready(payload)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload):
        await self.service.on_wavelink_track_start(payload)

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload):
        await self.service.on_wavelink_track_end(payload)

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player):
        await self.service.on_wavelink_inactive_player(player)

    @app_commands.command(name='play', description='Play or queue a song from a URL or search term')
    @app_commands.describe(query='URL or search term of the song to play',
                           source='The source to search from (YouTube, Spotify, Deezer)')
    @app_commands.choices(source=[
        app_commands.Choice(name='YouTube', value='YouTube'),
        app_commands.Choice(name='Spotify', value='Spotify'),
        app_commands.Choice(name='Deezer', value='Deezer')
    ])
    @app_commands.autocomplete(query=MusicService.youtube_autocomplete)
    async def play(self, interaction: Interaction, query: str, source: str = 'Deezer'):
        await self.service.play(interaction, query, source)

    @play.error
    async def play_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='skip', description='Skip the current playing song')
    async def skip(self, interaction: Interaction):
        await self.service.skip(interaction)

    @skip.error
    async def skip_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='pause', description='Pause the music playback')
    async def pause(self, interaction: Interaction):
        await self.service.pause(interaction)

    @pause.error
    async def pause_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='resume', description='Resume the music playback if paused')
    async def resume(self, interaction: Interaction):
        await self.service.resume(interaction)

    @resume.error
    async def resume_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='stop', description='Stop the music and clear the queue')
    async def stop(self, interaction: Interaction):
        await self.service.stop(interaction)

    @stop.error
    async def stop_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='queue', description='Show the current music queue')
    async def show_queue(self, interaction: Interaction):
        await self.service.show_queue(interaction, 1)

    @show_queue.error
    async def show_queue_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='clear', description='Clear the current music queue')
    async def clear(self, interaction: Interaction):
        await self.service.clear_queue(interaction)

    @clear.error
    async def clear_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='cleargone', description='Remove tracks from the queue requested by users not in the voice channel')
    async def cleargone(self, interaction: Interaction):
        await self.service.clear_gone(interaction)

    @cleargone.error
    async def cleargone_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='move', description='Move a song in the queue from one position to another')
    @app_commands.describe(position="Current position of the song in the queue",
                           new_position="New position in the queue")
    async def move(self, interaction: Interaction, position: int, new_position: int):
        await self.service.move(interaction, position, new_position)

    @move.error
    async def move_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='wondertrade', description='Submit a song recommendation to anyone else using the bot!')
    @app_commands.describe(query="The song title or URL to trade", note="A personal note to include with the trade")
    async def wondertrade(self, interaction: Interaction, query: str, note: str):
        await self.service.wondertrade(interaction, query, note)

    @wondertrade.error
    async def wondertrade_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='shuffle', description='Shuffles the current music queue')
    async def shuffle(self, interaction: Interaction):
        await self.service.shuffle(interaction)

    @shuffle.error
    async def shuffle_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='autoplay', description='Toggle AutoPlay mode for automatic music recommendations')
    async def autoplay(self, interaction: Interaction):
        await self.service.autoplay(interaction)

    @autoplay.error
    async def autoplay_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='loop', description='Toggle loop mode for the current track or queue')
    @app_commands.describe(mode="Set loop mode")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Normal (No Loop)", value="normal"),
        app_commands.Choice(name="Loop Current Track", value="loop"),
        app_commands.Choice(name="Loop Entire Queue", value="loop_all")
    ])
    async def loop(self, interaction: Interaction, mode: app_commands.Choice[str]):
        await self.service.loop(interaction, mode.value)

    @loop.error
    async def loop_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='jump', description='Jump to a specific time in the current track')
    @app_commands.describe(time="Time to jump to (mm:ss format)")
    async def jump(self, interaction: Interaction, time: str):
        await self.service.jump(interaction, time)

    @jump.error
    async def jump_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='filters', description='Select a filter to apply')
    @app_commands.autocomplete(query=MusicService.filters_autocomplete)
    async def filters(self, interaction: Interaction, query: str):
        await self.service.filters(interaction, query)

    @filters.error
    async def filters_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='resetfilter', description='Reset all filters')
    async def resetfilter(self, interaction: Interaction):
        await self.service.resetfilter(interaction)

    @resetfilter.error
    async def resetfilter_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name='receive', description='Receive a song recommendation from anyone else using the bot!')
    async def receive(self, interaction: Interaction):
        await self.service.receive(interaction)

    @receive.error
    async def receive_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            retry_after = error.retry_after
            embed = create_error_embed(
                f"This command is on cooldown. Please try again in {retry_after:.2f} seconds."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            await self.error_handler(interaction, error)

    @app_commands.command(name='lyrics', description='Fetch lyrics for the current playing track')
    async def lyrics(self, interaction: Interaction):
        await self.service.lyrics(interaction)

    @lyrics.error
    async def lyrics_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        try:
            if isinstance(error, app_commands.CommandOnCooldown):
                embed = create_error_embed(
                    error_message=f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds."
                )
                self.logger.warning(f"Command cooldown triggered by {interaction.user}: {interaction.command.name}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                self.logger.error(f"Error in command '{interaction.command.name}': {str(error)}")
                embed = create_error_embed(
                    error_message="An error occurred while processing the command."
                )

                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            self.logger.error(f"Error occurred in error handler: {str(e)}")
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=create_error_embed("A severe error occurred."),
                                                        ephemeral=True)
            else:
                await interaction.followup.send(embed=create_error_embed("A severe error occurred."), ephemeral=True)

# Function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(MusicCog(bot))
