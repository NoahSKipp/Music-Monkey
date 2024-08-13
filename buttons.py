# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 14.08..2024                    #
# ========================================= #

import discord
from discord import ui, ButtonStyle
import wavelink
import logging
import aiohttp
import config
from discord import Embed, Interaction
import database as db
import json


#   Sets up the class for the player control buttons
class MusicButtons(ui.View):
    def __init__(self, player, cog):
        super().__init__(timeout=None)
        self.player = player
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

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

            await interaction.response.send_message(
                "DJ-only mode is enabled. You need DJ privileges to use this command.",
                ephemeral=True
            )
            return False

        return True

    async def has_voted(self, user: discord.User, guild: discord.Guild) -> bool:
        print(f"Checking vote status for user {user.id} in guild {guild.id}")

        if guild.id == config.EXEMPT_GUILD_ID:
            return True

        exempt_guild = self.cog.bot.get_guild(config.EXEMPT_GUILD_ID)
        if not exempt_guild:
            try:
                exempt_guild = await self.cog.bot.fetch_guild(config.EXEMPT_GUILD_ID)
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
                if config.EXEMPT_ROLE_ID in roles:
                    return True
        except discord.NotFound:
            return False
        except discord.Forbidden:
            return False
        except Exception as e:
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
                    voted = data.get("voted") == 1
                    return voted
                else:
                    return False

    @ui.button(label='QUEUE', style=ButtonStyle.green, custom_id='queue_button')
    async def show_queue(self, interaction: Interaction, button: ui.Button):
        if self.player and not self.player.queue.is_empty:
            await self.cog.display_queue(interaction, 1, edit=False)
        else:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)

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

        new_volume = max(self.player.volume - 10, 0)
        await self.player.set_volume(new_volume)
        await interaction.followup.send(f'Volume decreased to {new_volume}%', ephemeral=True)

    @ui.button(label='PAUSE', style=ButtonStyle.blurple, custom_id='pause_button')
    async def pause(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        if self.player.paused:
            await self.player.pause(False)
            button.label = 'PAUSE'
        else:
            await self.player.pause(True)
            button.label = 'PLAY'

        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)

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

        new_volume = min(self.player.volume + 10, 100)
        await self.player.set_volume(new_volume)
        await interaction.followup.send(f'Volume increased to {new_volume}%', ephemeral=True)

    @ui.button(label='SKIP', style=ButtonStyle.green, custom_id='skip_button')
    async def skip(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        await self.player.skip()
        await interaction.followup.send('Skipped the current song', ephemeral=True)

    @ui.button(label='LOOP', style=ButtonStyle.green, custom_id='loop_button')
    async def toggle_loop(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        player = interaction.guild.voice_client
        current_mode = player.queue.mode

        if current_mode == wavelink.QueueMode.normal:
            player.queue.mode = wavelink.QueueMode.loop
            button.label = 'LOOP QUEUE'
            response = "Looping current track enabled."
        elif current_mode == wavelink.QueueMode.loop:
            player.queue.mode = wavelink.QueueMode.loop_all
            button.label = 'LOOP OFF'
            response = "Looping all tracks enabled."
        elif current_mode == wavelink.QueueMode.loop_all:
            player.queue.mode = wavelink.QueueMode.normal
            button.label = 'LOOP'
            response = "Looping disabled."

        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)
        await interaction.followup.send(response, ephemeral=True)

    @ui.button(label='REWIND', style=ButtonStyle.green, custom_id='rewind_button')
    async def rewind(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        new_position = max(0, self.player.position - 15000)
        await self.player.seek(new_position)
        await interaction.followup.send(f"Rewound 15 seconds.", ephemeral=True)

    @ui.button(label='STOP', style=ButtonStyle.red, custom_id='stop_button')
    async def stop_music(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return

        self.player.was_forcefully_stopped = True

        await self.player.stop()
        await self.player.disconnect()
        await interaction.followup.send('Stopped the music and cleared the queue.', ephemeral=True)

        self.stop()

        if hasattr(self.player, 'now_playing_message') and self.player.now_playing_message:
            try:
                await self.player.now_playing_message.delete()
            except discord.NotFound:
                pass
            except discord.HTTPException as e:
                logging.error(f"Failed to delete now playing message: {e}")

        self.player.now_playing_message = None

    @ui.button(label='FORWARD', style=ButtonStyle.green, custom_id='forward_button')
    async def forward(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not await self.cog.user_in_voice(interaction):
            await interaction.followup.send("You must be in the same voice channel as me to use this command.",
                                            ephemeral=True)
            return
        new_position = min(self.player.position + 15000, self.player.current.length)
        await self.player.seek(new_position)
        await interaction.followup.send(f"Forwarded 15 seconds.", ephemeral=True)

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

        if self.player.autoplay == wavelink.AutoPlayMode.disabled:
            self.player.autoplay = wavelink.AutoPlayMode.enabled
            button.label = "DISABLE AUTOPLAY"
            response = "Autoplay enabled."
        else:
            self.player.autoplay = wavelink.AutoPlayMode.disabled
            button.label = "AUTOPLAY"
            response = "Autoplay disabled."
        await interaction.followup.edit_message(view=self, message_id=interaction.message.id)
        await interaction.followup.send(response, ephemeral=True)

    @ui.button(label='LIKE', style=ButtonStyle.red, custom_id='heart_button')
    async def add_to_playlist(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

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

        track = self.player.current
        if not track:
            await interaction.followup.send("No track is currently playing.", ephemeral=True)
            return

        playlist_cog = self.cog.bot.get_cog("Playlist")
        if playlist_cog:
            await playlist_cog.add_song_to_playlist_via_heart_button(interaction, track)
        else:
            await interaction.followup.send("Playlist functionality is currently unavailable.", ephemeral=True)


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

    # Define buttons for pagination
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


class FilterSelectView(discord.ui.View):
    def __init__(self, options, user_id, player):
        super().__init__()
        self.user_id = user_id
        self.player = player
        self.add_item(FilterSelect(options, user_id, player))


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

class PlaylistEditSelectView(discord.ui.View):
    def __init__(self, playlists, interaction):
        super().__init__(timeout=60)
        self.playlists = playlists
        self.interaction = interaction

        options = [
            discord.SelectOption(label=playlist['name'], value=str(playlist['playlist_id']))
            for playlist in playlists
        ]

        self.select = discord.ui.Select(placeholder="Choose a playlist to edit", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction):
        selected_playlist_id = int(self.select.values[0])
        selected_playlist = next(
            (playlist for playlist in self.playlists if playlist['playlist_id'] == selected_playlist_id), None)

        if selected_playlist:
            embed, view = await create_edit_interface(interaction, selected_playlist)
            await interaction.response.edit_message(embed=embed, view=view)
        self.stop()

# PlaylistPlaySelectView for selecting a playlist to play
class PlaylistPlaySelectView(discord.ui.View):
    def __init__(self, playlists, interaction):
        super().__init__(timeout=60)
        self.playlists = playlists
        self.interaction = interaction

        self.interaction.client.loop.create_task(self.update_options())

    async def update_options(self):
        options = []
        seen = set()
        for index, playlist in enumerate(self.playlists):
            if playlist['privacy'] == 1 or self.interaction.user.id == playlist['user_id']:
                creator_name = self.interaction.client.get_user(playlist['user_id']).name
                label = f"{playlist['name']} by {creator_name}"
                if label not in seen:
                    options.append(discord.SelectOption(label=label, value=str(index)))
                    seen.add(label)
            else:
                collaborators = await db.get_playlist_collaborators(playlist['playlist_id'])
                if self.interaction.user.id in collaborators:
                    creator_name = self.interaction.client.get_user(playlist['user_id']).name
                    label = f"{playlist['name']} by {creator_name}"
                    if label not in seen:
                        options.append(discord.SelectOption(label=label, value=str(index)))
                        seen.add(label)

        if options:
            select = discord.ui.Select(placeholder="Choose a playlist", options=options)
            select.callback = self.select_callback
            self.add_item(select)

        await self.interaction.followup.send(
            "Multiple playlists found. Please select one:",
            view=self if options else None,
            ephemeral=True if options else False
        )

    async def select_callback(self, interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration

        selected_index = int(interaction.data['values'][0])
        selected_playlist = self.playlists[selected_index]
        if selected_playlist:
            contents = await db.get_playlist_contents(selected_playlist['playlist_id'])
            if not contents:
                await interaction.followup.send_message(f"Oops! The playlist '{selected_playlist['name']}' is empty. 📂",
                                                        ephemeral=True)
                return
            player = interaction.guild.voice_client
            if not player:
                channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
                if not channel:
                    await interaction.followup.send_message("Please join a voice channel to play music. 🎶",
                                                            ephemeral=True)
                    return
                player = await channel.connect(cls=wavelink.Player)
                player.guild_id = interaction.guild_id
                player.interaction_channel_id = interaction.channel_id

            playlist_cog = interaction.client.get_cog("Playlist")
            if playlist_cog:
                await playlist_cog.play_songs(interaction, contents, player)
                await interaction.followup.send(
                    f"Playing all songs from playlist '{selected_playlist['name']}'! 🎶",
                    ephemeral=False)
            else:
                await interaction.followup.send(
                    "Whoops! I can't seem to find my playlist controls. Please try again later. 🎧",
                    ephemeral=True)
        self.stop()

# ConfirmDeleteView for confirming playlist deletion
class ConfirmDeleteView(discord.ui.View):
    def __init__(self, user_id, playlist_name, playlist_id):
        super().__init__()
        self.user_id = user_id
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        result = await db.delete_playlist(self.user_id, self.playlist_name, self.playlist_id)
        message = await interaction.original_response()
        await message.edit(content=result, view=None)

    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        message = await interaction.original_response()
        await message.edit(content="Playlist deletion cancelled. 🎶", view=None)

# PlaylistPaginator for navigating through playlist contents
class PlaylistPaginator(discord.ui.View):
    def __init__(self, embeds, current_page=0, total_pages=None, timeout=180):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.current_page = current_page
        self.total_pages = total_pages if total_pages else len(embeds)

        self.first_button = discord.ui.Button(label="First", style=discord.ButtonStyle.grey, custom_id="first_page")
        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary, custom_id="prev_page")
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_page")
        self.last_button = discord.ui.Button(label="Last", style=discord.ButtonStyle.grey, custom_id="last_page")

        self.first_button.callback = self.first_page
        self.prev_button.callback = self.previous
        self.next_button.callback = self.next
        self.last_button.callback = self.last_page

        self.add_item(self.first_button)
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        self.add_item(self.last_button)

        self.update_buttons()

    async def update(self, interaction: discord.Interaction, message=None):
        self.update_buttons()
        if self.embeds:
            embed = self.embeds[self.current_page]
            embed.set_footer(
                text=f"Page {self.current_page + 1} of {self.total_pages}")  # Update the footer with the page number
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                if message:
                    await interaction.followup.send(message, ephemeral=True)
            except discord.errors.InteractionResponded:
                pass
            except discord.errors.NotFound:
                await interaction.channel.send(embed=embed)
                if message:
                    await interaction.channel.send(message)
        else:
            await interaction.response.edit_message(content="No more pages available. 🎶", view=self)
            if message:
                await interaction.followup.send(message, ephemeral=True)

    def update_buttons(self):
        self.first_button.disabled = self.current_page == 0
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1
        self.last_button.disabled = self.current_page == self.total_pages - 1

    async def first_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = 0
        await self.update(interaction)

    async def previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page > 0:
            self.current_page -= 1
            await self.update(interaction)

    async def next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update(interaction)

    async def last_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = self.total_pages - 1
        await self.update(interaction)

# Paginator for navigating through embeds
class Paginator(discord.ui.View):
    def __init__(self, embeds, invites, bot, timeout=180):
        super().__init__(timeout=timeout)
        self.embeds = embeds
        self.invites = invites
        self.bot = bot
        self.current_page = 0

        self.prev_button = discord.ui.Button(label="Previous", style=discord.ButtonStyle.primary,
                                             custom_id="prev_button")
        self.accept_button = discord.ui.Button(label="Accept", style=discord.ButtonStyle.success,
                                               custom_id="accept_button")
        self.decline_button = discord.ui.Button(label="Decline", style=discord.ButtonStyle.danger,
                                                custom_id="decline_button")
        self.next_button = discord.ui.Button(label="Next", style=discord.ButtonStyle.primary, custom_id="next_button")

        self.prev_button.callback = self.previous
        self.accept_button.callback = self.accept
        self.decline_button.callback = self.decline
        self.next_button.callback = self.next

        self.add_item(self.prev_button)
        self.add_item(self.accept_button)
        self.add_item(self.decline_button)
        self.add_item(self.next_button)

        self.update_buttons()

    async def update(self, interaction: discord.Interaction, message=None):
        self.update_buttons()
        if self.embeds:
            embed = self.embeds[self.current_page]
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                if message:
                    await interaction.followup.send(message, ephemeral=True)
            except discord.errors.InteractionResponded:
                pass
            except discord.errors.NotFound:
                await interaction.channel.send(embed=embed)
                if message:
                    await interaction.channel.send(message)
        else:
            await interaction.response.edit_message(content="No more invites. 🎶", view=self)
            if message:
                await interaction.followup.send(message, ephemeral=True)

    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.embeds) - 1

    async def previous(self, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update(interaction)

    async def next(self, interaction: discord.Interaction):
        self.current_page += 1
        await self.update(interaction)

    async def accept(self, interaction: discord.Interaction):
        invite = self.invites[self.current_page]
        await db.accept_playlist_invite(invite['invite_id'])
        message = f"Invite to playlist '{invite['name']}' accepted! 🎉"
        await self.remove_current_invite()
        await self.update(interaction, message)

    async def decline(self, interaction: discord.Interaction):
        invite = self.invites[self.current_page]
        await db.decline_playlist_invite(invite['invite_id'])
        message = f"Invite to playlist '{invite['name']}' declined. 🎶"
        await self.remove_current_invite()
        await self.update(interaction, message)

    async def remove_current_invite(self):
        if self.invites:
            self.invites.pop(self.current_page)
            self.embeds.pop(self.current_page)
        if self.current_page >= len(self.embeds):
            self.current_page = len(self.embeds) - 1
        if not self.embeds:
            self.clear_items()
            self.add_item(
                discord.ui.Button(label="No more invites", style=discord.ButtonStyle.secondary, disabled=True))
        self.update_buttons()

# PlaylistSelection for selecting a playlist from a list
class PlaylistSelection(discord.ui.View):
    def __init__(self, playlists, bot):
        super().__init__(timeout=180)
        self.playlists = playlists
        self.bot = bot
        self.selected_playlist = playlists[0] if playlists else None

        self.select = discord.ui.Select(placeholder="Choose a playlist", custom_id="select_playlist", options=[])
        self.view_button = discord.ui.Button(label="View", style=discord.ButtonStyle.primary, custom_id="view_button")

        self.select.callback = self.select_playlist
        self.view_button.callback = self.view_playlist

        self.add_item(self.select)
        self.add_item(self.view_button)

    async def update_options(self, selected_playlist_id=None):
        options = []
        seen = set()
        for index, playlist in enumerate(self.playlists):
            creator = self.bot.get_user(playlist['user_id'])
            if not creator:
                creator = await self.bot.fetch_user(playlist['user_id'])
            label = f"{playlist['name']} (by {creator.name})"
            if label not in seen:
                options.append(discord.SelectOption(label=label, value=str(playlist['playlist_id']),
                                                    default=(playlist['playlist_id'] == selected_playlist_id)))
                seen.add(label)
        self.select.options = options

    async def update_view(self, interaction: discord.Interaction, selected_playlist_id=None):
        await self.update_options(selected_playlist_id)
        embed = await self.create_embed()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(embed=embed, view=self)

    async def select_playlist(self, interaction: discord.Interaction):
        await interaction.response.defer()
        selected_playlist_id = int(self.select.values[0])
        self.selected_playlist = next(
            (playlist for playlist in self.playlists if playlist['playlist_id'] == selected_playlist_id), None)
        await self.update_view(interaction, selected_playlist_id)

    async def view_playlist(self, interaction: discord.Interaction):
        await interaction.response.defer()
        user_id = interaction.user.id
        if self.selected_playlist:
            if self.selected_playlist['privacy'] == 1 or user_id == self.selected_playlist[
                'user_id'] or await db.is_collaborator(user_id, self.selected_playlist['playlist_id']):
                contents = await db.get_playlist_contents(self.selected_playlist['playlist_id'])
                embed = discord.Embed(title=f"Playlist: {self.selected_playlist['name']}",
                                      color=discord.Color.dark_red())
                for song in contents:
                    embed.add_field(name=song['song_name'], value=f"Artist: {song['artist']}", inline=False)
                await interaction.followup.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send_message("Oops! You do not have permission to view this playlist. 🎶",
                                                        ephemeral=True)
        else:
            await interaction.followup.send_message("Please select a playlist first. 🎶", ephemeral=True)

    async def create_embed(self):
        if not self.selected_playlist:
            return discord.Embed(title="No Playlists", description="No playlists available to display.",
                                 color=discord.Color.dark_red())

        creator = self.bot.get_user(self.selected_playlist['user_id'])
        if not creator:
            creator = await self.bot.fetch_user(self.selected_playlist['user_id'])
        embed = discord.Embed(title=self.selected_playlist['name'], description=f"Creator: {creator.name}",
                              color=discord.Color.dark_red())
        embed.add_field(name="Privacy", value="Public" if self.selected_playlist['privacy'] == 1 else "Private")
        if self.selected_playlist['privacy'] == 1:  # Public playlist
            contents = await db.get_playlist_contents(self.selected_playlist['playlist_id'])
            embed.add_field(name="Song Count", value=str(len(contents)))

        return embed

# PlaylistSelectView for selecting a playlist to add a song to
class PlaylistSelectView(discord.ui.View):
    def __init__(self, playlists, track):
        super().__init__(timeout=60)
        self.track = track

        options = [discord.SelectOption(label=playlist['name'], value=playlist['name']) for playlist in playlists]
        self.select = discord.ui.Select(placeholder="Choose a playlist", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        selected_playlist = self.select.values[0]
        await db.add_song_to_playlist(interaction.user.id, selected_playlist, self.track.identifier, self.track.title, self.track.author, self.track.raw_data)
        await interaction.response.send_message(f"Added to your playlist '{selected_playlist}'! 🎶", ephemeral=True)
        self.stop()

# Create playlist selection embeds and view
async def create_playlist_selection_embeds(playlists, bot):
    view = PlaylistSelection(playlists, bot)
    await view.update_options(selected_playlist_id=playlists[0]['playlist_id'])

    embeds = []
    for playlist in playlists:
        creator = bot.get_user(playlist['user_id'])
        if not creator:
            creator = await bot.fetch_user(playlist['user_id'])
        embed = discord.Embed(title=playlist['name'], description=f"Creator: {creator.name}",
                              color=discord.Color.dark_red())
        embed.add_field(name="Privacy", value="Public" if playlist['privacy'] == 1 else "Private")
        if playlist['privacy'] == 1:  # Public playlist
            contents = await db.get_playlist_contents(playlist['playlist_id'])
            embed.add_field(name="Song Count", value=str(len(contents)))
        embeds.append(embed)

    return embeds, view

# Create invite view embeds and view
async def create_invite_view_embeds(invites, bot):
    embeds = []
    invite_ids = set()

    for invite in invites:
        if invite['invite_id'] in invite_ids:
            continue

        invite_ids.add(invite['invite_id'])
        embed = discord.Embed(title=invite['name'], description=f"Invited by: <@{invite['user_id']}>",
                              color=discord.Color.dark_red())
        embed.set_footer(text=f"Invite ID: {invite['invite_id']}")
        embeds.append(embed)

    view = Paginator(embeds, invites, bot)
    return embeds, view

# Create edit interface for a playlist
async def create_edit_interface(interaction: discord.Interaction, playlist):
    embed = discord.Embed(title=f"Edit Playlist: {playlist['name']}", color=discord.Color.dark_red())
    embed.add_field(name="Current Privacy", value="Public" if playlist['privacy'] == 1 else "Private")

    view = discord.ui.View()

    privacy_options = [
        discord.SelectOption(label='Public', value='1'),
        discord.SelectOption(label='Private', value='0')
    ]

    async def privacy_callback(interaction: discord.Interaction):
        selected_privacy = int(interaction.data['values'][0])
        await db.update_playlist_privacy(playlist['playlist_id'], selected_privacy)
        await interaction.response.send_message(
            f"Playlist privacy updated to {'Public' if selected_privacy == 1 else 'Private'} 🎶", ephemeral=True)

    privacy_select = discord.ui.Select(placeholder='Change Privacy', options=privacy_options,
                                       custom_id="privacy_select")
    privacy_select.callback = privacy_callback
    view.add_item(privacy_select)

    async def delete_collaborator_callback(interaction: discord.Interaction):
        collaborators = await db.get_playlist_collaborators(playlist['playlist_id'])
        if not collaborators:
            await interaction.followup.send("No collaborators to delete. 🎶", ephemeral=True)
            return
        embed, view = await create_collaborator_delete_interface(playlist['playlist_id'], collaborators,
                                                                 interaction.client)
        await interaction.response.edit_message(embed=embed, view=view)

    delete_collaborator_button = discord.ui.Button(label="Delete Collaborator", style=discord.ButtonStyle.danger,
                                                   custom_id="delete_collaborator_button")
    delete_collaborator_button.callback = delete_collaborator_callback
    view.add_item(delete_collaborator_button)

    async def edit_name_callback(interaction: discord.Interaction):
        modal = EditPlaylistNameModal(playlist['playlist_id'], playlist['name'])
        await interaction.response.send_modal(modal)

    edit_name_button = discord.ui.Button(label="Edit Name", style=discord.ButtonStyle.secondary,
                                         custom_id="edit_name_button")
    edit_name_button.callback = edit_name_callback
    view.add_item(edit_name_button)

    return embed, view

# Create collaborator delete interface
async def create_collaborator_delete_interface(playlist_id, collaborators, client):
    embed = discord.Embed(title="Delete Collaborator", description="Select a collaborator to delete",
                          color=discord.Color.dark_red())

    options = []
    for collaborator_id in collaborators:
        try:
            user_id = int(collaborator_id)
            user = await client.fetch_user(user_id)
            options.append(discord.SelectOption(label=user.name, value=str(user_id)))
        except ValueError:
            continue

    if not options:
        embed.description = "No collaborators to delete."
        view = discord.ui.View()
        return embed, view

    select = discord.ui.Select(placeholder="Select a collaborator", options=options,
                               custom_id="delete_collaborator_select")

    async def select_callback(interaction: discord.Interaction):
        selected_user_id = int(select.values[0])
        await db.remove_collaborator_from_playlist(playlist_id, selected_user_id)
        await interaction.followup.send(f"Collaborator {selected_user_id} has been removed. 🎶", ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    return embed, view

# Modal for editing playlist name
class EditPlaylistNameModal(discord.ui.Modal, title="Edit Playlist Name"):
    def __init__(self, playlist_id, current_name):
        super().__init__()
        self.playlist_id = playlist_id
        self.current_name = current_name
        self.add_item(discord.ui.TextInput(label="New Playlist Name", placeholder="Enter new playlist name",
                                           default=current_name))

    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.children[0].value
        await db.edit_playlist_name(self.playlist_id, new_name)
        await interaction.response.send_message(f"Playlist name updated to '{new_name}'. 🎶", ephemeral=True)