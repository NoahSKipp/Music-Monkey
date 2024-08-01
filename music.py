# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 21.04.2024                    #
# ========================================= #

import discord
from discord import app_commands, Interaction, Embed, ButtonStyle, ui
from discord.ext import commands, tasks
import wavelink
import logging
import config
import database as db
from datetime import datetime, timedelta
import asyncio
import aiohttp

# Set up the view class for the queue buttons
class QueuePaginationView(ui.View):
    def __init__(self, cog, interaction, current_page, total_pages):
        super().__init__(timeout=None)
        self.cog = cog
        self.interaction = interaction
        self.current_page = current_page
        self.total_pages = total_pages

        # Dynamically set button disabled states upon initialization
        self.children[0].disabled = self.current_page <= 1  # First button
        self.children[1].disabled = self.current_page <= 1  # Back button
        self.children[2].disabled = self.current_page >= self.total_pages  # Next button
        self.children[3].disabled = self.current_page >= self.total_pages  # Last button

    # Sets up the button to switch to the first page of the queue embed
    @ui.button(label="FIRST", style=ButtonStyle.grey, custom_id="first_queue_page")
    async def first_page(self, interaction: Interaction, button: ui.Button):
        self.current_page = 1
        await self.cog.display_queue(interaction, self.current_page, edit=True)
        await interaction.response.send_message()

    # Sets up the button to switch to the previous page of the queue embed
    @ui.button(label="BACK", style=ButtonStyle.primary, custom_id="previous_queue_page")
    async def previous_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.cog.display_queue(interaction, self.current_page, edit=True)
            await interaction.response.send_message()
        button.disabled = self.current_page <= 1

    # Sets up the button to switch to the next page of the queue embed
    @ui.button(label="NEXT", style=ButtonStyle.primary, custom_id="next_queue_page")
    async def next_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self.cog.display_queue(interaction, self.current_page, edit=True)
            await interaction.response.send_message()
        button.disabled = self.current_page >= self.total_pages

    # Sets up the button to switch to the last page of the queue embed
    @ui.button(label="LAST", style=ButtonStyle.grey, custom_id="last_queue_page")
    async def last_page(self, interaction: Interaction, button: ui.Button):
        self.current_page = self.total_pages
        await self.cog.display_queue(interaction, self.current_page, edit=True)
        await interaction.response.send_message()


# Helper function to format times
def format_duration(ms):
    # Convert milliseconds to minutes and seconds
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    hours = int((ms / (1000 * 60 * 60)) % 24)

    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes}:{seconds:02}"


