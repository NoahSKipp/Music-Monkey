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
