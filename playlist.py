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


# This function provides autocomplete suggestions for playlist names based on the current input
async def playlist_autocomplete(interaction: discord.Interaction, current: str):
    user_id = interaction.user.id
    playlists = await db.get_user_playlists(user_id)
    return [
        app_commands.Choice(name=playlist['name'], value=playlist['name'])
        for playlist in playlists if current.lower() in playlist['name'].lower()
    ]


# View for selecting a playlist to edit
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

    # Callback function when a playlist is selected for editing
    async def select_callback(self, interaction):
        selected_playlist_id = int(self.select.values[0])
        selected_playlist = next(
            (playlist for playlist in self.playlists if playlist['playlist_id'] == selected_playlist_id), None)

        if selected_playlist:
            embed, view = await create_edit_interface(interaction, selected_playlist)
            await interaction.response.edit_message(embed=embed, view=view)
        self.stop()


# View for selecting a playlist to play
class PlaylistPlaySelectView(discord.ui.View):
    def __init__(self, playlists, interaction):
        super().__init__(timeout=60)
        self.playlists = playlists
        self.interaction = interaction

        self.interaction.client.loop.create_task(self.update_options())

    # Updates the options in the select menu based on the user's playlists
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

    # Callback function when a playlist is selected to play
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


# Playlist management cog with various commands for creating, editing, and interacting with playlists
class Playlist(commands.GroupCog, group_name="playlist"):
    def __init__(self, bot):
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction):
        logging.debug(f'Interaction check for {interaction.user} in guild {interaction.guild_id}')
        await db.enter_guild(interaction.guild_id)
        await db.enter_user(interaction.user.id, interaction.guild_id)
        dj_only = await db.get_dj_only_enabled(interaction.guild_id)
        dj_role_id = await db.get_dj_role(interaction.guild_id)

        if not dj_only:
            return True

        has_permissions = interaction.user.guild_permissions.manage_roles
        is_dj = any(role.id == dj_role_id for role in interaction.user.roles)

        if has_permissions or is_dj:
            return True

        await interaction.response.send_message(
            "DJ-only mode is enabled. You need DJ privileges to use this.",
            ephemeral=True
        )
        return False

    # Modified play_song function to handle playlist playback
    async def play_songs(self, interaction, songs, player):
        try:
            tracks = []
            for song in songs:
                search_result = await wavelink.Playable.search(song['uri'])
                if search_result:
                    tracks.append(search_result[0])

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

        if guild.id == config.EXEMPT_GUILD_ID:
            return True
        if guild.id == '1253445742388056064':
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
        uri = track.uri

        result = await db.add_song_to_playlist(user_id, name, song_id, song_name, artist, uri)
        if result == 'Playlist not found':
            await interaction.followup.send("Sorry, I couldn't find that playlist. 🎶", ephemeral=True)
        else:
            await interaction.followup.send(f"Added song '{song_name}' by '{artist}' to playlist '{name}'! <a:tadaMM:1258473486003732642>",
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
                f"Removed song '{track.title}' by '{track.author}' from playlist '{name}'! <a:tadaMM:1258473486003732642>", ephemeral=True)

    @remove.error
    async def remove_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

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
            await interaction.followup.send(f"Yay! Removed duplicate songs from playlist '{name}'. <a:tadaMM:1258473486003732642>", ephemeral=True)

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