# Set up the class for Track
class Track(wavelink.Playable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = None


# Set up the class for the Music cog
class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_vote_reminder_time_per_guild = {}
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    async def has_voted(self, user: discord.User, guild: discord.Guild) -> bool:
        # Log guild and role checks
        print(f"Checking vote status for user {user.id} in guild {guild.id}")

        # Check if the command is used in the exempt guild
        if guild.id == config.EXEMPT_GUILD_ID:
            return True

        # Check if the user has the exempt role in the exempt guild
        exempt_guild = self.bot.get_guild(config.EXEMPT_GUILD_ID)
        if not exempt_guild:
            try:
                exempt_guild = await self.bot.fetch_guild(config.EXEMPT_GUILD_ID)
            except discord.NotFound:
                return False
            except discord.Forbidden:
                return False
            except Exception as e:
                return False

        try:
            exempt_member = await exempt_guild.fetch_member(user.id)
            if exempt_member:
                roles = [role.id for role in exempt_member.roles]
                print(f"Exempt member found in exempt guild with roles: {roles}")
                if config.EXEMPT_ROLE_ID in roles:
                    print(
                        f"User {user.id} has the exempt role {config.EXEMPT_ROLE_ID} in exempt guild {config.EXEMPT_GUILD_ID}.")
                    return True
        except discord.NotFound:
            return False
        except discord.Forbidden:
            return False
        except Exception as e:
            return False

        # If not exempt by guild or role, check vote status on Top.gg
        url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
        headers = {
            "Authorization": f"Bearer {config.TOPGG_TOKEN}",
            "X-Auth-Key": config.AUTHORIZATION_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    voted = data.get("voted") == 1
                    return voted
                else:
                    return False

    async def vote_reminder(self, interaction: Interaction):
        guild_id = str(interaction.guild_id)
        current_time = datetime.now()

        if (guild_id in self.last_vote_reminder_time_per_guild and
                (current_time - self.last_vote_reminder_time_per_guild[guild_id]) > timedelta(hours=12)):
            await self.send_vote_reminder(interaction)
            self.last_vote_reminder_time_per_guild[guild_id] = current_time
        elif guild_id not in self.last_vote_reminder_time_per_guild:
            await self.send_vote_reminder(interaction)
            self.last_vote_reminder_time_per_guild[guild_id] = current_time

    async def send_vote_reminder(self, interaction):
        embed = Embed(
            title="Support Us by Voting!",
            description="🌟 Your votes help keep the bot free and continuously improving. Please take a moment to support us!",
            color=discord.Color.green()
        )
        embed.add_field(name="Vote Here", value="[Vote on Top.gg](https://top.gg/bot/1228071177239531620/vote)")
        embed.set_thumbnail(url=interaction.client.user.avatar.url)
        embed.set_footer(text="Thank you for your support! Your votes make a big difference!")
        await interaction.followup.send(embed=embed, ephemeral=False)

    async def error_handler(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            await interaction.response.send_message(
                f"Command is on cooldown. Try again in {error.retry_after:.2f} seconds.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error occurred while processing the command.",
                ephemeral=True
            )

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        logging.debug("Voice state update triggered.")

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

                    logging.debug("Setting was_forcefully_stopped flag to True for inactivity.")
                    voice_state.was_forcefully_stopped = True
                    await self.disconnect_and_cleanup(voice_state)
            except asyncio.CancelledError:
                logging.warning("Inactivity check was cancelled.")

    async def user_in_voice(self, interaction):
        member = interaction.user
        return member.voice and member.voice.channel == interaction.guild.voice_client.channel if interaction.guild.voice_client else False

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

        dj_only = await db.get_dj_only_enabled(interaction.guild_id)
        dj_role_id = await db.get_dj_role(interaction.guild_id)
        restricted_commands = await db.get_restricted_commands(interaction.guild_id)

        if not dj_only:
            return True

        if interaction.command.name in restricted_commands:
            has_permissions = interaction.user.guild_permissions.manage_roles
            is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

            if has_permissions or is_dj:
                return True

            await interaction.response.send_message(
                "DJ-only mode is enabled. You need DJ privileges to use this command.",
                ephemeral=True
            )
            return False
        return True

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f'Node {payload.node.identifier} is ready!')

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        if player and hasattr(player, 'interaction_channel_id'):
            channel = self.bot.get_channel(player.interaction_channel_id)
            if channel:
                await self.send_inactivity_message(channel)
        print("Setting was_forcefully_stopped flag to True for inactivity.")
        player.was_forcefully_stopped = True
        await self.disconnect_and_cleanup(player)

    async def send_inactivity_message(self, channel: discord.TextChannel):
        try:
            embed = discord.Embed(
                title="🎵 Music Monkey Left Due to Inactivity 🎵",
                description=(
                    "Oops, I left the voice channel due to inactivity. 😴\n"
                    "Don't worry, though! I'm always ready to swing back into action when you need me. "
                    "Just start playing another song, and I'll be there with you! 🎶\n\n"
                ),
                color=discord.Color.dark_red()
            )
            await channel.send(embed=embed)
        except discord.errors.Forbidden as e:
            logging.error(f"Failed to send inactivity message due to missing permissions: {e}")
        except Exception as e:
            logging.error(f"Unexpected error when sending inactivity message: {e}")

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
                    logging.error(f"Failed to delete now playing message: {e}")
            player.now_playing_message = None
        except Exception as e:
            logging.error(f"Error during disconnect and cleanup: {e}")
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
                logging.error(f"Failed to fetch user {requester_id}: {e}")
                requester = None

        duration = format_duration(track.length)

        embed = discord.Embed(
            title="Now Playing",
            description=f"**{track.title}** by `{track.author}`\nRequested by: {requester.display_name if requester else 'AutoPlay'}\nDuration: {duration}",
            color=discord.Color.dark_red()
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
                        logging.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    view = MusicButtons(player, self)
                    player.now_playing_message = await channel.send(embed=embed, view=view)
                    player.now_playing_view = view
            else:
                logging.error("Cannot find the channel to send the now playing message.")
        else:
            logging.error("Interaction channel ID not set on player.")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player: wavelink.Player = payload.player

        if player:
            if getattr(player, 'was_forcefully_stopped', False):
                logging.debug(
                    "Player was manually stopped or disconnected due to inactivity. Skipping auto-play of next track.")
                player.was_forcefully_stopped = False
                return

            try:
                if player.queue.mode == wavelink.QueueMode.loop:
                    logging.debug("Looping current track.")
                    await player.play(payload.track)
                    return

                if player.queue.mode == wavelink.QueueMode.loop_all and player.queue.is_empty:
                    logging.debug("Looping entire queue.")
                    if not hasattr(player.queue, 'original_tracks') or not player.queue.original_tracks:
                        player.queue.original_tracks = player.queue.history.copy()
                    for track in player.queue.original_tracks:
                        player.queue.put(track)

                next_track = player.queue.get()
                logging.debug(f"Playing next track: {next_track.title}")
                await player.play(next_track)

                requester_id = getattr(next_track.extras, 'requester_id', None)
                requester = await self.bot.fetch_user(requester_id) if requester_id else "AutoPlay"

                duration = format_duration(next_track.length)

                embed = discord.Embed(
                    title="Now Playing",
                    description=f"**{next_track.title}** by `{next_track.author}`\nRequested by: {requester.display_name if requester_id else 'AutoPlay'}\nDuration: {duration}",
                    color=discord.Color.dark_red()
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
                        logging.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    channel = self.bot.get_channel(player.interaction_channel_id)
                    if channel:
                        player.now_playing_message = await channel.send(embed=embed)
            except wavelink.QueueEmpty:
                logging.debug("Queue is empty and no looping mode is active.")
                embed = discord.Embed(
                    title="🎵 Nothing is Playing 🎵",
                    description=(
                        "The music queue is empty, and nothing is currently playing. 🎶\n"
                        "Start playing a new song to fill the air with tunes!"
                    ),
                    color=discord.Color.dark_red()
                )
                if hasattr(player, 'now_playing_message') and player.now_playing_message:
                    try:
                        await player.now_playing_message.edit(embed=embed, view=None)
                    except (discord.NotFound, discord.Forbidden):
                        channel = self.bot.get_channel(player.interaction_channel_id)
                        if channel:
                            player.now_playing_message = await channel.send(embed=embed)
                    except discord.HTTPException as e:
                        logging.error(f"Failed to edit message due to an HTTP error: {e}")
                else:
                    channel = self.bot.get_channel(player.interaction_channel_id)
                    if channel:
                        player.now_playing_message = await channel.send(embed=embed)

    # Sets up the player queue display
    async def display_queue(self, interaction: discord.Interaction, page: int, edit=False):
        # Gets the player object of the bot in the current guild's voice channel
        player = interaction.guild.voice_client
        # If there's no player, no player queue or an empty player queue, displays a message
        if not player or not player.queue or player.queue.is_empty:
            await interaction.response.send_message("The queue is empty.")
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
        embed = discord.Embed(title=f'Queue - Page {page} of {total_pages}', description=queue_description,
                              color=discord.Color.dark_red())
        view = QueuePaginationView(self, interaction, page, total_pages)

        if edit:
            await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='play', description='Play or queue a song from a URL or search term')
    @app_commands.describe(query='URL or search term of the song to play')
    async def play(self, interaction: Interaction, query: str):
        try:
            await interaction.response.defer(ephemeral=False)

            if not interaction.guild.voice_client:
                if not interaction.user.voice or not interaction.user.voice.channel:
                    await interaction.followup.send("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
                    return
            else:
                if not await self.user_in_voice(interaction):
                    await interaction.followup.send(
                        "You must be in the same voice channel as the bot to use this command.", ephemeral=True)
                    return

            await self.play_song(interaction, query)
        except discord.errors.NotFound:
            logging.error("Interaction not found or expired.")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    async def play_song(self, interaction: Interaction, query: str):
        try:
            await self.vote_reminder(interaction)

            if query.startswith("https://") or query.startswith("http://"):
                results = await wavelink.Playable.search(query)
            else:
                results = await wavelink.Playable.search(query, source=wavelink.enums.TrackSource.YouTube)

            if not results:
                await interaction.followup.send('No tracks found with that query.', ephemeral=True)
                return

            track = results[0]

            if "youtube.com" not in track.uri and "youtu.be" not in track.uri:
                if not await self.has_voted(interaction.user, interaction.guild):
                    embed = discord.Embed(
                        description=(
                            "Playing tracks from sources other than YouTube is a special feature just for our awesome voters.\n "
                            "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. \n"
                            "As a bonus, Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642> "
                        ),
                        color=discord.Color.green()
                    )
                    embed.set_author(name="Unlock This Feature!", icon_url=self.bot.user.display_avatar.url)
                    embed.set_footer(text="Thanks for your support!")
                    await interaction.followup.send(embed=embed, ephemeral=True)
                    return

            channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
            if not channel:
                await interaction.followup.send("You must be in a voice channel to play music.", ephemeral=True)
                return

            node = wavelink.Pool.get_node
            if node is None:
                await interaction.followup.send("No node available. Please try again later.", ephemeral=True)
                return

            player = interaction.guild.voice_client
            if not player:
                player = await channel.connect(cls=wavelink.Player)
                player.guild_id = interaction.guild_id
                player.interaction_channel_id = interaction.channel_id

            if isinstance(results, wavelink.Playlist):
                tracks = results.tracks
                embed = Embed(
                    title="**Added to Queue**",
                    description=f"{len(tracks)} tracks from the playlist",
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text=f"Queue length: {len(player.queue) + len(tracks)}")
                for track in tracks:
                    track.extras.requester_id = interaction.user.id
                    player.queue.put(track)
                await interaction.followup.send(embed=embed, ephemeral=False)
            else:
                track = results[0]
                track.extras.requester_id = interaction.user.id
                player.queue.put(track)
                embed = Embed(
                    title="**Added to Queue**",
                    description=f"{track.title} by {track.author}",
                    color=discord.Color.dark_red()
                )
                embed.set_footer(text=f"Queue length: {len(player.queue)}")
                await interaction.followup.send(embed=embed, ephemeral=False)

            if not player.playing and not player.paused:
                next_track = player.queue.get()
                await player.play(next_track)

            await db.enter_song(player.current.identifier, player.current.title, player.current.author,
                                player.current.length, player.current.uri)
            await db.increment_plays(interaction.user.id, player.current.identifier, interaction.guild_id)

        except discord.errors.NotFound:
            logging.error("Interaction not found or expired.")
        except Exception as e:
            logging.error(f"Error processing the play command: {e}")
            try:
                await interaction.followup.send('An error occurred while trying to play the track.', ephemeral=True)
            except discord.errors.NotFound:
                logging.error("Failed to send follow-up message: Interaction not found or expired.")

    # Command to skip the current song
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='skip', description='Skip the current playing song')
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player: wavelink.Player = interaction.guild.voice_client
        if player is None or not player.connected:
            await interaction.followup.send("The queue is empty, as I'm not active right now.", ephemeral=True)
            return

        # Stops the current track and trigger the track end event
        await player.stop()

        # Check if the queue is empty before attempting to get the next track
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)  # Play the next track
            await interaction.followup.send(f"Now playing: {next_track.title}")
        else:
            await interaction.followup.send("The queue is currently empty.")

    # Handles command execution errors and delegates to the error_handler
    @skip.error
    async def skip_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to pause the music playback
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='pause', description='Pause the music playback')
    async def pause(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if player and isinstance(player, wavelink.Player):
            if not player.paused:
                await player.pause(True)  # Pause the playback
                await interaction.followup.send("Playback has been paused.")
            else:
                await interaction.followup.send("Playback is already paused.", ephemeral=True)
        else:
            await interaction.followup.send("The bot is not connected to a voice channel.", ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @pause.error
    async def pause_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to resume the music playback (if paused)
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='resume', description='Resume the music playback if paused')
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if player and isinstance(player, wavelink.Player):
            if player.paused:
                await player.pause(False)  # Resume playback
                await interaction.followup.send("Playback has been resumed.")
            else:
                await interaction.followup.send("Playback is not paused.", ephemeral=True)
        else:
            await interaction.followup.send("The bot is not connected to a voice channel.", ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @resume.error
    async def resume_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to stop the music playback, disconnect the bot and clear the queue
    # noinspection PyTypeChecker
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='stop', description='Stop the music and clear the queue')
    async def stop(self, interaction: discord.Interaction):
        logging.debug("Stop command received.")
        await interaction.response.defer(ephemeral=True)  # Signal to Discord that more time is needed to process
        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if player:
            logging.debug("Setting was_forcefully_stopped flag to True.")
            player.was_forcefully_stopped = True  # Set the flag before stopping the player
            await self.disconnect_and_cleanup(player)
            await interaction.followup.send('Stopped the music and cleared the queue.', ephemeral=False)

    # Handles command execution errors and delegates to the error_handler
    @stop.error
    async def stop_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to display the queue
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='queue', description='Show the current music queue')
    async def show_queue(self, interaction: discord.Interaction):
        await self.display_queue(interaction, 1)

    # Handles command execution errors and delegates to the error_handler
    @show_queue.error
    async def queue_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to clear the queue
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='clear', description='Clear the current music queue')
    async def clear(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            # If queue is empty, send a message
            await interaction.followup.send("The queue is already empty.", ephemeral=True)
        else:
            player.queue.clear()  # Clear the queue
            await interaction.followup.send("The music queue has been cleared.", ephemeral=True)

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to remove songs from the queue that were requested by users no longer in the voice channel
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='cleargone',
                          description='Remove tracks from the queue requested by users not in the voice channel')
    async def cleargone(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                description=(
                    "This feature is available to our awesome voters.\n "
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. \n"
                    "As a bonus, Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642> "
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Unlock This Feature!", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.followup.send("The queue is empty.", ephemeral=True)
            return

        voice_channel_members = {member.id for member in interaction.user.voice.channel.members}
        initial_count = len(player.queue)
        tracks_to_remove = [i for i, track in enumerate(player.queue) if
                            not hasattr(track.extras, 'requester_id') or getattr(track.extras, 'requester_id',
                                                                                 None) not in voice_channel_members]

        for index in reversed(tracks_to_remove):
            player.queue.delete(index)

        removed_count = initial_count - len(player.queue)
        await interaction.followup.send(
            f"Removed {removed_count} tracks requested by users not currently in the channel.")

    @cleargone.error
    async def cleargone_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to move a specific song in the queue to a new position in the queue
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='move', description='Move a song in the queue from one position to another')
    @app_commands.describe(position="The song's current position in the queue",
                           new_position="The song's new position in the queue")
    async def move(self, interaction: discord.Interaction, position: int, new_position: int):
        await interaction.response.defer(ephemeral=False)

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.followup.send("The queue is empty.", ephemeral=True)
            return

        # Convert to zero-indexed
        position -= 1
        new_position -= 1

        if position < 0 or new_position < 0 or position >= len(player.queue) or new_position >= len(player.queue):
            await interaction.followup.send("Invalid positions provided.", ephemeral=True)
            return

        try:
            # Retrieve the track from the current position
            track = player.queue.get_at(position)
            # Remove the track from the current position
            player.queue.remove(track)
            # Insert the track at the new position
            player.queue.put_at(new_position, track)

            await interaction.followup.send(
                f"Moved track from position {position + 1} to position {new_position + 1}.", ephemeral=False)
        except (IndexError, wavelink.QueueEmpty) as e:
            await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @move.error
    async def move_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to remove a song from the queue
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='remove', description='Remove a specific song from the queue by its position')
    @app_commands.describe(position='Position in the queue of the song to remove')
    async def remove(self, interaction: discord.Interaction, position: int):
        await interaction.response.defer(ephemeral=True)

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.followup.send("The queue is empty.", ephemeral=True)
            return

        if position < 1 or position > len(player.queue):
            await interaction.followup.send("Invalid position in the queue.", ephemeral=True)
            return

        try:
            # Delete the track at the specified position, adjusted for zero-indexed list
            player.queue.delete(position - 1)
            await interaction.followup.send(f"Removed track at position {position} from the queue.", ephemeral=False)
        except IndexError:
            await interaction.followup.send("No track found at the specified position.", ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to shuffle the queue
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='shuffle', description='Shuffles the current music queue')
    async def shuffle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or not player.queue or not hasattr(player,
                                                         'now_playing_message') or not player.now_playing_message:
            await interaction.followup.send(
                "Shuffle can only be used when a song is playing and visible in the Now Playing message.",
                ephemeral=True)
            return

        # Shuffle the queue
        player.queue.shuffle()

        # Send confirmation message
        await interaction.followup.send("The queue has been shuffled.", ephemeral=False)

    # Handles command execution errors and delegates to the error_handler
    @shuffle.error
    async def shuffle_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to toggle autoplay on the player
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='autoplay', description='Toggle AutoPlay mode for automatic music recommendations')
    @app_commands.choices(mode=[
        app_commands.Choice(name='enabled', value='enabled'),
        app_commands.Choice(name='disabled', value='disabled')
    ])
    async def autoplay(self, interaction: discord.Interaction, mode: str):
        await interaction.response.defer(ephemeral=True)

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        # Apply the autoplay mode based on user choice
        if mode == 'enabled':
            player.autoplay = wavelink.AutoPlayMode.enabled
            await interaction.followup.send("AutoPlay has been enabled.", ephemeral=True)
        elif mode == 'disabled':
            player.autoplay = wavelink.AutoPlayMode.disabled
            await interaction.followup.send("AutoPlay has been disabled.", ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @autoplay.error
    async def autoplay_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='loop', description='Toggle loop mode for the current track or queue')
    @app_commands.describe(mode="Select loop mode.")
    @app_commands.choices(mode=[
        app_commands.Choice(name="Normal", value="normal"),
        app_commands.Choice(name="Loop Song", value="loop"),
        app_commands.Choice(name="Loop Queue", value="loop_all")
    ])
    async def loop(self, interaction: discord.Interaction, mode: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player:
            await interaction.followup.send("I'm not connected to a voice channel.", ephemeral=True)
            return

        if not player.playing:
            await interaction.followup.send("No music is currently playing.", ephemeral=True)
            return

        # Set the loop mode based on user input
        if mode.value == "normal":
            player.queue.mode = wavelink.QueueMode.normal
            mode_description = "normal (no looping)"
        elif mode.value == "loop":
            player.queue.mode = wavelink.QueueMode.loop
            mode_description = "looping current track"
        elif mode.value == "loop_all":
            player.queue.mode = wavelink.QueueMode.loop_all
            mode_description = "looping entire queue"

        # Send a response back to the user
        await interaction.followup.send(f"Queue mode set to {mode_description}.", ephemeral=False)

    # Handles command execution errors and delegates to the error_handler
    @loop.error
    async def loop_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to jump to a specific time in the current track
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='jump', description='Jump to a specific time in the current track')
    @app_commands.describe(time='Time to jump to in the format mm:ss')
    async def jump(self, interaction: discord.Interaction, time: str):
        await interaction.response.defer(ephemeral=True)

        if not await self.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        # Validate and parse the time format
        try:
            minutes, seconds = map(int, time.split(':'))
            position = (minutes * 60 + seconds) * 1000  # Convert time to milliseconds
        except ValueError:
            await interaction.followup.send("Invalid time format. Please use mm:ss format.", ephemeral=True)
            return

        # Get the current player
        player = interaction.guild.voice_client
        if player and player.playing:
            # Seek to the desired position
            await player.seek(position)
            await interaction.followup.send(f"Jumped to {minutes} minutes and {seconds} seconds.", ephemeral=False)
        else:
            await interaction.followup.send("There is no active player or track playing.", ephemeral=True)

    @jump.error
    async def jump_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to apply filters to the playback
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='filters', description='Select a filter to apply')
    async def filters(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player = interaction.guild.voice_client
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label='Bass Boost', description='Enhances the bass frequencies', value='bass_boost'),
            discord.SelectOption(label='Nightcore', description='Increases the pitch and speed', value='nightcore'),
            discord.SelectOption(label='Vaporwave', description='Adds a slow rotation and slight pitch shift',
                                 value='vaporwave'),
            discord.SelectOption(label='Karaoke', description='Reduces the lead vocals for a karaoke effect',
                                 value='karaoke'),
            discord.SelectOption(label='Tremolo', description='Adds a tremolo effect with periodic volume oscillation',
                                 value='tremolo'),
            discord.SelectOption(label='Distortion', description='Adds a distortion effect for a grittier sound',
                                 value='distortion')
        ]

        view = FilterSelectView(options, interaction.user.id, player)
        await interaction.followup.send("Please select a filter to apply:", view=view, ephemeral=True)

    @filters.error
    async def filters_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to reset the filters back to default playback
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='resetfilter', description='Reset all filters')
    async def resetfilter(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        player = interaction.guild.voice_client
        if not player:
            await interaction.followup.send("Not connected to a voice channel.", ephemeral=True)
            return

        # Reset all filters
        filters = wavelink.Filters()
        filters.reset()
        await player.set_filters(filters)
        await interaction.followup.send("All filters have been reset!", ephemeral=True)

    @resetfilter.error
    async def resetfilter_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to create a recommendation/wondertrade.
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='wondertrade', description='Submit a song recommendation to anyone else using the bot!')
    @app_commands.describe(query='The name/link to the song you want to recommend',
                           note='A small (up to 60 characters) message to go with your recommendation!')
    async def wondertrade(self, interaction: Interaction, query: str, note: str):
        await interaction.response.defer(ephemeral=True)
        # Try to get a song from the extracted query to send as a wondertrade.
        try:
            # Searches for a song with the user's provided query.
            search_result = await wavelink.Playable.search(query)

            # If the query yields no results, send a message and exit the function.
            if not search_result:
                await interaction.followup.send('No tracks found with that query.', ephemeral=True)
                return

            # If the query is a playlist, send a message and exit the function.
            elif isinstance(search_result, wavelink.Playlist):
                await interaction.followup.send('Please only send songs, not playlists.', ephemeral=True)
                return

            # Otherwise, attempt to create the wondertrade.
            else:
                # Note: search_result is initialized as a list, so we extract the first playable, the searched song.
                search_result = search_result[0]
                result = await db.submit_wonder_trade(search_result.identifier, search_result.title,
                                                      search_result.author, search_result.length, search_result.uri,
                                                      interaction.user.id, note)
                # Output the result to the user.
                print("Wondertrade creation result:", result)
                await interaction.followup.send(result, ephemeral=True)

        # Otherwise, send an error message.
        except Exception as e:
            logging.error(f"Error processing the wondertrade command: {e}")
            await interaction.followup.send('An error occurred when trying to create the wonder trade.', ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
    @wondertrade.error
    async def wondertrade_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to receive a recommendation/wondertrade.
    @discord.app_commands.checks.cooldown(1, 1800)  # 1 use every 30 seconds
    @app_commands.command(name='receive', description='Receive a song recommendation from anyone else using the bot!')
    async def receive(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
        if not channel:
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client

        if player:
            if not await self.user_in_voice(interaction):
                await interaction.followup.send("You must be in the same voice channel as the bot to use this command.",
                                                ephemeral=True)
                return
        else:
            try:
                player = await channel.connect(cls=wavelink.Player)
                player.guild_id = interaction.guild_id
                player.interaction_channel_id = interaction.channel_id
            except Exception as e:
                logging.error(f"Error connecting to voice channel: {e}")
                await interaction.followup.send("Failed to connect to the voice channel.", ephemeral=True)
                return

        try:
            response = await db.receive_wonder_trade(interaction.user.id)

            if isinstance(response, tuple):
                uri, note = response
                logging.info(f"Received wonder trade result: {uri}, {note}")

                if not uri.startswith('_'):
                    if note:
                        embed = discord.Embed(
                            title="You've received a song recommendation note!",
                            description=f"Oh! It seems the person who recommended this song left you a note!\n||{note}||",
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="Messages aren't monitored or filtered. View at your own discretion.")
                        await interaction.followup.send(embed=embed)

                    await self.play_song(interaction, uri)
                    await db.delete_wonder_trade(uri)

                else:
                    uri = uri.lstrip('_')
                    await interaction.followup.send(uri)

            else:
                await interaction.followup.send(response)

        except Exception as e:
            logging.error(f"Error processing the receive command: {e}")
            await interaction.followup.send('An error occurred when trying to receive the wonder trade.',
                                            ephemeral=False)

    # Handles command execution errors and delegates to the wondertrade_specific_error_handler
    @receive.error
    async def receive_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.wondertrade_specific_error_handler(interaction, error)

    async def wondertrade_specific_error_handler(self, interaction: discord.Interaction,
                                                 error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CommandOnCooldown):
            minutes = error.retry_after / 60
            await interaction.response.send_message(
                f"You can only receive a wondertrade once every 30 minutes. Wait a little and try again in {minutes:.2f} minutes!",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "An error occurred while processing the command.",
                ephemeral=True
            )

    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    @app_commands.command(name='lyrics', description='Fetch lyrics for the current playing track')
    async def lyrics(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not await self.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                description=(
                    "This feature is available to our awesome voters.\n "
                    "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk. \n"
                    "As a bonus, Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step and enjoy all the tunes! <a:tadaMM:1258473486003732642> "
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Unlock This Feature!", icon_url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player: wavelink.Player = interaction.guild.voice_client
        if not player or not player.connected:
            await interaction.followup.send("The bot is not connected to a voice channel.")
            return

        try:
            response = await player.node.send(method="GET",
                                              path=f"v4/sessions/{player.node.session_id}/players/{player.guild.id}/lyrics")
            if 'lines' in response:
                lyrics_lines = response['lines']
                lyrics_text = "\n".join([f"{line['line']}" for line in lyrics_lines if line.get('line')])
                if lyrics_text:
                    embed = discord.Embed(title=f"Lyrics: {response.get('track', {}).get('title', 'Current Track')}",
                                          description=lyrics_text,
                                          color=discord.Color.dark_red())
                    embed.add_field(name="Artist", value=response.get('track', {}).get('author', 'Unknown Artist'),
                                    inline=True)
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}",
                                     icon_url=interaction.user.display_avatar.url)
                    await interaction.followup.send(embed=embed)
                else:
                    await interaction.followup.send("Oops, I was unable to find lyrics for this song.")
            else:
                error_message = response.get('error', 'Lyrics not found.')
                await interaction.followup.send(f"Oops, I was unable to find lyrics for this song.")
        except Exception as e:
            await interaction.followup.send(f"Oops, I was unable to find lyrics for this song.")

    @lyrics.error
    async def lyrics_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)


# Set up and add the view class for the filter selection
class FilterSelectView(discord.ui.View):
    def __init__(self, options, user_id, player):
        super().__init__()
        self.user_id = user_id
        self.player = player
        self.add_item(FilterSelect(options, user_id, player))


# Set up the filter select class
class FilterSelect(discord.ui.Select):
    def __init__(self, options, user_id, player):
        self.user_id = user_id
        self.player = player
        super().__init__(placeholder='Choose a filter...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):

        filter_name = self.values[0]
        if filter_name == 'bass_boost':
            await apply_bass_boost(self.player)
        elif filter_name == 'nightcore':
            await apply_nightcore(self.player)
        elif filter_name == 'vaporwave':
            await apply_vaporwave(self.player)
        elif filter_name == 'karaoke':
            await apply_karaoke(self.player)
        elif filter_name == 'tremolo':
            await apply_tremolo(self.player)
        elif filter_name == 'distortion':
            await apply_distortion(self.player)

        await interaction.response.send_message(f'Applied {filter_name.replace("_", " ").title()} filter!',
                                                ephemeral=True)


# Apply the bass boost effect
async def apply_bass_boost(player):
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
async def apply_nightcore(player):
    filters = wavelink.Filters()
    filters.timescale.set(pitch=1.25, speed=1.25)
    await player.set_filters(filters)


# Apply the vaporwave effect
async def apply_vaporwave(player):
    filters = wavelink.Filters()
    filters.timescale.set(pitch=0.8, speed=0.85)
    filters.rotation.set(rotation_hz=0.1)
    await player.set_filters(filters)


# Apply the karaoke effect
async def apply_karaoke(player):
    filters = wavelink.Filters()
    filters.karaoke.set(level=1.0, mono_level=1.0, filter_band=220.0, filter_width=100.0)
    await player.set_filters(filters)


# Apply the tremolo effect
async def apply_tremolo(player):
    filters = wavelink.Filters()
    filters.tremolo.set(frequency=4.0, depth=0.75)
    await player.set_filters(filters)


# Apply the distortion effect
async def apply_distortion(player):
    filters = wavelink.Filters()
    filters.distortion.set(sin_offset=0.5, sin_scale=0.5, cos_offset=0.5, cos_scale=0.5, tan_offset=0.5, tan_scale=0.5,
                           offset=0.5, scale=0.5)
    await player.set_filters(filters)


#   Sets up the class for the player control buttons
class MusicButtons(ui.View):
    def __init__(self, player, cog):
        super().__init__(timeout=None)
        self.player = player
        self.cog = cog

    # Checks if the user has the required permissions to interact with the buttons
    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

        dj_only = await db.get_dj_only_enabled(interaction.guild_id)
        dj_role_id = await db.get_dj_role(interaction.guild_id)
        restricted_commands = await db.get_restricted_commands(interaction.guild_id)

        if not dj_only:
            return True

        if interaction.command.name in restricted_commands:
            has_permissions = interaction.user.guild_permissions.manage_roles
            is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

            if has_permissions or is_dj:
                return True

            await interaction.response.send_message(
                "DJ-only mode is enabled. You need DJ privileges to use this command.",
                ephemeral=True
            )
            return False
        return True

    async def has_voted(self, user: discord.User, guild: discord.Guild) -> bool:
        # Log guild and role checks
        print(f"Checking vote status for user {user.id} in guild {guild.id}")

        # Check if the command is used in the exempt guild
        if guild.id == config.EXEMPT_GUILD_ID:
            return True

        # Check if the user has the exempt role in the exempt guild
        exempt_guild = self.bot.get_guild(config.EXEMPT_GUILD_ID)
        if not exempt_guild:
            try:
                exempt_guild = await self.bot.fetch_guild(config.EXEMPT_GUILD_ID)
            except discord.NotFound:
                return False
            except discord.Forbidden:
                return False
            except Exception as e:
                return False

        try:
            exempt_member = await exempt_guild.fetch_member(user.id)
            if exempt_member:
                roles = [role.id for role in exempt_member.roles]
                print(f"Exempt member found in exempt guild with roles: {roles}")
                if config.EXEMPT_ROLE_ID in roles:
                    print(
                        f"User {user.id} has the exempt role {config.EXEMPT_ROLE_ID} in exempt guild {config.EXEMPT_GUILD_ID}.")
                    return True
        except discord.NotFound:
            return False
        except discord.Forbidden:
            return False
        except Exception as e:
            return False

        # If not exempt by guild or role, check vote status on Top.gg
        url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
        headers = {
            "Authorization": f"Bearer {config.TOPGG_TOKEN}",
            "X-Auth-Key": config.AUTHORIZATION_KEY
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    voted = data.get("voted") == 1
                    return voted
                else:
                    return False

    # Sets up queue button
    @ui.button(label='QUEUE', style=ButtonStyle.green, custom_id='queue_button')
    async def show_queue(self, interaction: Interaction, button: ui.Button):
        if self.player and not self.player.queue.is_empty:
            # Starts displaying queue from the first page
            await self.cog.display_queue(interaction, 1, edit=False)
        else:
            # Respond if the queue is empty
            await interaction.response.send_message("The queue is empty.", ephemeral=True)

    # Sets up buttons for volume increase
    @ui.button(label='VOL +', style=ButtonStyle.green, custom_id='vol_up_button')
    async def volume_up(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        if not await self.cog.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.cog.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        new_volume = min(self.player.volume + 10, 100)  # Volume should not exceed 100
        await self.player.set_volume(new_volume)
        await interaction.followup.send(f'Volume increased to {new_volume}%', ephemeral=True)

    # Sets up button to pause music playback
    @ui.button(label='PAUSE', style=ButtonStyle.blurple, custom_id='pause_button')
    async def pause(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        # Check the current paused state directly from the player and toggle it
        if self.player.paused:
            await self.player.pause(False)  # If currently paused, resume playback
            button.label = 'PAUSE'  # Update the button label to 'Pause'
        else:
            await self.player.pause(True)  # If currently playing, pause playback
            button.label = 'RESUME'  # Update the button label to 'Resume'

        # Edit the message to reflect the new button label
        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)

    # Sets up the button for volume decrease
    @ui.button(label='VOL -', style=ButtonStyle.green, custom_id='vol_down_button')
    async def volume_down(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        if not await self.cog.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.cog.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        new_volume = max(self.player.volume - 10, 0)  # Volume should not go below 0
        await self.player.set_volume(new_volume)
        await interaction.followup.send(f'Volume decreased to {new_volume}%', ephemeral=True)

    # Sets up the button to skip the current song
    @ui.button(label='SKIP', style=ButtonStyle.green, custom_id='skip_button')
    async def skip(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        await self.player.skip()
        await interaction.followup.send('Skipped the current song', ephemeral=True)

    # Sets up the button to toggle the loop mode
    @ui.button(label='LOOP', style=ButtonStyle.green, custom_id='loop_button')
    async def toggle_loop(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        if not await self.cog.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.cog.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        player = interaction.guild.voice_client
        current_mode = player.queue.mode

        if current_mode == wavelink.QueueMode.normal:
            player.queue.mode = wavelink.QueueMode.loop
            button.label = "LOOP ALL"
            response = "Looping current track enabled."
        elif current_mode == wavelink.QueueMode.loop:
            player.queue.mode = wavelink.QueueMode.loop_all
            button.label = "NORMAL"
            response = "Looping all tracks enabled."
        elif current_mode == wavelink.QueueMode.loop_all:
            player.queue.mode = wavelink.QueueMode.normal
            button.label = "LOOP"
            response = "Looping disabled."

        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)
        await interaction.followup.send(response, ephemeral=True)

    # Sets up the button for the rewind functionality
    @ui.button(label='REWIND', style=ButtonStyle.green, custom_id='rewind_button')
    async def rewind(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        # Calculate the new position, ensuring it does not fall below zero
        new_position = max(0, self.player.position - 15000)
        await self.player.seek(new_position)
        await interaction.followup.send(f"Rewound 15 seconds.", ephemeral=True)

    # Sets up the button to stop the music playback
    @ui.button(label='STOP', style=ButtonStyle.red, custom_id='stop_button')
    async def stop_music(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        # Set the was_forcefully_stopped flag
        if hasattr(self.player, 'was_manually_stopped'):
            self.player.was_forcefully_stopped = True
        else:
            self.player.was_forcefully_stopped = True

        # Stops the current track, clears the queue, and disconnects the player from the channel
        await self.player.stop()
        await self.player.disconnect()
        await interaction.followup.send('Stopped the music and cleared the queue.', ephemeral=True)

        # Stop the view to prevent further interaction
        self.stop()

        # Delete the now playing message if it exists
        if hasattr(self.player, 'now_playing_message') and self.player.now_playing_message:
            try:
                await self.player.now_playing_message.delete()
            except discord.NotFound:
                pass  # If the message was already deleted, do nothing
            except discord.HTTPException as e:
                logging.error(f"Failed to delete now playing message: {e}")

        # Clear the reference to the now playing message
        self.player.now_playing_message = None

    # Sets up the button for the forward functionality
    @ui.button(label='FORWARD', style=ButtonStyle.green, custom_id='forward_button')
    async def forward(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        # Calculate the new position, ensuring it does not exceed the track's duration
        new_position = min(self.player.position + 15000, self.player.current.length)
        await self.player.seek(new_position)
        await interaction.followup.send(f"Forwarded 15 seconds.", ephemeral=True)

    # Sets up the button to toggle autoplay
    @ui.button(label='AUTOPLAY', style=ButtonStyle.green, custom_id='autoplay_button')
    async def toggle_autoplay(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        if not await self.cog.has_voted(interaction.user, interaction.guild):
            embed = discord.Embed(
                title="Unlock This Feature!",
                description=(
                    "Hey there, music lover! 🎶 This feature is available to our awesome voters. "
                    "Please [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) "
                    "to unlock this perk. Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! <a:tadaMM:1258473486003732642>"
                ),
                color=discord.Color.green()
            )
            embed.set_author(name="Music Monkey", icon_url=self.cog.bot.user.display_avatar.url)
            embed.set_footer(text="Thanks for your support!")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # If autoplay is disabled, enable it and change button label
        if self.player.autoplay == wavelink.AutoPlayMode.disabled:
            self.player.autoplay = wavelink.AutoPlayMode.enabled
            button.label = "DISABLE AUTOPLAY"
            response = "Autoplay enabled."
        # Otherwise disable autoplay and change button label
        else:
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            button.label = "AUTOPLAY"
            response = "Autoplay disabled."
        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)
        await interaction.followup.send(response, ephemeral=True)


# Adds the cog to the bot
async def setup(bot):
    await bot.add_cog(MusicCog(bot))
