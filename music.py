import discord
from discord import app_commands, Interaction, Embed, ButtonStyle, ui
from discord.ext import commands, tasks
import wavelink
import logging
import database
from datetime import datetime, timedelta


class SelectRoleView(discord.ui.View):
    def __init__(self, options, user_id):
        super().__init__()
        self.user_id = user_id
        self.add_item(RoleSelect(options))


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

    @ui.button(label="FIRST", style=ButtonStyle.grey, custom_id="first_queue_page")
    async def first_page(self, interaction: Interaction, button: ui.Button):
        self.current_page = 1
        await self.cog.display_queue(interaction, self.current_page, edit=True)
        await interaction.response.send_message()

    @ui.button(label="BACK", style=ButtonStyle.primary, custom_id="previous_queue_page")
    async def previous_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.cog.display_queue(interaction, self.current_page, edit=True)
            await interaction.response.send_message()
        button.disabled = self.current_page <= 1

    @ui.button(label="NEXT", style=ButtonStyle.primary, custom_id="next_queue_page")
    async def next_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page < self.total_pages:
            self.current_page += 1
            await self.cog.display_queue(interaction, self.current_page, edit=True)
            await interaction.response.send_message()
        button.disabled = self.current_page >= self.total_pages

    @ui.button(label="LAST", style=ButtonStyle.grey, custom_id="last_queue_page")
    async def last_page(self, interaction: Interaction, button: ui.Button):
        self.current_page = self.total_pages
        await self.cog.display_queue(interaction, self.current_page, edit=True)
        await interaction.response.send_message()


def format_duration(ms):
    # Convert milliseconds to minutes and seconds
    seconds = int((ms / 1000) % 60)
    minutes = int((ms / (1000 * 60)) % 60)
    hours = int((ms / (1000 * 60 * 60)) % 24)

    if hours > 0:
        return f"{hours}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes}:{seconds:02}"


class RoleSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder='Choose a DJ role...', min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        # Ensure the right user is interacting with the select menu
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("You do not have permission to interact with this.", ephemeral=True)
            return

        # Update the DJ role in the database
        role_id = int(self.values[0])
        await database.set_dj_role(interaction.guild_id, role_id)
        role_name = next((option.label for option in self.options if option.value == self.values[0]), 'Unknown Role')
        await interaction.response.send_message(f"The DJ role has been set to **{role_name}**.", ephemeral=True)
        self.view.stop()  # Stop the view to prevent further interactions