# View for confirming the deletion of a playlist
class ConfirmDeleteView(discord.ui.View):
    def __init__(self, user_id, playlist_name, playlist_id):
        super().__init__()
        self.user_id = user_id
        self.playlist_name = playlist_name
        self.playlist_id = playlist_id

    # Callback function for the confirm button to delete the playlist
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()  # Defer the interaction to avoid expiration

        result = await db.delete_playlist(self.user_id, self.playlist_name, self.playlist_id)
        message = await interaction.original_response()
        await message.edit(content=result, view=None)

    # Callback function for the cancel button to cancel the deletion
    @discord.ui.button(label="No", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()  # Defer the interaction to avoid expiration

        message = await interaction.original_response()
        await message.edit(content="Playlist deletion cancelled. 🎶", view=None)


# Paginator view for navigating through playlist contents
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

    # Updates the paginator view and buttons
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

    # Updates the state of the buttons in the paginator
    def update_buttons(self):
        self.first_button.disabled = self.current_page == 0
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == self.total_pages - 1
        self.last_button.disabled = self.current_page == self.total_pages - 1

    # Callback function for the first button in the paginator
    async def first_page(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
        self.current_page = 0
        await self.update(interaction)

    # Callback function for the previous button in the paginator
    async def previous(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
        if self.current_page > 0:
            self.current_page -= 1
            await self.update(interaction)

    # Callback function for the next button in the paginator
    async def next(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            await self.update(interaction)

    # Callback function for the last button in the paginator
    async def last_page(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
        self.current_page = self.total_pages - 1
        await self.update(interaction)


# Paginator view for navigating through embeds
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

    # Updates the paginator view and buttons
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

    # Updates the state of the buttons in the paginator
    def update_buttons(self):
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page >= len(self.embeds) - 1

    # Callback function for the previous button in the paginator
    async def previous(self, interaction: discord.Interaction):
        self.current_page -= 1
        await self.update(interaction)

    # Callback function for the next button in the paginator
    async def next(self, interaction: discord.Interaction):
        self.current_page += 1
        await self.update(interaction)

    # Callback function for the accept button in the paginator
    async def accept(self, interaction: discord.Interaction):
        invite = self.invites[self.current_page]
        await db.accept_playlist_invite(invite['invite_id'])
        message = f"Invite to playlist '{invite['name']}' accepted! 🎉"
        await self.remove_current_invite()
        await self.update(interaction, message)

    # Callback function for the decline button in the paginator
    async def decline(self, interaction: discord.Interaction):
        invite = self.invites[self.current_page]
        await db.decline_playlist_invite(invite['invite_id'])
        message = f"Invite to playlist '{invite['name']}' declined. 🎶"
        await self.remove_current_invite()
        await self.update(interaction, message)

    # Removes the current invite from the list
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


# View for selecting a playlist from a list
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

    # Updates the options in the select menu
    async def update_options(self, selected_playlist_id=None):
        print("Updating options")  # Debug print

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
                print(f"Option: {label}, Value: {playlist['playlist_id']}")  # Debug print
        self.select.options = options

    # Updates the view with the selected playlist
    async def update_view(self, interaction: discord.Interaction, selected_playlist_id=None):
        await self.update_options(selected_playlist_id)
        embed = await self.create_embed()
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except discord.errors.InteractionResponded:
            await interaction.edit_original_response(embed=embed, view=self)

    # Callback function for selecting a playlist
    async def select_playlist(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
        selected_playlist_id = int(self.select.values[0])
        self.selected_playlist = next(
            (playlist for playlist in self.playlists if playlist['playlist_id'] == selected_playlist_id), None)
        await self.update_view(interaction, selected_playlist_id)

    # Callback function for viewing the selected playlist
    async def view_playlist(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer the interaction to avoid expiration
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

    # Creates an embed for the selected playlist
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


# Creates embeds and a view for selecting a playlist
async def create_playlist_selection_embeds(playlists, bot):
    view = PlaylistSelection(playlists, bot)
    await view.update_options(
        selected_playlist_id=playlists[0]['playlist_id'])  # Ensure options are set before creating the view

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


# Creates embeds and a view for displaying playlist invites
async def create_invite_view_embeds(invites, bot):
    embeds = []
    invite_ids = set()  # Track processed invite IDs to avoid duplicates

    for invite in invites:
        if invite['invite_id'] in invite_ids:
            continue  # Skip duplicates

        invite_ids.add(invite['invite_id'])
        embed = discord.Embed(title=invite['name'], description=f"Invited by: <@{invite['user_id']}>",
                              color=discord.Color.dark_red())
        embed.set_footer(text=f"Invite ID: {invite['invite_id']}")
        embeds.append(embed)

    view = Paginator(embeds, invites, bot)
    return embeds, view


# Creates the interface for editing a playlist
async def create_edit_interface(interaction: discord.Interaction, playlist):
    embed = discord.Embed(title=f"Edit Playlist: {playlist['name']}", color=discord.Color.dark_red())
    embed.add_field(name="Current Privacy", value="Public" if playlist['privacy'] == 1 else "Private")

    view = discord.ui.View()

    privacy_options = [
        discord.SelectOption(label='Public', value='1'),
        discord.SelectOption(label='Private', value='0')
    ]

    # Callback function for changing playlist privacy
    async def privacy_callback(interaction: discord.Interaction):
        selected_privacy = int(interaction.data['values'][0])
        await db.update_playlist_privacy(playlist['playlist_id'], selected_privacy)
        await interaction.response.send_message(
            f"Playlist privacy updated to {'Public' if selected_privacy == 1 else 'Private'} 🎶", ephemeral=True)

    privacy_select = discord.ui.Select(placeholder='Change Privacy', options=privacy_options,
                                       custom_id="privacy_select")
    privacy_select.callback = privacy_callback
    view.add_item(privacy_select)

    # Callback function for deleting a collaborator from the playlist
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

    # Callback function for editing the playlist name
    async def edit_name_callback(interaction: discord.Interaction):
        modal = EditPlaylistNameModal(playlist['playlist_id'], playlist['name'])
        await interaction.response.send_modal(modal)

    edit_name_button = discord.ui.Button(label="Edit Name", style=discord.ButtonStyle.secondary,
                                         custom_id="edit_name_button")
    edit_name_button.callback = edit_name_callback
    view.add_item(edit_name_button)

    return embed, view


# Creates the interface for deleting a collaborator from the playlist
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

    # Callback function for selecting a collaborator to delete
    async def select_callback(interaction: discord.Interaction):
        selected_user_id = int(select.values[0])
        await db.remove_collaborator_from_playlist(playlist_id, selected_user_id)
        await interaction.followup.send(f"Collaborator {selected_user_id} has been removed. 🎶", ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    return embed, view


# Modal for editing the name of a playlist
class EditPlaylistNameModal(discord.ui.Modal, title="Edit Playlist Name"):
    def __init__(self, playlist_id, current_name):
        super().__init__()
        self.playlist_id = playlist_id
        self.current_name = current_name
        self.add_item(discord.ui.TextInput(label="New Playlist Name", placeholder="Enter new playlist name",
                                           default=current_name))

    # Callback function for submitting the new playlist name
    async def on_submit(self, interaction: discord.Interaction):
        new_name = self.children[0].value
        await db.edit_playlist_name(self.playlist_id, new_name)
        await interaction.response.send_message(f"Playlist name updated to '{new_name}'. 🎶", ephemeral=True)


# Sets up the cog in the bot
async def setup(bot):
    await bot.add_cog(Playlist(bot))
