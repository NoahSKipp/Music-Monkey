import discord
import wavelink
import json
from utils.voting_checks import has_voted
from utils.interaction_checks import restriction_check
from utils.embeds import create_basic_embed, create_error_embed
from utils.logging import get_logger
from database import database as db
from utils.playlistbuttons import (
    PlaylistPlaySelectView, ConfirmDeleteView,
    PlaylistPaginator, create_playlist_selection_embeds, create_invite_view_embeds,
    create_edit_interface
)

# Initialize the logger from logging.py
logger = get_logger(__name__)

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
        await db.add_song_to_playlist(interaction.user.id, selected_playlist, self.track.identifier, self.track.title,
                                      self.track.author, self.track.raw_data)
        await interaction.response.send_message(
            embed=create_basic_embed("", f"Added to your playlist '{selected_playlist}'! 🎶"), ephemeral=True)
        self.stop()


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
        await interaction.response.send_message(
            embed=create_basic_embed("", f"Playlist name updated to '{new_name}'. 🎶"), ephemeral=True)


async def create_edit_interface(interaction: discord.Interaction, playlist):
    embed = create_basic_embed(f"Edit Playlist: {playlist['name']}", "")  # Add an empty description
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
            embed=create_basic_embed("", f"Playlist privacy updated to {'Public' if selected_privacy == 1 else 'Private'} 🎶"),
            ephemeral=True
        )

    privacy_select = discord.ui.Select(placeholder='Change Privacy', options=privacy_options, custom_id="privacy_select")
    privacy_select.callback = privacy_callback
    view.add_item(privacy_select)

    async def delete_collaborator_callback(interaction: discord.Interaction):
        collaborators = await db.get_playlist_collaborators(playlist['playlist_id'])
        if not collaborators:
            await interaction.followup.send(embed=create_error_embed("No collaborators to delete. 🎶"), ephemeral=True)
            return
        embed, view = await create_collaborator_delete_interface(playlist['playlist_id'], collaborators, interaction.client)
        await interaction.response.edit_message(embed=embed, view=view)

    delete_collaborator_button = discord.ui.Button(label="Delete Collaborator", style=discord.ButtonStyle.danger, custom_id="delete_collaborator_button")
    delete_collaborator_button.callback = delete_collaborator_callback
    view.add_item(delete_collaborator_button)

    async def edit_name_callback(interaction: discord.Interaction):
        modal = EditPlaylistNameModal(playlist['playlist_id'], playlist['name'])
        await interaction.response.send_modal(modal)

    edit_name_button = discord.ui.Button(label="Edit Name", style=discord.ButtonStyle.secondary, custom_id="edit_name_button")
    edit_name_button.callback = edit_name_callback
    view.add_item(edit_name_button)

    return embed, view


async def create_collaborator_delete_interface(playlist_id, collaborators, client):
    embed = create_basic_embed("Delete Collaborator", "Select a collaborator to delete")

    options = []
    for collaborator_id in collaborators:
        try:
            user_id = int(collaborator_id)
            user = await client.fetch_user(user_id)
            options.append(discord.SelectOption(label=user.name, value=str(user_id)))
        except ValueError:
            continue

    if not options:
        embed = create_error_embed("No collaborators to delete.")
        view = discord.ui.View()
        return embed, view

    select = discord.ui.Select(placeholder="Select a collaborator", options=options, custom_id="delete_collaborator_select")

    async def select_callback(interaction: discord.Interaction):
        selected_user_id = int(select.values[0])
        await db.remove_collaborator_from_playlist(playlist_id, selected_user_id)
        await interaction.followup.send(
            embed=create_basic_embed("", f"Collaborator {selected_user_id} has been removed. 🎶"), ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)
    return embed, view


async def create_playlist_selection_embeds(playlists, bot):
    view = PlaylistSelectView(playlists, None)
    await view.update_options(selected_playlist_id=playlists[0]['playlist_id'])

    embeds = []
    for playlist in playlists:
        creator = bot.get_user(playlist['user_id'])
        if not creator:
            creator = await bot.fetch_user(playlist['user_id'])
        embed = create_basic_embed(f"{playlist['name']}", f"Creator: {creator.name}")
        embed.add_field(name="Privacy", value="Public" if playlist['privacy'] == 1 else "Private")
        if playlist['privacy'] == 1:  # Public playlist
            contents = await db.get_playlist_contents(playlist['playlist_id'])
            embed.add_field(name="Song Count", value=str(len(contents)))
        embeds.append(embed)

    return embeds, view


