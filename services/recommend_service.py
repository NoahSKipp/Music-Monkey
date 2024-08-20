import google.generativeai as genai
import discord
import wavelink
import config
from utils.logging import get_logger
from utils.interaction_checks import restriction_check
from utils.voting_checks import has_voted
from utils.embeds import create_basic_embed, create_error_embed

# Configure Google Gemini API
genai.configure(api_key=config.GEMINI)


class RecommendService:
    def __init__(self, bot):
        self.bot = bot

    async def recommend_songs(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Defer the interaction to prevent timeout

        # Check if the user has voted, and handle response if not
        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        # Check for restrictions and send an error if the user doesn't have permission
        if not await restriction_check(interaction):
            embed = create_error_embed("You don't have permission to use this feature.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Ensure that music is currently playing before proceeding
        player = interaction.guild.voice_client
        if not player or not wavelink.Player.connected or player.current is None:
            embed = create_error_embed("No music is currently playing.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        # Prepare the list of songs currently playing and in the queue
        current_track = player.current.title if player.current else 'No track currently playing'
        queue_tracks = [track.title for track in list(player.queue)] if player.queue else []
        song_list = [current_track] + queue_tracks
        song_list_str = ', '.join(song_list)

        # Generate a recommendation prompt for Google Gemini
        prompt = f"Based on these songs: {song_list_str}. Please generate 5 song recommendations."
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ]

        # Interact with the generative model to get song recommendations
        model = genai.GenerativeModel(model_name="gemini-1.0-pro", safety_settings=safety_settings)
        convo = model.start_chat(history=[])
        convo.send_message(prompt)
        response = convo.last.text

        # Present the recommendations to the user with buttons to add them to the queue
        view = SelectSongsView(response, player)
        embed = create_basic_embed(
            title="Song Recommendations",
            description=f"Based on your current queue, here are some song recommendations:\n{response}"
        )
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class SelectSongsView(discord.ui.View):
    def __init__(self, recommendations, player):
        super().__init__()
        self.player = player

        # Split the response into individual song recommendations
        songs = recommendations.split('\n')

        for song in songs:
            if song.strip():  # Ensure the song line is not empty
                button_label = song.strip().split('. ', 1)[1] if '. ' in song else song.strip()  # Remove the numbering
                self.add_item(SongButton(label=button_label, player=self.player, song_query=button_label))


class SongButton(discord.ui.Button):
    def __init__(self, label, player, song_query):
        super().__init__(style=discord.ButtonStyle.primary, label=label[:80], custom_id=label[:80])
        self.song_query = song_query
        self.player = player

    async def callback(self, interaction: discord.Interaction):
        # Search for the song using the query and add it to the queue if found
        tracks = await wavelink.Playable.search(self.song_query, source=wavelink.TrackSource.YouTubeMusic)
        if tracks:
            track = tracks[0] if isinstance(tracks, list) and tracks else tracks
            track.extras = {"requester_id": interaction.user.id}  # Add requester ID to track metadata
            self.player.queue.put(track)
            await interaction.response.send_message(embed=create_basic_embed(
                title="Added to Queue",
                description=f"Added to queue: {self.song_query}"
            ), ephemeral=True)
        else:
            await interaction.response.send_message(embed=create_error_embed(
                error_message="Unable to find the song."
            ), ephemeral=True)
