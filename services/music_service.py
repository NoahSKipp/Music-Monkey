import discord
import wavelink
import asyncio
from discord import app_commands
from discord.ext import commands
from utils.interaction_checks import restriction_check, can_manage_roles, is_dj
from utils.embeds import create_basic_embed, create_error_embed
from utils.formatters import format_duration
from utils.logging import get_logger
from database import database as db
from utils.buttons import QueuePaginationView, MusicButtons
from utils.voting_checks import has_voted_sources, has_voted

logger = get_logger(__name__)


class Track(wavelink.Playable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = None


class MusicService(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def youtube_autocomplete(self, interaction: discord.Interaction, current: str):
        try:
            if not current:
                return []

            # Use Lavalink/Wavelink to search YouTube
            search_results: wavelink.Search = await wavelink.Playable.search(f"{current}")

            # Return up to 25 results to display
            return [
                app_commands.Choice(name=track.title, value=track.uri)
                for track in search_results[:25]
            ]
        except Exception as e:
            logger.error(f"Error in autocomplete: {e}")
            return []

    async def filters_autocomplete(self, interaction: discord.Interaction, current: str):
        options = [
            "Bass Boost", "Nightcore", "Vaporwave", "Karaoke", "Tremolo", "Distortion"
        ]
        return [
            app_commands.Choice(name=option, value=option.lower().replace(" ", "_"))
            for option in options if current.lower() in option.lower()
        ][:25]

    async def play(self, interaction: discord.Interaction, query: str, source: str = 'Deezer'):
        try:
            await interaction.response.defer(ephemeral=False)

            # Check for restrictions first
            if not await restriction_check(interaction):
                return

            # Check if the bot is already in a voice channel
            player = interaction.guild.voice_client
            channel = interaction.user.voice.channel if interaction.user.voice else None

            if not channel:
                embed = create_error_embed("You must be in a voice channel to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if not player:
                try:
                    # Join the user's voice channel immediately
                    player = await channel.connect(cls=wavelink.Player)
                    player.guild_id = interaction.guild_id
                    player.interaction_channel_id = interaction.channel_id
                except discord.Forbidden:
                    embed = create_error_embed(
                        "I don't have permission to join your voice channel. Please check my permissions.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                except discord.HTTPException as e:
                    logger.error(f"Failed to connect to the voice channel: {e}")
                    embed = create_error_embed(
                        "An unexpected error occurred when trying to join your voice channel. Please check my permissions, I may not be allowed to join you in your current channel.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
                except Exception as e:
                    logger.error(f"Unexpected error when trying to join the voice channel: {e}")
                    embed = create_error_embed(
                        "An unexpected error occurred when trying to join your voice channel. Please check my permissions, I may not be allowed to join you in your current channel.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            else:
                if not await self.user_in_voice(interaction):
                    embed = create_error_embed("You must be in the same voice channel as the bot to use this command.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            # After joining the voice channel, proceed with other checks
            if not await has_voted_sources(interaction.user, interaction.guild, self.bot, interaction):
                # Check for inactivity if the user hasn't voted
                await asyncio.sleep(5)  # Short delay before checking inactivity
                if not player.playing:  # Check if still idle
                    text_channel = self.bot.get_channel(player.interaction_channel_id)
                    if text_channel:
                        await self.send_inactivity_message(text_channel)
                    await self.disconnect_and_cleanup(player)
                return

            # Proceed to play the song
            await self.play_song(interaction, query, source)

        except discord.errors.NotFound:
            logger.error("Interaction not found or expired.")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

    async def play_song(self, interaction: discord.Interaction, query: str, source: str):
        try:
            # Check if the query is a URL
            if query.startswith("https://") or query.startswith("http://"):
                search_query = query
            else:
                # Apply the appropriate search prefix based on the source
                if source == 'Spotify':
                    search_query = query
                    source_prefix = 'spsearch'
                elif source == 'Deezer':
                    search_query = query
                    source_prefix = 'dzsearch'
                elif source == 'None':
                    search_query = query
                    source_prefix = ''
                else:  # Default to Deezer
                    search_query = query
                    source_prefix = 'dzsearch'

                # If source_prefix is set, apply the search prefix
                if source_prefix:
                    search_query = f'{source_prefix}:{query}'

            # Use fetch_tracks to avoid default source prefix addition
            results: wavelink.Search = await wavelink.Pool.fetch_tracks(search_query)

            if not results:
                embed = create_error_embed('No tracks found with that query.')
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client

            # Ensure that the player is properly initialized and connected
            if player is None:
                channel = interaction.user.voice.channel if interaction.user.voice else None
                if channel:
                    player = await channel.connect(cls=wavelink.Player)
                    player.guild_id = interaction.guild_id
                    player.interaction_channel_id = interaction.channel_id
                else:
                    embed = create_error_embed("You must be in a voice channel to play music.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            if player is None:
                embed = create_error_embed("Failed to connect to the voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # If the search result is a playlist, add all tracks to the queue
            if isinstance(results, wavelink.Playlist):
                tracks = results.tracks
                embed = create_basic_embed(
                    "**Added to Queue**",
                    f"{len(tracks)} tracks from the playlist"
                ).set_footer(text=f"Queue length: {len(player.queue) + len(tracks)}")
                for track in tracks:
                    track.extras.requester_id = interaction.user.id
                    player.queue.put(track)
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                # If it's a single track, add it to the queue
                track = results[0]
                track.extras.requester_id = interaction.user.id
                player.queue.put(track)
                embed = create_basic_embed(
                    "**Added to Queue**",
                    f"{track.title} by {track.author}"
                ).set_footer(text=f"Queue length: {len(player.queue)}")
                await interaction.followup.send(embed=embed, ephemeral=False)

            # Start playing the next track if nothing is currently playing
            if not player.playing and not player.paused:
                next_track = player.queue.get()
                await player.play(next_track)

            # Update the database with the track information
            await db.enter_song(player.current.identifier, player.current.title, player.current.author,
                                player.current.length, player.current.uri)
            await db.increment_plays(interaction.user.id, player.current.identifier, interaction.guild_id)

        except discord.errors.NotFound:
            logger.error("Interaction not found or expired.")
        except Exception as e:
            logger.error(f"Error processing the play command: {e}")
            try:
                embed = create_error_embed('An error occurred while trying to play the track.')
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.errors.NotFound:
                logger.error("Failed to send follow-up message: Interaction not found or expired.")

    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player: wavelink.Player = interaction.guild.voice_client
            if player is None or not player.connected:
                embed = create_error_embed("The queue is empty, as I'm not active right now.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Stops the current track and trigger the track end event
            await player.stop()

            # Check if the queue is empty before attempting to get the next track
            if not player.queue.is_empty:
                next_track = player.queue.get()
                await player.play(next_track)  # Play the next track
                embed = create_basic_embed("", f"Now playing: {next_track.title}")
                await interaction.followup.send(embed=embed)
            else:
                embed = create_error_embed("The queue is currently empty.")
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the skip command: {e}")

    async def pause(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if player and isinstance(player, wavelink.Player):
                if not player.paused:
                    await player.pause(True)  # Pause the playback
                    embed = create_basic_embed("", "Playback has been paused.")
                    await interaction.followup.send(embed=embed)
                else:
                    embed = create_error_embed("Playback is already paused.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = create_error_embed("The bot is not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the pause command: {e}")

    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if player and isinstance(player, wavelink.Player):
                if player.paused:
                    await player.pause(False)  # Resume playback
                    embed = create_basic_embed("", "Playback has been resumed.")
                    await interaction.followup.send(embed=embed)
                else:
                    embed = create_error_embed("Playback is not paused.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                embed = create_error_embed("The bot is not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the resume command: {e}")

    async def stop(self, interaction: discord.Interaction):
        logger.debug("Stop command received.")
        await interaction.response.defer(ephemeral=True)  # Signal to Discord that more time is needed to process
        try:
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if player:
                logger.debug("Setting was_forcefully_stopped flag to True.")
                player.was_forcefully_stopped = True  # Set the flag before stopping the player
                await self.disconnect_and_cleanup(player)
                embed = create_basic_embed("", "Stopped the music and cleared the queue.")
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the stop command: {e}")

    async def show_queue(self, interaction: discord.Interaction, page: int):
        await self.display_queue(interaction, page)

    async def display_queue(self, interaction: discord.Interaction, page: int, edit=False):
        try:
            # Gets the player object of the bot in the current guild's voice channel
            player = interaction.guild.voice_client

            # If there's no player, no player queue, or an empty player queue, displays a message
            if not player or not player.queue or player.queue.is_empty:
                embed = create_error_embed("The queue is empty.")
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.followup.send(embed=embed)
                return

            # Setting the parameters for the queue embed
            items_per_page = 10
            total_pages = (len(player.queue) + items_per_page - 1) // items_per_page
            start_index = (page - 1) * items_per_page
            end_index = min(start_index + items_per_page, len(player.queue))
            queue_slice = list(player.queue)[start_index:end_index]

            queue_description = "\n".join(
                f"{idx + 1 + start_index}. **{track.title}** by `{track.author}` ({format_duration(track.length)}) - Requested by <@{track.extras.requester_id}>"
                for idx, track in enumerate(queue_slice)
            )
            embed = create_basic_embed(f'Queue - Page {page} of {total_pages}', queue_description)
            view = QueuePaginationView(self, interaction, page, total_pages)

            if edit:
                await interaction.message.edit(embed=embed, view=view)
            else:
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)
                else:
                    await interaction.followup.send(embed=embed, view=view, ephemeral=False)
        except Exception as e:
            logger.error(f"Error displaying the queue: {e}")

    async def clear_queue(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player or player.queue.is_empty:
                embed = create_error_embed("The queue is already empty.")
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                player.queue.clear()  # Clear the queue
                embed = create_basic_embed("", "The music queue has been cleared.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error clearing the queue: {e}")

    async def clear_gone(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player or player.queue.is_empty:
                embed = create_error_embed("The queue is empty.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Get the IDs of members currently in the voice channel
            voice_channel_members = {member.id for member in interaction.user.voice.channel.members}
            initial_count = len(player.queue)
            # Identify tracks to remove where the requester is no longer in the voice channel
            tracks_to_remove = [i for i, track in enumerate(player.queue) if
                                not hasattr(track.extras, 'requester_id') or getattr(track.extras, 'requester_id',
                                                                                     None) not in voice_channel_members]

            for index in reversed(tracks_to_remove):
                player.queue.delete(index)

            removed_count = initial_count - len(player.queue)
            embed = create_basic_embed("",
                f"Removed {removed_count} tracks requested by users not currently in the channel.")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the clear gone command: {e}")

    async def move(self, interaction: discord.Interaction, position: int, new_position: int):
        await interaction.response.defer(ephemeral=False)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player or player.queue.is_empty:
                embed = create_error_embed("The queue is empty.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Convert to zero-indexed
            position -= 1
            new_position -= 1

            if position < 0 or new_position < 0 or position >= len(player.queue) or new_position >= len(player.queue):
                embed = create_error_embed("Invalid positions provided.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                # Retrieve the track from the current position
                track = player.queue.get_at(position)
                # Remove the track from the current position
                player.queue.remove(track)
                # Insert the track at the new position
                player.queue.put_at(new_position, track)

                embed = create_basic_embed("", f"Moved track from position {position + 1} to position {new_position + 1}.")
                await interaction.followup.send(embed=embed)
            except (IndexError, wavelink.QueueEmpty) as e:
                embed = create_error_embed(f"An error occurred: {str(e)}")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the move command: {e}")

    async def remove(self, interaction: discord.Interaction, position: int):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player or player.queue.is_empty:
                embed = create_error_embed("The queue is empty.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if position < 1 or position > len(player.queue):
                embed = create_error_embed("Invalid position in the queue.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            try:
                # Delete the track at the specified position, adjusted for zero-indexed list
                player.queue.delete(position - 1)
                embed = create_basic_embed("", f"Removed track at position {position} from the queue.")
                await interaction.followup.send(embed=embed)
            except IndexError:
                embed = create_error_embed("No track found at the specified position.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the remove command: {e}")

    async def shuffle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player or not player.queue or not hasattr(player,
                                                             'now_playing_message') or not player.now_playing_message:
                embed = create_error_embed(
                    "Shuffle can only be used when a song is playing and visible in the Now Playing message.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Shuffle the queue
            player.queue.shuffle()

            # Send confirmation message
            embed = create_basic_embed("", "The queue has been shuffled.")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the shuffle command: {e}")

    async def autoplay(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            # Check for restrictions first
            if not await restriction_check(interaction):
                return

            # Ensure the user is in the same voice channel as the bot
            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Retrieve the player for the current guild
            player = interaction.guild.voice_client
            if not player:
                embed = create_error_embed("Not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Toggle the autoplay mode
            if player.autoplay == wavelink.AutoPlayMode.enabled:
                player.autoplay = wavelink.AutoPlayMode.disabled
                embed = create_basic_embed("", "AutoPlay has been disabled.")
            else:
                player.autoplay = wavelink.AutoPlayMode.enabled
                embed = create_basic_embed("", "AutoPlay has been enabled.")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error processing the autoplay command: {e}")

    async def loop(self, interaction: discord.Interaction, mode: str):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player:
                embed = create_error_embed("I'm not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            if not player.playing:
                embed = create_error_embed("No music is currently playing.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Set the loop mode based on user input
            if mode == "normal":
                player.queue.mode = wavelink.QueueMode.normal
                mode_description = "normal (no looping)"
            elif mode == "loop":
                player.queue.mode = wavelink.QueueMode.loop
                mode_description = "looping current track"
            elif mode == "loop_all":
                player.queue.mode = wavelink.QueueMode.loop_all
                mode_description = "looping entire queue"

            # Send a response back to the user
            embed = create_basic_embed("", f"Queue mode set to {mode_description}.")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the loop command: {e}")

    async def jump(self, interaction: discord.Interaction, time: str):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await restriction_check(interaction):
                return

            if not await self.user_in_voice(interaction):
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Validate and parse the time format
            try:
                minutes, seconds = map(int, time.split(':'))
                position = (minutes * 60 + seconds) * 1000  # Convert time to milliseconds
            except ValueError:
                embed = create_error_embed("Invalid time format. Please use mm:ss format.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Get the current player
            player = interaction.guild.voice_client
            if player and player.playing:
                # Seek to the desired position
                await player.seek(position)
                embed = create_basic_embed("", f"Jumped to {minutes} minutes and {seconds} seconds.")
                await interaction.followup.send(embed=embed)
            else:
                embed = create_error_embed("There is no active player or track playing.")
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the jump command: {e}")

    async def filters(self, interaction: discord.Interaction, filter: str):
        try:
            await interaction.response.defer(ephemeral=True)

            # Retrieve the player object of the bot in the current guild's voice channel
            player = interaction.guild.voice_client
            if not player:
                embed = create_error_embed("Not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Apply the filter based on the selected option
            if filter == 'bass_boost':
                await self.apply_bass_boost(player)
            elif filter == 'nightcore':
                await self.apply_nightcore(player)
            elif filter == 'vaporwave':
                await self.apply_vaporwave(player)
            elif filter == 'karaoke':
                await self.apply_karaoke(player)
            elif filter == 'tremolo':
                await self.apply_tremolo(player)
            elif filter == 'distortion':
                await self.apply_distortion(player)
            else:
                embed = create_error_embed("Invalid filter selected.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            embed = create_basic_embed("", f"The {filter.replace('_', ' ').title()} filter has been applied.")
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error processing the filters command: {e}")
            embed = create_error_embed("An error occurred while trying to apply the filter.")
            await interaction.followup.send(embed=embed, ephemeral=True)

    # Apply the bass boost effect
    async def apply_bass_boost(self, player):
        filters = wavelink.Filters()
        filters.equalizer.set(bands=[
            {"band": 0, "gain": 0.25},
            {"band": 1, "gain": 0.25},
            {"band": 2, "gain": 0.25},
            {"band": 3, "gain": 0.2},
            {"band": 4, "gain": 0.15}
        ])
        await player.set_filters(filters)

    # Apply the nightcore effect
    async def apply_nightcore(self, player):
        filters = wavelink.Filters()
        filters.timescale.set(pitch=1.25, speed=1.25)
        await player.set_filters(filters)

    # Apply the vaporwave effect
    async def apply_vaporwave(self, player):
        filters = wavelink.Filters()
        filters.timescale.set(pitch=0.8, speed=0.85)
        filters.rotation.set(rotation_hz=0.1)
        await player.set_filters(filters)

    # Apply the karaoke effect
    async def apply_karaoke(self, player):
        filters = wavelink.Filters()
        filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
        await player.set_filters(filters)

    # Apply the tremolo effect
    async def apply_tremolo(self, player):
        filters = wavelink.Filters()
        filters.tremolo.set(frequency=4.0, depth=0.75)
        await player.set_filters(filters)

    # Apply the distortion effect
    async def apply_distortion(self, player):
        filters = wavelink.Filters()
        filters.distortion.set(sin_offset=0.5, sin_scale=0.5, cos_offset=0.5, cos_scale=0.5, tan_offset=0.5,
                               tan_scale=0.5,
                               offset=0.5, scale=0.5)
        await player.set_filters(filters)

    async def resetfilter(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            player = interaction.guild.voice_client
            if not player:
                embed = create_error_embed("Not connected to a voice channel.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Reset all filters
            filters = wavelink.Filters()
            filters.reset()
            await player.set_filters(filters)
            embed = create_basic_embed("", "All filters have been reset!")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the resetfilter command: {e}")
            embed = create_error_embed("An error occurred while trying to reset the filters.")
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def wondertrade(self, interaction: discord.Interaction, query: str, note: str):
        await interaction.response.defer(ephemeral=True)
        try:
            # Searches for a song with the user's provided query.
            search_result = await wavelink.Playable.search(query)

            # If the query yields no results, send a message and exit the function.
            if not search_result:
                embed = create_error_embed('No tracks found with that query.')
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # If the query is a playlist, send a message and exit the function.
            elif isinstance(search_result, wavelink.Playlist):
                embed = create_error_embed('Please only send songs, not playlists.')
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Otherwise, attempt to create the wondertrade.
            else:
                # Note: search_result is initialized as a list, so we extract the first playable, the searched song.
                search_result = search_result[0]
                result = await db.submit_wonder_trade(search_result.identifier, search_result.title,
                                                      search_result.author, search_result.length, search_result.uri,
                                                      interaction.user.id, note)
                # Output the result to the user.
                embed = create_basic_embed("Wondertrade creation result", result)
                await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error processing the wondertrade command: {e}")
            embed = create_error_embed('An error occurred when trying to create the wonder trade.')
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def receive(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        try:
            channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
            if not channel:
                embed = create_error_embed("You must be in the same voice channel as me to use this command.")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            player = interaction.guild.voice_client

            if player:
                if not await self.user_in_voice(interaction):
                    embed = create_error_embed("You must be in the same voice channel as the bot to use this command.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return
            else:
                try:
                    player = await channel.connect(cls=wavelink.Player)
                    player.guild_id = interaction.guild_id
                    player.interaction_channel_id = interaction.channel_id
                except Exception as e:
                    logger.error(f"Error connecting to voice channel: {e}")
                    embed = create_error_embed("Failed to connect to the voice channel.")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            response = await db.receive_wonder_trade(interaction.user.id)

            if isinstance(response, tuple):
                uri, note = response
                logger.info(f"Received wonder trade result: {uri}, {note}")

                if not uri.startswith('_'):
                    if note:
                        embed = create_basic_embed(
                            "You've received a song recommendation note!",
                            f"Oh! It seems the person who recommended this song left you a note!\n||{note}||"
                        ).set_footer(text="Messages aren't monitored or filtered. View at your own discretion.")
                        await interaction.followup.send(embed=embed)

                    await self.play_song(interaction, uri, source=None)
                    await db.delete_wonder_trade(uri)

                else:
                    uri = uri.lstrip('_')
                    embed = create_basic_embed("", uri)
                    await interaction.followup.send(embed=embed)

            else:
                embed = create_basic_embed("", response)
                await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error processing the receive command: {e}")
            embed = create_error_embed('An error occurred when trying to receive the wonder trade.')
            await interaction.followup.send(embed=embed, ephemeral=False)

    async def lyrics(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            if not await restriction_check(interaction):
                return

            player: wavelink.Player = interaction.guild.voice_client
            if not player or not player.connected:
                embed = create_error_embed("The bot is not connected to a voice channel.")
                await interaction.followup.send(embed=embed)
                return

            response = await player.node.send(method="GET",
                                              path=f"v4/sessions/{player.node.session_id}/players/{player.guild.id}/lyrics")
            if 'lines' in response:
                lyrics_lines = response['lines']
                lyrics_text = "\n".join([f"{line['line']}" for line in lyrics_lines if line.get('line')])
                if lyrics_text:
                    embed = create_basic_embed(f"Lyrics: {response.get('track', {}).get('title', 'Current Track')}", lyrics_text
                    ).add_field(
                        name="Artist", value=response.get('track', {}).get('author', 'Unknown Artist')
                    ).set_footer(text=f"Requested by {interaction.user.display_name}",
                                 icon_url=interaction.user.display_avatar.url)
                    await interaction.followup.send(embed=embed)
                else:
                    embed = create_error_embed("Oops, I was unable to find lyrics for this song.")
                    await interaction.followup.send(embed=embed)
            else:
                embed = create_error_embed("Oops, I was unable to find lyrics for this song.")
                await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error processing the lyrics command: {e}")
            embed = create_error_embed("Oops, I was unable to find lyrics for this song.")
            await interaction.followup.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        logger.debug("Voice state update triggered.")

        voice_state = member.guild.voice_client

        if voice_state is None or not isinstance(voice_state, wavelink.Player):
            return

        if len(voice_state.channel.members) == 1:
            try:
                await asyncio.sleep(10)
                if len(voice_state.channel.members) == 1:
                    text_channel = self.bot.get_channel(voice_state.interaction_channel_id)
                    if text_channel:
                        await self.send_inactivity_message(text_channel)

                    logger.debug("Setting was_forcefully_stopped flag to True for inactivity.")
                    voice_state.was_forcefully_stopped = True
                    await self.disconnect_and_cleanup(voice_state)
            except asyncio.CancelledError:
                logger.warning("Inactivity check was cancelled.")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f'Node {payload.node.identifier} is ready!')

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        if player and hasattr(player, 'interaction_channel_id'):
            channel = self.bot.get_channel(player.interaction_channel_id)
            if channel:
                await self.send_inactivity_message(channel)
        logger.debug("Setting was_forcefully_stopped flag to True for inactivity.")
        player.was_forcefully_stopped = True
        await self.disconnect_and_cleanup(player)

    async def send_inactivity_message(self, channel: discord.TextChannel):
        try:
            embed = create_basic_embed(
                "🎵 Music Monkey Left Due to Inactivity 🎵",
                "Oops, I left the voice channel due to inactivity. 😴\n"
                "Don't worry, though! I'm always ready to swing back into action when you need me. "
                "Just start playing another song, and I'll be there with you! 🎶\n\n"
            )
            await channel.send(embed=embed)

        except discord.errors.Forbidden as e:
            logger.error(f"Failed to send inactivity message due to missing permissions: {e}")
        except Exception as e:
            logger.error(f"Unexpected error when sending inactivity message: {e}")

    async def disconnect_and_cleanup(self, player: wavelink.Player):
        try:
            await player.stop()
            await player.disconnect()
            if hasattr(player, 'now_playing_message') and player.now_playing_message:
                try:
                    await player.now_playing_message.delete()
                except discord.NotFound:
                    pass
                except discord.HTTPException as e:
                    logger.error(f"Failed to delete now playing message: {e}")
            player.now_playing_message = None
        except Exception as e:
            logger.error(f"Error during disconnect and cleanup: {e}")
        finally:
            player.was_forcefully_stopped = False

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        player.inactive_timeout = 10
        track: wavelink.Playable = payload.track

        requester_id = getattr(track.extras, 'requester_id', None)
        requester = None
        if requester_id:
            try:
                requester = await self.bot.fetch_user(requester_id)
            except discord.NotFound:
                requester = None
            except Exception as e:
                logger.error(f"Failed to fetch user {requester_id}: {e}")
                requester = None

        duration = format_duration(track.length)

        embed = create_basic_embed("Now Playing", f"**{track.title}** by `{track.author}`\nRequested by: {requester.display_name if requester else 'AutoPlay'}\nDuration: {duration}"
        )
        if track.artwork:
            embed.set_image(url=track.artwork)

        if hasattr(player, 'interaction_channel_id'):
            channel = self.bot.get_channel(player.interaction_channel_id)
            if channel:
                if hasattr(player, 'now_playing_message') and player.now_playing_message:
                    try:
                        await player.now_playing_message.edit(embed=embed, view=player.now_playing_view)
                    except (discord.NotFound, discord.Forbidden):
                        view = MusicButtons(player, self)
                        player.now_playing_message = await channel.send(embed=embed, view=view)
                        player.now_playing_view = view
                    except discord.HTTPException as e:
                        logger.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    view = MusicButtons(player, self)
                    player.now_playing_message = await channel.send(embed=embed, view=view)
                    player.now_playing_view = view
            else:
                logger.error("Cannot find the channel to send the now playing message.")
        else:
            logger.error("Interaction channel ID not set on player.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player

        if player:
            if getattr(player, 'was_forcefully_stopped', False):
                logger.debug(
                    "Player was manually stopped or disconnected due to inactivity. Skipping auto-play of next track."
                )
                player.was_forcefully_stopped = False
                return

            try:
                if player.queue.mode == wavelink.QueueMode.loop:
                    logger.debug("Looping current track.")
                    await player.play(payload.track)
                    return

                if player.queue.mode == wavelink.QueueMode.loop_all and player.queue.is_empty:
                    logger.debug("Looping entire queue.")
                    if not hasattr(player.queue, 'original_tracks') or not player.queue.original_tracks:
                        player.queue.original_tracks = player.queue.history.copy()
                    for track in player.queue.original_tracks:
                        player.queue.put(track)

                next_track = player.queue.get()
                logger.debug(f"Playing next track: {next_track.title}")
                await player.play(next_track)

                requester_id = getattr(next_track.extras, 'requester_id', None)
                requester = await self.bot.fetch_user(requester_id) if requester_id else "AutoPlay"

                duration = format_duration(next_track.length)

                embed = create_basic_embed(
                    "Now Playing",
                    f"**{next_track.title}** by `{next_track.author}`\nRequested by: {requester.display_name if requester_id else 'AutoPlay'}\nDuration: {duration}"
                )
                if next_track.artwork:
                    embed.set_image(url=next_track.artwork)

                if hasattr(player, 'now_playing_message') and player.now_playing_message:
                    try:
                        await player.now_playing_message.edit(embed=embed)
                    except (discord.NotFound, discord.Forbidden):
                        channel = self.bot.get_channel(player.interaction_channel_id)
                        if channel:
                            player.now_playing_message = await channel.send(embed=embed)
                    except discord.HTTPException as e:
                        logger.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    channel = self.bot.get_channel(player.interaction_channel_id)
                    if channel:
                        player.now_playing_message = await channel.send(embed=embed)
            except wavelink.QueueEmpty:
                logger.debug("Queue is empty and no looping mode is active.")
                embed = create_basic_embed(
                    "🎵 Nothing is Playing 🎵",
                    "The music queue is empty, and nothing is currently playing. 🎶\n"
                    "Start playing a new song to fill the air with tunes!"
                )
                if hasattr(player, 'now_playing_message') and player.now_playing_message:
                    try:
                        await player.now_playing_message.edit(embed=embed, view=None)
                    except (discord.NotFound, discord.Forbidden):
                        channel = self.bot.get_channel(player.interaction_channel_id)
                        if channel:
                            player.now_playing_message = await channel.send(embed=embed)
                    except discord.HTTPException as e:
                        logger.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    channel = self.bot.get_channel(player.interaction_channel_id)
                    if channel:
                        player.now_playing_message = await channel.send(embed=embed)

    async def user_in_voice(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        return member.voice and member.voice.channel == interaction.guild.voice_client.channel if interaction.guild.voice_client else False


# Function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(MusicService(bot))