class PlaylistService:
    def __init__(self, bot):
        self.bot = bot

    async def playlist_autocomplete(self, interaction: discord.Interaction, current: str):
        user_id = interaction.user.id
        playlists = await db.get_user_playlists(user_id)
        return [
            discord.app_commands.Choice(name=playlist['name'], value=playlist['name'])
            for playlist in playlists if current.lower() in playlist['name'].lower()
        ]

    async def create_playlist(self, interaction: discord.Interaction, name: str, privacy: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        guild_id = interaction.guild_id
        privacy_value = 1 if privacy.lower() == "public" else 0

        existing_playlists = await db.get_user_playlists(user_id)
        if any(playlist['name'].lower() == name.lower() for playlist in existing_playlists):
            await interaction.followup.send(embed=create_error_embed(f"You already have a playlist named '{name}'. "
                                                                     f"Please choose a different name. 🎶"))
            return

        await db.enter_guild(guild_id)
        await db.enter_user(user_id, guild_id)
        await db.create_playlist(user_id, guild_id, name, privacy_value)
        await interaction.followup.send(embed=create_basic_embed("", f"Awesome! Playlist '{name}' created with privacy "
                                                                     f"setting {'Public' if privacy_value == 1 else 'Private'}. 🎵"))

    async def add_song_to_playlist(self, interaction: discord.Interaction, name: str, query: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(embed=create_error_embed("Oops! You don't have permission to add songs to "
                                                                     "this playlist. 🎶"))
            return

        search_result = await wavelink.Playable.search(query)
        if not search_result:
            await interaction.followup.send(
                embed=create_error_embed('Hmm, I couldn’t find any tracks with that query. 🎵'))
            return

        track = search_result[0]
        song_id = track.identifier
        song_name = track.title
        artist = track.author
        raw_data = track.raw_data  # Use raw_data instead of URI

        result = await db.add_song_to_playlist(user_id, name, song_id, song_name, artist, raw_data)
        if result == 'Playlist not found':
            await interaction.followup.send(embed=create_error_embed("Sorry, I couldn't find that playlist. 🎶"))
        else:
            await interaction.followup.send(
                embed=create_basic_embed("", f"Added song '{song_name}' by '{artist}' to playlist '{name}'! 🎉"))

    async def remove_song_from_playlist(self, interaction: discord.Interaction, name: str, query: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(embed=create_error_embed("Oops! You don't have permission to remove songs "
                                                                     "from this playlist. 🎶"))
            return

        search_result = await wavelink.Playable.search(query)
        if not search_result:
            await interaction.followup.send(
                embed=create_error_embed('Hmm, I couldn’t find any tracks with that query. 🎵'))
            return

        track = search_result[0]
        song_id = track.identifier

        result = await db.remove_song_from_playlist(user_id, name, song_id)
        if result == 'Playlist not found':
            await interaction.followup.send(embed=create_error_embed("Sorry, I couldn't find that playlist. 🎶"))
        else:
            await interaction.followup.send(embed=create_basic_embed("",
                                                                     f"Removed song '{track.title}' by '{track.author}' from playlist '{name}'! 🎉"))

    async def dedupe_playlist(self, interaction: discord.Interaction, name: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to dedupe this playlist. 🎶"))
            return

        result = await db.dedupe_playlist(user_id, name)
        if result == 'Playlist not found':
            await interaction.followup.send(embed=create_error_embed("Sorry, I couldn't find that playlist. 🎶"))
        else:
            await interaction.followup.send(
                embed=create_basic_embed("", f"Yay! Removed duplicate songs from playlist '{name}'. 🎉"))

    async def view_playlist(self, interaction: discord.Interaction, name: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        playlists = await db.view_playlist(name)
        if not playlists:
            await interaction.followup.send(
                embed=create_error_embed("Sorry, I couldn't find any playlists with that name. 🎶"))
            return

        viewable_playlists = [playlist for playlist in playlists if 'privacy' in playlist and (
                playlist['privacy'] == 1 or await self.check_permissions(user_id, playlist['name']))]
        if not viewable_playlists:
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to view this playlist. 🎶"))
            return

        if len(viewable_playlists) == 1:
            selected_playlist = viewable_playlists[0]
            contents = await db.get_playlist_contents(selected_playlist['playlist_id'])
            if not contents:
                await interaction.followup.send(
                    embed=create_error_embed(f"Oops! The playlist '{selected_playlist['name']}' is empty. 🎶"))
                return

            items_per_page = 10
            total_pages = (len(contents) + items_per_page - 1) // items_per_page
            embeds = []
            for i in range(0, len(contents), items_per_page):
                embed = create_basic_embed("", f"Playlist: {selected_playlist['name']}")
                for song in contents[i:i + items_per_page]:
                    embed.add_field(name=song['song_name'], value=f"Artist: {song['artist']}", inline=False)
                embed.set_footer(text=f"Page {i // items_per_page + 1} of {total_pages}")
                embeds.append(embed)

            paginator = PlaylistPaginator(embeds, total_pages=total_pages)
            await interaction.followup.send(embed=embeds[0], view=paginator)
        else:
            embeds, view = await create_playlist_selection_embeds(viewable_playlists, self.bot)
            await interaction.followup.send(embed=embeds[0], view=view)

    async def view_guild_playlists(self, interaction: discord.Interaction):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        guild_id = interaction.guild_id
        playlists = await db.get_guild_playlists(guild_id)
        if not playlists:
            await interaction.followup.send(embed=create_error_embed("No playlists found for this guild. 🎶"))
            return

        items_per_page = 10
        embeds = []
        for playlist in playlists:
            embed = create_basic_embed(f"{playlist['name']}", f"Creator: {playlist['user_id']}")
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
        await interaction.followup.send(embed=embeds[0], view=paginator)

    async def edit_playlist(self, interaction: discord.Interaction, name: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        playlist = await db.get_playlist_by_name(name)

        if not playlist:
            await interaction.followup.send(embed=create_error_embed("Sorry, I couldn't find that playlist. 🎶"))
            return

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to edit this playlist. 🎶"))
            return

        embed, view = await create_edit_interface(interaction, playlist)
        await interaction.followup.send(embed=embed, view=view)

    async def invite_user_to_playlist(self, interaction: discord.Interaction, name: str, user: discord.User):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        invitee_id = user.id

        if not await self.check_permissions(user_id, name):
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to invite collaborators to this playlist. 🎶"))
            return

        result = await db.invite_user_to_playlist(user_id, name, invitee_id)

        if isinstance(result, str):
            await interaction.followup.send(embed=create_error_embed(result))
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
                logger.info(f"DM sent to {user.name} ({user.id}) about the invite to '{playlist_name}'.")
            except discord.Forbidden:
                logger.warning(f"Failed to send DM to {user.name} ({user.id}).")

            await interaction.followup.send(
                embed=create_basic_embed("", f"Invited {user.name} to playlist '{playlist_name}'. 🎶"))

    async def view_user_invites(self, interaction: discord.Interaction):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        invites = await db.get_user_invites(user_id)
        if not invites:
            await interaction.followup.send(embed=create_error_embed("No invites found. 🎶"))
            return

        embeds, view = await create_invite_view_embeds(invites, self.bot)
        await interaction.followup.send(embed=embeds[0], view=view)

    async def play_playlist(self, interaction: discord.Interaction, name: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        guild_id = interaction.guild_id

        playlists = await db.view_playlist(name)
        if not playlists:
            await interaction.followup.send(
                embed=create_error_embed("Sorry, I couldn't find any playlists with that name. 🎶"))
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
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to view this playlist. 🎶"))
            return

        channel = interaction.user.voice.channel if interaction.user and interaction.user.voice else None
        if not channel:
            await interaction.followup.send(embed=create_error_embed("Please join a voice channel to play music. 🎶"))
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
                await interaction.followup.send(
                    embed=create_error_embed(f"Oops! The playlist '{selected_playlist['name']}' is empty. 🎶"))
                return

            await self.play_songs(interaction, contents, player)

            embed = create_basic_embed("Playing Playlist 🎶",
                                       f"Playing all songs from playlist '{selected_playlist['name']}'! 🎉"
                                       )
            embed.set_thumbnail(url=self.bot.user.display_avatar.url)
            embed.set_footer(text="Enjoy your music!", icon_url=interaction.user.display_avatar.url)

            await interaction.followup.send(embed=embed)
        else:
            view = PlaylistPlaySelectView(viewable_playlists, interaction)
            await interaction.followup.send(view=view)

    async def delete_playlist(self, interaction: discord.Interaction, name: str):
        if not await restriction_check(interaction):
            return

        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        user_id = interaction.user.id
        playlist = await db.get_user_playlist_by_name(user_id, name)
        if not playlist:
            await interaction.followup.send(embed=create_error_embed("Sorry, I couldn't find that playlist. 🎶"))
            return

        if playlist['user_id'] != user_id:
            await interaction.followup.send(
                embed=create_error_embed("Oops! You don't have permission to delete this playlist. 🎶"))
            return

        view = ConfirmDeleteView(user_id, name, playlist['playlist_id'])
        embed = create_basic_embed("", f"Are you sure you want to delete the playlist '{name}'? 🎶")
        await interaction.followup.send(embed=embed, view=view)

    async def play_songs(self, interaction, songs, player):
        try:
            tracks = []
            for song in songs:
                raw_data = json.loads(song['raw_data'])
                track = wavelink.Playable(data=raw_data)
                tracks.append(track)

            for track in tracks:
                track.extras = {"requester_id": interaction.user.id}
                player.queue.put(track)

            embed = create_basic_embed("**Added to Queue**", f"{len(tracks)} tracks from the playlist"
                                       )
            embed.set_footer(text=f"Queue length: {len(player.queue)}")
            await interaction.followup.send(embed=embed, ephemeral=False)

            if not player.playing and not player.paused:
                await player.play(player.queue.get())

            for track in tracks:
                await db.enter_song(track.identifier, track.title, track.author, track.length, track.uri)
                await db.increment_plays(interaction.user.id, track.identifier, interaction.guild_id)

        except discord.errors.NotFound:
            logger.error("Interaction not found or expired.")
        except Exception as e:
            logger.error(f"Error processing the play command: {e}")
            try:
                await interaction.followup.send(
                    embed=create_error_embed('An error occurred while trying to play the track.'), ephemeral=True)
            except discord.errors.NotFound:
                logger.error("Failed to send follow-up message: Interaction not found or expired.")

    async def add_song_to_playlist_via_heart_button(self, interaction: discord.Interaction, track: wavelink.Playable):
        user_id = interaction.user.id
        guild_id = interaction.guild_id

        # Fetch user's playlists
        playlists = await db.get_user_playlists(user_id)

        if not playlists:
            # No playlists found, create a new one called "{User}'s Favorites"
            playlist_name = f"{interaction.user.name}'s Favorites"
            await db.create_playlist(user_id, guild_id, playlist_name, privacy=0)
            await db.add_song_to_playlist(user_id, playlist_name, track.identifier, track.title, track.author,
                                          track.raw_data)
            embed = create_basic_embed("", f"Added to your new playlist '{playlist_name}'! 🎶")
            await interaction.followup.send(embed=embed, ephemeral=True)
        elif len(playlists) == 1:
            # Only one playlist found, add to that playlist
            playlist_name = playlists[0]['name']
            await db.add_song_to_playlist(user_id, playlist_name, track.identifier, track.title, track.author,
                                          track.raw_data)
            embed = create_basic_embed("", f"Added to your playlist '{playlist_name}'! 🎶")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            # Multiple playlists found, show a dropdown menu to select one
            view = PlaylistSelectView(playlists, track)
            embed = create_basic_embed("", "Select a playlist to add the song to:")
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    async def check_permissions(self, user_id: int, playlist_name: str):
        return await db.check_playlist_permission(user_id, playlist_name)
