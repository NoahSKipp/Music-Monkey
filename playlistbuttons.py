# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 14.08..2024                   #
# ========================================= #

import discord
import database as db
import logging
import json
import wavelink


# PlaylistEditSelectView for selecting a playlist to edit
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
