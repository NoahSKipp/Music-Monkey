# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 13.07.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import database as db
import wavelink
import aiohttp
import config
import logging
import json
from buttons import (PlaylistEditSelectView, PlaylistPlaySelectView, ConfirmDeleteView,
                     PlaylistPaginator, Paginator, PlaylistSelection,
                     create_playlist_selection_embeds, create_invite_view_embeds,
                     create_edit_interface)

# This function provides autocomplete suggestions for playlist names based on the current input
async def playlist_autocomplete(interaction: discord.Interaction, current: str):
    user_id = interaction.user.id
    playlists = await db.get_user_playlists(user_id)
    return [
        app_commands.Choice(name=playlist['name'], value=playlist['name'])
        for playlist in playlists if current.lower() in playlist['name'].lower()
    ]

# Playlist management cog with various commands for creating, editing, and interacting with playlists
class Playlist(commands.GroupCog, group_name="playlist"):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')

        # Fetch DJ-only mode status, DJ role ID, and restricted commands from the database
        dj_only = await db.get_dj_only_enabled(interaction.guild_id)
        dj_role_id = await db.get_dj_role(interaction.guild_id)
        restricted_commands = await db.get_restricted_commands(interaction.guild_id)

        # If DJ-only mode is not enabled, allow the interaction
        if not dj_only:
            return True

        # Skip restriction checks if restricted_commands is None
        if restricted_commands is None:
            return True

        # Check if the command is restricted and validate user permissions
        if interaction.command.name in restricted_commands:
            has_permissions = interaction.user.guild_permissions.manage_roles
            is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

            if has_permissions or is_dj:
                return True

            # Inform the user they lack the necessary privileges
            await interaction.response.send_message(
                "DJ-only mode is enabled. You need DJ privileges to use this command.",
                ephemeral=True
            )
            return False

        return True

    async def add_song_to_playlist_via_heart_button(self, interaction: discord.Interaction, track: wavelink.Playable):
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        # Fetch user's playlists
        playlists = await db.get_user_playlists(user_id)

        if not playlists:
            # No playlists found, create a new one called "{User}'s Favorites"
            playlist_name = f"{interaction.user.name}'s Favorites"
            await db.create_playlist(user_id, guild_id, playlist_name, privacy=0)
            await db.add_song_to_playlist(user_id, playlist_name, track.identifier, track.title, track.author, track.raw_data)
            await interaction.followup.send(f"Added to your new playlist '{playlist_name}'! 🎶", ephemeral=True)
        elif len(playlists) == 1:
            # Only one playlist found, add to that playlist
            playlist_name = playlists[0]['name']
            await db.add_song_to_playlist(user_id, playlist_name, track.identifier, track.title, track.author, track.raw_data)
            await interaction.followup.send(f"Added to your playlist '{playlist_name}'! 🎶", ephemeral=True)
        else:
            # Multiple playlists found, show a dropdown menu to select one
            view = PlaylistSelectView(playlists, track)
            await interaction.followup.send("Select a playlist to add the song to:", view=view, ephemeral=True)


    # Modified play_song function to handle playlist playback
    async def play_songs(self, interaction, songs, player):
        try:
            tracks = []
            for song in songs:
                # Deserialize raw_data JSON string back to dictionary
                raw_data = json.loads(song['raw_data'])
                track = wavelink.Playable(data=raw_data)  # Use raw_data to reconstruct the Playable
                tracks.append(track)

            for track in tracks:
                track.extras = {"requester_id": interaction.user.id}
                player.queue.put(track)

            embed = discord.Embed(
                title="**Added to Queue**",
                description=f"{len(tracks)} tracks from the playlist",
                color=discord.Color.dark_red()
            )
            embed.set_footer(text=f"Queue length: {len(player.queue)}")
            await interaction.followup.send(embed=embed, ephemeral=False)

            if not player.playing and not player.paused:
                await player.play(player.queue.get())

            for track in tracks:
                await db.enter_song(track.identifier, track.title, track.author, track.length, track.uri)
                await db.increment_plays(interaction.user.id, track.identifier, interaction.guild_id)

        except discord.errors.NotFound:
            logging.error("Interaction not found or expired.")
        except Exception as e:
            logging.error(f"Error processing the play command: {e}")
            try:
                await interaction.followup.send('An error occurred while trying to play the track.', ephemeral=True)
            except discord.errors.NotFound:
                logging.error("Failed to send follow-up message: Interaction not found or expired.")

    # Checks if the user has voted to use certain features
    async def check_voting_status(self, interaction: discord.Interaction):
        user = interaction.user
        guild = interaction.guild

        # Check if the user has voted
        if not await self.has_voted(user, guild):
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
            try:
                await interaction.followup.send(embed=embed, ephemeral=True)
            except discord.errors.NotFound:
                await interaction.channel.send(embed=embed)
            return False
        return True

    # Checks if the user has voted on Top.gg
    async def has_voted(self, user: discord.User, guild: discord.Guild) -> bool:
        print(f"Checking vote status for user {user.id} in guild {guild.id}")

        if guild.id == 1229102559453777991:
            return True

        if guild.id == config.EXEMPT_GUILD_ID:
            return True

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

    # Method to show the contents of a playlist
    async def show_playlist_contents(self, interaction: discord.Interaction, playlist):
        contents = await db.get_playlist_contents(playlist['playlist_id'])
        embed = discord.Embed(title=f"Playlist: {playlist['name']}", color=discord.Color.dark_red())
        for song in contents:
            embed.add_field(name=song['song_name'], value=f"Artist: {song['artist']}", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # Handles command execution errors and delegates to the error_handler
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

    # Command to create a new playlist
    @app_commands.command(name="create", description="Create a new playlist")
    @app_commands.describe(name="Name of the playlist", privacy="Privacy of the playlist (Public/Private)")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def create(self, interaction: discord.Interaction, name: str, privacy: str = "public"):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        guild_id = interaction.guild_id

        privacy_value = 1 if privacy.lower() == "public" else 0

        # Check if the user already has a playlist with the given name
        existing_playlists = await db.get_user_playlists(user_id)
        if any(playlist['name'].lower() == name.lower() for playlist in existing_playlists):
            await interaction.followup.send(
                f"You already have a playlist named '{name}'. Please choose a different name. 🎶", ephemeral=True)
            return

        await db.enter_guild(guild_id)
        await db.enter_user(user_id, guild_id)
        await db.create_playlist(user_id, guild_id, name, privacy_value)
        await interaction.followup.send(
            f"Awesome! Playlist '{name}' created with privacy setting {'Public' if privacy_value == 1 else 'Private'}. 🎵",
            ephemeral=True)

    @create.error
    async def create_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Checks if the user has permissions to edit a playlist
    async def check_permissions(self, user_id: int, playlist_name: str):
        return await db.check_playlist_permission(user_id, playlist_name)

    # Command to add a song to a playlist
    @app_commands.command(name="add", description="Add a song to a playlist")
    @app_commands.describe(name="Name of the playlist", query="Song to add")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def add(self, interaction: discord.Interaction, name: str, query: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send("Oops! You don't have permission to add songs to this playlist. 🎶",
                                            ephemeral=True)
            return

        search_result = await wavelink.Playable.search(query)
        if not search_result:
            await interaction.followup.send('Hmm, I couldn’t find any tracks with that query. 🎵', ephemeral=True)
            return

        track = search_result[0]
        song_id = track.identifier
        song_name = track.title
        artist = track.author
        raw_data = track.raw_data  # Use raw_data instead of URI

        result = await db.add_song_to_playlist(user_id, name, song_id, song_name, artist, raw_data)
        if result == 'Playlist not found':
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Added song '{song_name}' by '{artist}' to playlist '{name}'! <a:tadaMM:1258473486003732642>",
                ephemeral=True)

    @add.error
    async def add_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to remove a song from a playlist
    @app_commands.command(name="remove", description="Remove a song from a playlist")
    @app_commands.describe(name="Name of the playlist", query="Song to remove")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def remove(self, interaction: discord.Interaction, name: str, query: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send("Oops! You don't have permission to remove songs from this playlist. 🎶",
                                            ephemeral=True)
            return

        search_result = await wavelink.Playable.search(query)
        if not search_result:
            await interaction.followup.send('Hmm, I couldn’t find any tracks with that query. 🎵', ephemeral=True)
            return

        track = search_result[0]
        song_id = track.identifier

        result = await db.remove_song_from_playlist(user_id, name, song_id)
        if result == 'Playlist not found':
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Removed song '{track.title}' by '{track.author}' from playlist '{name}'! <a:tadaMM:1258473486003732642>",
                ephemeral=True)

    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to remove duplicate songs from a playlist
    # Command to remove duplicate songs from a playlist
    @app_commands.command(name="dedupe", description="Remove duplicate songs from a playlist")
    @app_commands.describe(name="Name of the playlist")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def dedupe(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send("Oops! You don't have permission to dedupe this playlist. 🎶",
                                            ephemeral=True)
            return

        result = await db.dedupe_playlist(user_id, name)
        if result == 'Playlist not found':
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
        else:
            await interaction.followup.send(
                f"Yay! Removed duplicate songs from playlist '{name}'. <a:tadaMM:1258473486003732642>", ephemeral=True)

    @dedupe.error
    async def dedupe_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to view a playlist
    @app_commands.command(name="view", description="View a playlist")
    @app_commands.describe(name="Name of the playlist")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def view(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        playlists = await db.view_playlist(name)
        if not playlists:
            await interaction.followup.send("Sorry, I couldn't find any playlists with that name. 🎶", ephemeral=True)
            return

        viewable_playlists = [playlist for playlist in playlists if 'privacy' in playlist and (
                playlist['privacy'] == 1 or await self.check_permissions(user_id, playlist['name']))]
        if not viewable_playlists:
            await interaction.followup.send("Oops! You don't have permission to view this playlist. 🎶", ephemeral=True)
            return

        if len(viewable_playlists) == 1:
            selected_playlist = viewable_playlists[0]
            contents = await db.get_playlist_contents(selected_playlist['playlist_id'])
            if not contents:
                await interaction.followup.send(f"Oops! The playlist '{selected_playlist['name']}' is empty. 🎶",
                                                ephemeral=True)
                return

            items_per_page = 10
            total_pages = (len(contents) + items_per_page - 1) // items_per_page
            embeds = []
            for i in range(0, len(contents), items_per_page):
                embed = discord.Embed(title=f"Playlist: {selected_playlist['name']}", color=discord.Color.dark_red())
                for song in contents[i:i + items_per_page]:
                    embed.add_field(name=song['song_name'], value=f"Artist: {song['artist']}", inline=False)
                embed.set_footer(text=f"Page {i // items_per_page + 1} of {total_pages}")
                embeds.append(embed)

            paginator = PlaylistPaginator(embeds, total_pages=total_pages)
            await interaction.followup.send(embed=embeds[0], view=paginator, ephemeral=True)
        else:
            embeds, view = await create_playlist_selection_embeds(viewable_playlists, self.bot)
            await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)

    @view.error
    async def view_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to view all playlists in the current guild
    @app_commands.command(name="guildview", description="View all playlists in the current guild")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def guildview(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        guild_id = interaction.guild_id
        playlists = await db.get_guild_playlists(guild_id)
        if not playlists:
            await interaction.followup.send("No playlists found for this guild. 🎶", ephemeral=True)
            return

        items_per_page = 10
        embeds = []
        for playlist in playlists:
            embed = discord.Embed(title=playlist['name'], description=f"Creator: {playlist['user_id']}",
                                  color=discord.Color.dark_red())
            embed.add_field(name="Privacy", value="Public" if playlist['privacy'] == 1 else "Private")
            contents = await db.get_playlist_contents(playlist['playlist_id'])
            total_pages = (len(contents) + items_per_page - 1) // items_per_page
            for i in range(0, len(contents), items_per_page):
                page_embed = embed.copy()
                for song in contents[i:i + items_per_page]:
                    page_embed.add_field(name=song['song_name'], value=f"Artist: {song['artist']}", inline=False)
                page_embed.set_footer(text=f"Page {i // items_per_page + 1} of {total_pages}")
                embeds.append(page_embed)

        paginator = PlaylistPaginator(embeds, total_pages=total_pages)
        await interaction.followup.send(embed=embeds[0], view=paginator, ephemeral=True)

    @guildview.error
    async def guildview_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to edit a playlist's settings
    @app_commands.command(name="edit", description="Edit a playlist's settings")
    @app_commands.describe(name="name")
    @app_commands.autocomplete(name=playlist_autocomplete)
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def edit(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        playlist = await db.get_playlist_by_name(name)

        if not playlist:
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
            return

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send("Oops! You don't have permission to edit this playlist. 🎶", ephemeral=True)
            return

        embed, view = await create_edit_interface(interaction, playlist)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @edit.error
    async def edit_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to invite a user to a playlist
    @app_commands.command(name="invite", description="Invite a user to a playlist")
    @app_commands.describe(name="Name of the playlist", user="User to invite")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def invite(self, interaction: discord.Interaction, name: str, user: discord.User):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        invitee_id = user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(
                "Oops! You don't have permission to invite collaborators to this playlist. 🎶", ephemeral=True)
            return

        result = await db.invite_user_to_playlist(user_id, name, invitee_id)

        if isinstance(result, str):
            await interaction.followup.send(result, ephemeral=True)
        else:
            playlist_name = result['playlist_name']
            creator_id = result['creator_id']
            try:
                creator_user = await self.bot.fetch_user(creator_id)
                dm_message = (
                    f"Hey {user.name},\n\n"
                    f"You've been invited to collaborate on the playlist **'{playlist_name}'** by {creator_user.name}!\n"
                    "You can accept or decline this invite by using the `/playlist invites` command in the server.\n\n"
                    "Happy listening!\n\n"
                    "- Music Monkey 🎵"
                )
                await user.send(dm_message)
                print(f"DM sent to {user.name} ({user.id}) about the invite to '{playlist_name}'.")
            except discord.Forbidden:
                print(f"Failed to send DM to {user.name} ({user.id}).")

            await interaction.followup.send(f"Invited {user.name} to playlist '{playlist_name}'. 🎶", ephemeral=True)

    @invite.error
    async def invite_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to view the user's playlist invites
    @app_commands.command(name="invites", description="View your playlist invites")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def invites(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        invites = await db.get_user_invites(user_id)
        if not invites:
            await interaction.followup.send("No invites found. 🎶", ephemeral=True)
            return

        embeds, view = await create_invite_view_embeds(invites, self.bot)
        await interaction.followup.send(embed=embeds[0], view=view, ephemeral=True)

    @invites.error
    async def invites_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @app_commands.command(name="play", description="Play all songs from a playlist")
    @app_commands.describe(name="Name of the playlist")
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def play(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        guild_id = interaction.guild_id

        playlists = await db.view_playlist(name)
        if not playlists:
            await interaction.followup.send("Sorry, I couldn't find any playlists with that name. 🎶", ephemeral=True)
            return

        viewable_playlists = []
        for playlist in playlists:
            if playlist['privacy'] == 1 or user_id == playlist['user_id']:
                viewable_playlists.append(playlist)
            else:
                collaborators = await db.get_playlist_collaborators(playlist['playlist_id'])
                if user_id in collaborators:
                    viewable_playlists.append(playlist)

        if not viewable_playlists:
            await interaction.followup.send("Oops! You don't have permission to view this playlist. 🎶", ephemeral=True)
            return

        channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
        if not channel:
            await interaction.followup.send("Please join a voice channel to play music. 🎶", ephemeral=True)
            return

        player = interaction.guild.voice_client
        if not player:
            player = await channel.connect(cls=wavelink.Player)
            player.guild_id = guild_id
            player.interaction_channel_id = interaction.channel_id

        if len(viewable_playlists) == 1:
            selected_playlist = viewable_playlists[0]
            contents = await db.get_playlist_contents(selected_playlist['playlist_id'])
            if not contents:
                await interaction.followup.send(f"Oops! The playlist '{selected_playlist['name']}' is empty. 🎶",
                                                ephemeral=True)
                return

            await self.play_songs(interaction, contents, player)

            embed = discord.Embed(
                title="Playing Playlist 🎶",
                description=f"Playing all songs from playlist '{selected_playlist['name']}'! <a:tadaMM:1258473486003732642>",
                color=discord.Color.dark_red()
            )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Enjoy your music!", icon_url=interaction.user.display_avatar.url)

            await interaction.followup.send(embed=embed, ephemeral=False)
        else:
            view = PlaylistPlaySelectView(viewable_playlists, interaction)
            # No need to send response here as PlaylistPlaySelectView handles it

    @play.error
    async def play_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    # Command to delete a playlist
    @app_commands.command(name="delete", description="Delete a playlist")
    @app_commands.describe(name="Name of the playlist")
    @app_commands.autocomplete(name=playlist_autocomplete)
    @discord.app_commands.checks.cooldown(1, 3)  # 1 use every 3 seconds
    async def delete(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if not await self.check_voting_status(interaction):
            return

        user_id = interaction.user.id
        playlist = await db.get_user_playlist_by_name(user_id, name)
        if not playlist:
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
            return

        if playlist['user_id'] != user_id:
            await interaction.followup.send("Oops! You don't have permission to delete this playlist. 🎶",
                                            ephemeral=True)
            return

        view = ConfirmDeleteView(user_id, name, playlist['playlist_id'])
        await interaction.followup.send(f"Are you sure you want to delete the playlist '{name}'? 🎶", view=view,
                                        ephemeral=True)

    @delete.error
    async def delete_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

# Sets up the cog in the bot
async def setup(bot):
    await bot.add_cog(Playlist(bot))