class Track(wavelink.Playable):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.requester = None


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.last_vote_reminder_time_per_guild = {}
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    @tasks.loop(seconds=10)
    async def check_voice_channel(self):
        for guild in self.bot.guilds:
            # Retrieve the bot's voice state in the guild
            voice_state = guild.voice_client

            # Check if the bot is connected to a voice channel
            if voice_state and voice_state.channel:
                channel = voice_state.channel
                if len(channel.members) == 1:  # Only the bot is left in the channel
                    print(f"Disconnecting due to inactivity in channel: {channel.name} of guild: {guild.name}")
                    await self.disconnect_and_cleanup(voice_state)

    @check_voice_channel.before_loop
    async def before_check_voice_channel(self):
        await self.bot.wait_until_ready()

    @check_voice_channel.before_loop
    async def before_check_voice_channel(self):
        await self.bot.wait_until_ready()

    async def user_in_voice(self, interaction):
        member = interaction.guild.get_member(interaction.user.id)
        return member.voice and member.voice.channel

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

        # Retrieve the DJ-only mode status and DJ role ID from the database
        dj_only = await database.get_dj_only_commands(interaction.guild_id)
        dj_role_id = await database.get_dj_role(interaction.guild_id)

        # If DJ-only mode is not enabled, allow all interactions
        if not dj_only:
            return True

        # Check if the user has manage_roles permission or the specific DJ role
        has_permissions = interaction.user.guild_permissions.manage_roles
        is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

        if has_permissions or is_dj:
            return True

        await interaction.response.send_message(
            "DJ-only mode is enabled. You need DJ privileges to use this.",
            ephemeral=True
        )
        return False

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f'Node {payload.node.identifier} is ready!')

    @commands.Cog.listener()
    async def on_wavelink_inactive_player(self, player: wavelink.Player):
        # Ensure that the player is still connected before sending the message and disconnecting
        if player and hasattr(player, 'interaction_channel_id'):
            channel = self.bot.get_channel(player.interaction_channel_id)
            if channel:
                await self.send_inactivity_message(channel)
        await self.disconnect_and_cleanup(player)

    async def send_inactivity_message(self, channel: discord.TextChannel):
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

    async def disconnect_and_cleanup(self, player: wavelink.Player):
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

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload):
        player: wavelink.Player = payload.player
        track: wavelink.Playable = payload.track
        player.inactive_timeout = 30

        # Attempt to fetch the requester user object
        requester_id = getattr(track.extras, 'requester_id', None)
        requester = None
        if requester_id:
            try:
                requester = await self.bot.fetch_user(requester_id)
            except discord.NotFound:
                # If the user can't be found, fall back to "AutoPlay"
                requester = None
            except Exception as e:
                logging.error(f"Failed to fetch user {requester_id}: {e}")
                requester = None

        # Formatting the duration using the helper function
        duration = format_duration(track.length)

        embed = discord.Embed(
            title="Now Playing",
            description=f"**{track.title}** by `{track.author}`\nRequested by: {requester.display_name if requester else 'AutoPlay'}\nDuration: {duration}",
            color=discord.Color.dark_red()
        )
        if track.artwork:
            embed.set_image(url=track.artwork)

        # Ensure the interaction channel ID is set
        if hasattr(player, 'interaction_channel_id'):
            channel = self.bot.get_channel(player.interaction_channel_id)
            if channel:
                # Update or create the Now Playing message
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
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)  # Play the next track

            # Retrieve the requester ID
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
                # If no existing message to edit or message was deleted, send a new one
                channel = self.bot.get_channel(player.interaction_channel_id)
                if channel:
                    player.now_playing_message = await channel.send(embed=embed)
        else:
            # Update the embed to reflect that nothing is playing
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

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.id == self.bot.user.id and before.channel is not None and after.channel is None:
            player = member.guild.voice_client
            if player and hasattr(player, 'now_playing_message') and player.now_playing_message:
                try:
                    await player.now_playing_message.delete()
                except discord.NotFound:
                    pass  # Message already deleted
                except discord.HTTPException as e:
                    logging.error(f"Failed to delete now playing message: {e}")
                player.now_playing_message = None  # Clear the reference

    async def display_queue(self, interaction: discord.Interaction, page: int, edit=False):
        player = interaction.guild.voice_client
        if not player or not player.queue or player.queue.is_empty:
            await interaction.response.send_message("The queue is empty.")
            return

        items_per_page = 10
        total_pages = (len(player.queue) + items_per_page - 1) // items_per_page
        start_index = (page - 1) * items_per_page
        end_index = min(start_index + items_per_page, len(player.queue))
        queue_slice = list(player.queue)[start_index:end_index]

        queue_description = "\n".join(
            f"{idx + 1 + start_index}. **{track.title}** by `{track.author}` ({format_duration(track.length)})"
            for idx, track in enumerate(queue_slice)
        )
        embed = discord.Embed(title=f'Queue - Page {page} of {total_pages}', description=queue_description,
                              color=discord.Color.dark_red())
        view = QueuePaginationView(self, interaction, page, total_pages)

        if edit:
            await interaction.message.edit(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name='dj', description='Toggle DJ-only command restrictions')
    @commands.has_permissions(manage_roles=True)
    async def toggle_dj_mode(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id
        current_state = await database.get_dj_only_commands(guild_id) or False
        new_state = not current_state
        await database.set_dj_only_commands(guild_id, new_state)

        await interaction.response.send_message(f'DJ-only mode is now {"enabled" if new_state else "disabled"}.')

    @app_commands.command(name='setdj', description='Set a DJ role')
    async def set_dj_role(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message(
                "You do not have the required permissions to use this command.",
                ephemeral=True
            )
            return

        roles = [role for role in interaction.guild.roles if role.name != "@everyone" and not role.is_bot_managed()]
        options = [
            discord.SelectOption(label=role.name, value=str(role.id), description=f"Set {role.name} as the DJ role")
            for role in roles
        ]
        view = SelectRoleView(options, interaction.user.id)
        await interaction.response.send_message("Please select a DJ role from the menu:", view=view, ephemeral=True)

        # Update the DJ role in the database
        selected_role_id = int(view.children[0].values[0])
        await database.set_dj_role(interaction.guild_id, selected_role_id)

    @app_commands.command(name='play', description='Play or queue a song from a URL or search term')
    @app_commands.describe(query='URL or search term of the song to play')
    async def play(self, interaction: Interaction, query: str):
        await interaction.response.defer(ephemeral=False)

        guild_id = str(interaction.guild_id)
        current_time = datetime.now()

        # Check if the reminder should be sent for this guild
        if (guild_id in self.last_vote_reminder_time_per_guild and
                (current_time - self.last_vote_reminder_time_per_guild[guild_id]) > timedelta(hours=12)):
            await self.send_vote_reminder(interaction)
            self.last_vote_reminder_time_per_guild[guild_id] = current_time
        elif guild_id not in self.last_vote_reminder_time_per_guild:
            await self.send_vote_reminder(interaction)
            self.last_vote_reminder_time_per_guild[guild_id] = current_time

        try:
            results = await wavelink.Playable.search(query)
            if not results:
                await interaction.followup.send('No tracks found with that query.', ephemeral=True)
                return

            channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
            if not channel:
                await interaction.followup.send("You must be in a voice channel to play music.", ephemeral=True)
                return

            node = wavelink.Pool.get_node()
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
                added_tracks_info = f"Added {len(tracks)} tracks from the playlist to the queue."
                for track in tracks:
                    track.extras.requester_id = interaction.user.id
                    player.queue.put(track)
            else:
                track = results[0]
                track.extras.requester_id = interaction.user.id
                player.queue.put(track)
                added_tracks_info = f"Added to queue: {track.title}"

            if not player.playing and not player.paused:
                next_track = player.queue.get()
                await player.play(next_track)
            else:
                await interaction.followup.send(added_tracks_info, ephemeral=False)

            # Increment the play count for the user in the database
            await database.increment_song_play(interaction.guild_id, interaction.user.id)

        except Exception as e:
            logging.error(f"Error processing the play command: {e}")
            await interaction.followup.send('An error occurred while trying to play the track.', ephemeral=True)

    async def send_vote_reminder(self, interaction):
        embed = Embed(
            title="Support Us by Voting!",
            description="🌟 Your votes help keep the bot free and continuously improving. Please take a moment to "
                        "support us!",
            color=0x00ff00
        )
        embed.add_field(name="Vote Here", value="[Vote on Top.gg](https://top.gg/bot/1228071177239531620/vote)")
        embed.set_thumbnail(url=interaction.client.user.avatar.url)
        embed.set_footer(text="Thank you for your support! Your votes make a big difference!")
        await interaction.followup.send(embed=embed, ephemeral=False)

    @app_commands.command(name='skip', description='Skip the current playing song')
    async def skip(self, interaction: Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        player: wavelink.Player = interaction.guild.voice_client
        if player is None:
            await interaction.response.send_message("The queue is empty, as I'm not active right now.", ephemeral=True)
            return

        # Stops the current track and trigger the track end event
        await player.stop()

        # Check if the queue is empty before attempting to get the next track
        if not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)  # Play the next track
            await interaction.response.send_message(f"Now playing: {next_track.title}")
        else:
            await interaction.response.send_message("The queue is currently empty.")

    @app_commands.command(name='pause', description='Pause the music playback')
    async def pause(self, interaction: discord.Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        player = interaction.guild.voice_client
        if player and isinstance(player, wavelink.Player):
            if not player.paused:
                await player.pause(True)
                await interaction.response.send_message("Playback has been paused.")
            else:
                await interaction.response.send_message("Playback is already paused.", ephemeral=True)
        else:
            await interaction.response.send_message("The bot is not connected to a voice channel.", ephemeral=True)

    @app_commands.command(name='resume', description='Resume the music playback if paused')
    async def resume(self, interaction: discord.Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        player = interaction.guild.voice_client
        if player and isinstance(player, wavelink.Player):
            if player.paused:
                await player.pause(False)
                await interaction.response.send_message("Playback has been resumed.")
            else:
                await interaction.response.send_message("Playback is not paused.", ephemeral=True)
        else:
            await interaction.response.send_message("The bot is not connected to a voice channel.", ephemeral=True)

    @app_commands.command(name='stop', description='Stop the music and clear the queue')
    async def stop(self, interaction: discord.Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        player = interaction.guild.voice_client
        await player.stop()
        player.queue.clear()
        await player.disconnect(force=False)
        await interaction.response.send_message('Stopped the music and cleared the queue.', ephemeral=False)

        # Delete the now playing message
        if hasattr(player, 'now_playing_message') and player.now_playing_message:
            try:
                await player.now_playing_message.delete()
            except discord.NotFound:
                pass  # If the message was already deleted, do nothing
            except discord.HTTPException as e:
                logging.error(f"Failed to delete now playing message: {e}")

    @app_commands.command(name='queue', description='Show the current music queue')
    async def show_queue(self, interaction: Interaction):
        await self.display_queue(interaction, 1)

    @app_commands.command(name='clear', description='Clear the current music queue')
    async def clear(self, interaction: Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.response.send_message("The queue is already empty.", ephemeral=True)
        else:
            player.queue.clear()  # Clear the queue
            await interaction.response.send_message("The music queue has been cleared.", ephemeral=True)

    @app_commands.command(name='cleargone',
                          description='Remove tracks from the queue requested by users not in the voice channel')
    async def cleargone(self, interaction: discord.Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        voice_channel_members = {member.id for member in interaction.user.voice.channel.members}
        initial_count = len(player.queue)
        tracks_to_remove = [i for i, track in enumerate(player.queue) if
                            not hasattr(track.extras, 'requester_id') or getattr(track.extras, 'requester_id',
                                                                                 None) not in voice_channel_members]

        for index in reversed(tracks_to_remove):
            player.queue.delete(index)

        removed_count = initial_count - len(player.queue)
        await interaction.response.send_message(
            f"Removed {removed_count} tracks requested by users not currently in the channel.", ephemeral=False)

    @app_commands.command(name='remove', description='Remove a specific song from the queue by its position')
    @app_commands.describe(position='Position in the queue of the song to remove')
    async def remove(self, interaction: discord.Interaction, position: int):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or player.queue.is_empty:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return

        if position < 1 or position > len(player.queue):
            await interaction.response.send_message("Invalid position in the queue.", ephemeral=True)
            return

        try:
            player.queue.delete(position - 1)  # Adjust spot for queue
            await interaction.response.send_message(f"Removed track at position {position} from the queue.",
                                                    ephemeral=False)
        except IndexError:
            await interaction.response.send_message("No track found at the specified position.", ephemeral=True)

    @app_commands.command(name='shuffle', description='Shuffles the current music queue')
    async def shuffle(self, interaction: Interaction):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player or not player.queue or not hasattr(player,
                                                         'now_playing_message') or not player.now_playing_message:
            await interaction.response.send_message(
                "Shuffle can only be used when a song is playing and visible in the Now Playing message.",
                ephemeral=True)
            return

        # Shuffle the queue
        player.queue.shuffle()

        # Send confirmation message
        await interaction.response.send_message("The queue has been shuffled.", ephemeral=True)

    @app_commands.command(name='autoplay', description='Toggle AutoPlay mode for automatic music recommendations')
    @app_commands.choices(mode=[
        app_commands.Choice(name='enabled', value='enabled'),
        app_commands.Choice(name='disabled', value='disabled')
    ])
    async def autoplay(self, interaction: discord.Interaction, mode: str):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        player = interaction.guild.voice_client

        if not player:
            await interaction.response.send_message("Not connected to a voice channel.", ephemeral=True)
            return

        if mode == 'enabled':
            player.autoplay = wavelink.AutoPlayMode.enabled
            await interaction.response.send_message("AutoPlay has been enabled.", ephemeral=True)
        elif mode == 'disabled':
            player.autoplay = wavelink.AutoPlayMode.disabled
            await interaction.response.send_message("AutoPlay has been disabled.", ephemeral=True)

    @app_commands.command(name='loop', description='Toggle loop mode for the current track or queue')
    async def loop(self, interaction: discord.Interaction):
        player: wavelink.Player = interaction.guild.voice_client

        if not player or not wavelink.Player.playing:
            await interaction.response.send_message("No active music player or nothing is currently playing.",
                                                    ephemeral=True)
            return

        # Toggle between normal and loop mode
        current_mode = player.queue.mode
        if current_mode == wavelink.QueueMode.loop:
            new_mode = wavelink.QueueMode.normal
        else:
            new_mode = wavelink.QueueMode.loop

        # Set the new mode
        player.queue.mode = new_mode

        # Send a response back to the user
        mode_description = "normal (no looping)" if new_mode == wavelink.QueueMode.normal else "looping current track"
        await interaction.response.send_message(f"Queue mode set to {mode_description}.", ephemeral=False)

    @app_commands.command(name='jump', description='Jump to a specific time in the current track')
    @app_commands.describe(time='Time to jump to in the format mm:ss')
    async def jump(self, interaction: discord.Interaction, time: str):
        if not await self.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        # Validate and parse the time format
        try:
            minutes, seconds = map(int, time.split(':'))
            position = (minutes * 60 + seconds) * 1000  # Convert time to milliseconds
        except ValueError:
            await interaction.response.send_message("Invalid time format. Please use mm:ss format.", ephemeral=True)
            return

        # Get the current player
        player = interaction.guild.voice_client
        if player and wavelink.Player.playing:
            # Seek to the desired position
            await player.seek(position)
            await interaction.response.send_message(f"Jumped to {minutes} minutes and {seconds} seconds.",
                                                    ephemeral=True)
        else:
            await interaction.response.send_message("There is no active player or track playing.", ephemeral=True)


class MusicButtons(ui.View):
    def __init__(self, player, cog):
        super().__init__(timeout=None)
        self.player = player
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

        # Retrieve the DJ-only mode status and DJ role ID from the database
        dj_only = await database.get_dj_only_commands(interaction.guild_id)
        dj_role_id = await database.get_dj_role(interaction.guild_id)

        # If DJ-only mode is not enabled, allow all interactions
        if not dj_only:
            return True

        # Check if the user has manage_roles permission or the specific DJ role
        has_permissions = interaction.user.guild_permissions.manage_roles
        is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

        # If the user has the necessary permissions or the DJ role, allow the interaction
        if has_permissions or is_dj:
            return True

        # If the user does not have the necessary permissions, send a message and deny the interaction
        await interaction.response.send_message(
            "DJ-only mode is enabled. You need DJ privileges to use this.",
            ephemeral=True
        )
        return False

    @ui.button(label='QUEUE', style=ButtonStyle.green, custom_id='queue_button')
    async def show_queue(self, interaction: Interaction, button: ui.Button):
        if self.player and not self.player.queue.is_empty:
            # Start from the first page
            await self.cog.display_queue(interaction, 1, edit=False)
        else:
            # Respond if the queue is empty
            await interaction.response.send_message("The queue is empty.", ephemeral=True)

    @ui.button(label='VOL +', style=ButtonStyle.green, custom_id='vol_up_button')
    async def volume_up(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        new_volume = min(self.player.volume + 10, 100)  # Volume should not exceed 100
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f'Volume increased to {new_volume}%', ephemeral=True)

    @ui.button(label='PAUSE', style=ButtonStyle.blurple, custom_id='pause_button')
    async def pause(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
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
        await interaction.response.edit_message(view=self)

    @ui.button(label='VOL -', style=ButtonStyle.green, custom_id='vol_down_button')
    async def volume_down(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        new_volume = max(self.player.volume - 10, 0)  # Volume should not go below 0
        await self.player.set_volume(new_volume)
        await interaction.response.send_message(f'Volume decreased to {new_volume}%', ephemeral=True)

    @ui.button(label='SKIP', style=ButtonStyle.green, custom_id='skip_button')
    async def skip(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        await self.player.skip()
        await interaction.response.send_message('Skipped the current song', ephemeral=True)

    @ui.button(label='LOOP', style=ButtonStyle.green, custom_id='loop_button')
    async def toggle_loop(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        current_mode = self.player.queue.mode
        if current_mode == wavelink.QueueMode.loop:
            self.player.queue.mode = wavelink.QueueMode.normal
            button.label = "LOOP"
            response = "Looping disabled."
        else:
            self.player.queue.mode = wavelink.QueueMode.loop
            button.label = "NORMAL"
            response = "Looping enabled."
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(response, ephemeral=True)

    @ui.button(label='REWIND', style=ButtonStyle.green, custom_id='rewind_button')
    async def rewind(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        # Calculate the new position, ensuring it does not fall below zero
        new_position = max(0, self.player.position - 5000)
        await self.player.seek(new_position)
        await interaction.response.send_message(f"Rewound 5 seconds.",
                                                ephemeral=True)

    @ui.button(label='STOP', style=ButtonStyle.red, custom_id='stop_button')
    async def stop_music(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        # Stops the current track, clears the queue, and disconnects the player from the channel
        await self.player.stop()
        await self.player.disconnect()
        await interaction.response.send_message('Stopped the music and cleared the queue.', ephemeral=True)

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

    @ui.button(label='FORWARD', style=ButtonStyle.green, custom_id='forward_button')
    async def forward(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        # Calculate the new position, ensuring it does not exceed the track's duration
        new_position = min(self.player.position + 5000, self.player.current.length)
        await self.player.seek(new_position)
        await interaction.response.send_message(f"Forwarded 5 seconds.",
                                                ephemeral=True)

    @ui.button(label='AUTOPLAY', style=ButtonStyle.green, custom_id='autoplay_button')
    async def toggle_autoplay(self, interaction: Interaction, button: ui.Button):
        if not await self.cog.user_in_voice(interaction):
            await interaction.response.send_message("You must be in a voice channel to use this command.",
                                                    ephemeral=True)
            return
        if self.player.autoplay == wavelink.AutoPlayMode.disabled:
            self.player.autoplay = wavelink.AutoPlayMode.enabled
            button.label = "DISABLE AUTOPLAY"
            response = "Autoplay enabled."
        else:
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            button.label = "ENABLE AUTOPLAY"
            response = "Autoplay disabled."
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(response, ephemeral=True)


async def setup(bot):
    await bot.add_cog(MusicCog(bot))
