# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 07.05.2024                    #
# ========================================= #

import discord
from discord import app_commands
from discord.ext import commands
import google.generativeai as genai
import logging
import config
import wavelink

# API key for Google Gemini
genai.configure(api_key=config.GEMINI)

class RecommendCog(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        discord.utils.setup_logging(level=logging.INFO)

    @app_commands.command(name='recommend', description='Get song recommendations based on the current queue.')
    async def recommend(self, interaction: discord.Interaction):
        player = interaction.guild.voice_client
        if not player or not wavelink.Player.connected or wavelink.Player.current is None:
            await interaction.response.send_message("No music is currently playing.", ephemeral=True)
            return

        current_track = player.current.title if player.current else 'No track currently playing'
        queue_tracks = [track.title for track in list(player.queue)] if player.queue else []
        song_list = [current_track] + queue_tracks
        song_list_str = ', '.join(song_list)

        prompt = f"Based on these songs: {song_list_str}. Please generate 5 song recommendations."

        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        model = genai.GenerativeModel(model_name="gemini-1.0-pro", safety_settings=safety_settings)
        convo = model.start_chat(history=[])
        convo.send_message(prompt)
        response = convo.last.text

        view = SelectSongsView(response, player)
        await interaction.response.send_message(f"Based on your current queue, here are some song recommendations:\n{response}", view=view, ephemeral=True)

class SelectSongsView(discord.ui.View):
    def __init__(self, recommendations, player):
        super().__init__()
        self.player = player

        songs = recommendations.split('\n')

        for song in songs:
            if song.strip():  # Ensure the song line is not empty
                button_label = song.strip().split('. ', 1)[1] if '. ' in song else song.strip()  # Remove the numbering
                self.add_item(SongButton(label=button_label, player=self.player, song_query=button_label))

class SongButton(discord.ui.Button):
    def __init__(self, label, player, song_query):
        super().__init__(style=discord.ButtonStyle.primary, label=label[:80], custom_id=label[:80])  # Limit label to 80 characters
        self.song_query = song_query
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        # Search for the track using the song name and artist
        tracks = await wavelink.Playable.search(self.song_query, source=wavelink.TrackSource.YouTubeMusic)
        if tracks:
            track = tracks[0] if isinstance(tracks, list) and tracks else tracks
            track.extras = {"requester_id": interaction.user.id}  # Add requester ID to track metadata
            self.player.queue.put(track)
            await interaction.response.send_message(f"Added to queue: {self.song_query}", ephemeral=True)
        else:
            await interaction.response.send_message("Unable to find the song.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(RecommendCog(bot))
