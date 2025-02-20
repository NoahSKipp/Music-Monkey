# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 17.12.2024                    #
# ========================================= #

import discord
import json
import google.generativeai as genai
from utils.embeds import create_basic_embed, create_error_embed
from database import database as db
from utils.logging import get_logger
import aiomysql

import config


# Configure Google Gemini

def configure_gemini(api_key):
    genai.configure(api_key=config.GEMINI)

logger = get_logger(__name__)

class RecapService:
    def __init__(self, bot):
        self.bot = bot

    async def generate_recap(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Defer immediately

        try:
            user_id = interaction.user.id

            # Fetch data from the database
            stats = await db.get_user_stats(user_id)

            if not stats:
                await interaction.followup.send(
                    embed=create_error_embed("No music data found to create a recap.")
                )
                return

            # Stats breakdown
            total_songs_played = stats['total_songs_played']
            total_hours_played = stats['total_hours_played']
            top_artist = stats['top_artist'] or "None"
            top_song = stats['top_song'] or "None"

            # Additional fun stats from the database
            total_artists = await self.get_total_artists(user_id)
            total_unique_songs = await self.get_total_unique_songs(user_id)
            most_used_source = await self.get_most_used_source(user_id)
            top_3_artists = await self.get_top_3_artists(user_id)
            top_3_songs = await self.get_top_3_songs(user_id)

            # Check if all stats are zero
            if (
                total_songs_played == 0 and total_hours_played == 0 and
                total_artists == 0 and total_unique_songs == 0 and
                not top_3_artists and not top_3_songs
            ):
                embed = create_basic_embed(
                    title="🎵 Your Music Journey Awaits! 🎵",
                    description=(
                        "It looks like your music journey hasn't started just yet! 🐒🎶\n\n"
                        "Play some music and let Music Monkey create a wonderful recap for you. "
                        "We can't wait to see what your music adventure brings!"
                    )
                )
                embed.set_footer(
                    text="Music Monkey is here to cheer you on! 🐵✨",
                    icon_url=self.bot.user.display_avatar.url
                )
                await interaction.followup.send(embed=embed)
                return

            # Log fetched data for debugging
            logger.debug(
                f"Stats fetched: Total Songs Played: {total_songs_played}, Total Hours Played: {total_hours_played}, Top Artist: {top_artist}, Top Song: {top_song}")
            logger.debug(
                f"Additional Stats: Total Artists: {total_artists}, Total Unique Songs: {total_unique_songs}, Most Used Source: {most_used_source}")
            logger.debug(f"Top 3 Artists: {top_3_artists}, Top 3 Songs: {top_3_songs}")

            # Generate a unique identity
            identity = await self.generate_gemini_identity(
                top_artist, top_song, total_artists, total_unique_songs, most_used_source, total_songs_played,
                total_hours_played, top_3_songs
            )

            # Descriptions for each identity
            identity_descriptions = {
                "The Genre Nomad": "You explore a wide range of genres, embracing diversity in your listening habits.",
                "The Hit Seeker": "You love keeping up with chart-topping hits and trending songs.",
                "The Deep Diver": "You enjoy diving into deep cuts and uncovering hidden musical gems.",
                "The Artist Loyalist": "You stick with your favorite artists, listening to them religiously.",
                "The Mood Maker": "You curate playlists to match your mood and set the vibe perfectly.",
                "The Time Traveler": "You enjoy music from across eras, embracing sounds from decades past.",
                "The Beat Enthusiast": "You focus on rhythm, beats, and musicality, living for the groove."
            }

            personality_description = identity_descriptions.get(identity,
                                                                "You have a diverse and engaging taste in music!")

            # Create the embed
            embed = create_basic_embed(
                title="🎶 Your 2024 Recap 🎶",
                description=(
                    f"✨**{identity}**\n"
                    f"{personality_description}\n"
                    f"ㅤ"
                )
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)

            # Add database stats to the embed
            embed.add_field(name="🎤 **Top Artist**", value=f"\n`{top_artist}`", inline=True)
            embed.add_field(name="🎵 **Top Song**", value=f"`{top_song}`", inline=True)

            embed.add_field(name="🏆 **Top 3 Artists**", value="\n".join([f"- {artist}" for artist in top_3_artists]),
                            inline=False)
            embed.add_field(name="🎷 **Top 3 Songs**", value="\n".join([f"- {song}" for song in top_3_songs]),
                            inline=False)

            embed.add_field(name="✨ **Highlights** ✨", value=(
                f"- 🔁 **Total Songs Played:** `{total_songs_played}`\n"
                f"- ⏳ **Total Hours Played:** `{total_hours_played:.2f} hours`\n"
                f"- 🌐 **Most Used Source:** `{most_used_source}`\n"
                f"- 🎨 **Total Artists:** `{total_artists}`\n"
                f"- 🎶 **Total Unique Songs:** `{total_unique_songs}`"
            ), inline=False)

            embed.set_footer(text="Thanks for listening with us!", icon_url=self.bot.user.display_avatar.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            logger.error(f"Error generating recap: {e}")
            await interaction.followup.send(
                embed=create_error_embed("An error occurred while generating your recap.")
            )

    async def execute_query(self, query, params):
        async with aiomysql.connect(**db.MYSQL_CONFIG) as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                return await cur.fetchall()

    async def get_total_artists(self, user_id):
        try:
            query = '''
                SELECT COUNT(DISTINCT songs.artist) AS total_artists
                FROM plays
                JOIN songs ON plays.song_id = songs.song_id
                WHERE plays.user_id = %s
            '''
            result = await self.execute_query(query, (user_id,))
            return result[0]["total_artists"] if result and "total_artists" in result[0] else 0
        except Exception as e:
            logger.error(f"Error fetching total artists count: {e}")
            return 0

    async def get_total_unique_songs(self, user_id):
        try:
            query = '''
                SELECT COUNT(DISTINCT plays.song_id) AS total_unique_songs
                FROM plays
                WHERE plays.user_id = %s
            '''
            result = await self.execute_query(query, (user_id,))
            return result[0]["total_unique_songs"] if result and "total_unique_songs" in result[0] else 0
        except Exception as e:
            logger.error(f"Error fetching total unique songs count: {e}")
            return 0

    async def get_top_3_artists(self, user_id):
        try:
            query = '''
                SELECT songs.artist, SUM(plays.count) AS play_count
                FROM plays
                JOIN songs ON plays.song_id = songs.song_id
                WHERE plays.user_id = %s
                GROUP BY songs.artist
                ORDER BY play_count DESC
                LIMIT 3
            '''
            result = await self.execute_query(query, (user_id,))
            return [f"{row['artist']} ({row['play_count']} plays)" for row in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching top 3 artists: {e}")
            return []

    async def get_top_3_songs(self, user_id):
        try:
            query = '''
                SELECT songs.name, songs.artist, SUM(plays.count) AS play_count
                FROM plays
                JOIN songs ON plays.song_id = songs.song_id
                WHERE plays.user_id = %s
                GROUP BY songs.name, songs.artist
                ORDER BY play_count DESC
                LIMIT 3
            '''
            result = await self.execute_query(query, (user_id,))
            return [f"{row['name']} by {row['artist']} ({row['play_count']} plays)" for row in result] if result else []
        except Exception as e:
            logger.error(f"Error fetching top 3 songs: {e}")
            return []

    async def get_most_used_source(self, user_id):
        try:
            query = '''
                SELECT songs.uri
                FROM plays
                JOIN songs ON plays.song_id = songs.song_id
                WHERE plays.user_id = %s
            '''
            result = await self.execute_query(query, (user_id,))
            if not result:
                return "Unknown"

            # Analyze URIs to determine the most used source
            sources = {}
            for row in result:
                uri = row["uri"]
                if "youtube" in uri.lower():
                    source = "YouTube"
                elif "soundcloud" in uri.lower():
                    source = "SoundCloud"
                elif "spotify" in uri.lower():
                    source = "Spotify"
                elif "deezer" in uri.lower():
                    source = "Deezer"
                else:
                    source = "Other"

                sources[source] = sources.get(source, 0) + 1

            most_used = max(sources, key=sources.get)
            return most_used

        except Exception as e:
            logger.error(f"Error fetching most used source: {e}")
            return "Unknown"

    async def generate_gemini_identity(self, top_artist, top_song, total_artists, total_unique_songs, most_used_source,
                                       total_songs_played, total_hours_played, top_3_songs):
        try:
            prompt = (
                """
                Analyze the following user data and select the most fitting music identity from the provided options. 
                User Data:
                - Top Artist: {top_artist}
                - Top Song: {top_song}
                - Total Artists: {total_artists}
                - Total Unique Songs: {total_unique_songs}
                - Most Used Source: {most_used_source}
                - Total Songs Played: {total_songs_played}
                - Total Hours Played: {total_hours_played:.2f}
                - Top Songs: {top_3_songs}

                Identities:
                1. The Genre Nomad (description: You explore a wide range of genres, embracing diversity in your listening habits.) 
                2. The Hit Seeker (description: You love keeping up with chart-topping hits and trending songs.)
                3. The Deep Diver (description: You enjoy diving into deep cuts and uncovering hidden musical gems.)
                4. The Artist Loyalist (description: You stick with your favorite artists, listening to them religiously.)
                5. The Mood Maker (description: You curate playlists to match your mood and set the vibe perfectly.)
                6. The Time Traveler (description: You enjoy music from across eras, embracing sounds from decades past.)
                7. The Beat Enthusiast (description: You focus on rhythm, beats, and musicality, living for the groove.)

                Respond with the identity name and briefly explain the choice.
                """
            ).format(
                top_artist=top_artist,
                top_song=top_song,
                total_artists=total_artists,
                total_unique_songs=total_unique_songs,
                most_used_source=most_used_source,
                total_songs_played=total_songs_played,
                total_hours_played=total_hours_played,
                top_3_songs="\n".join(top_3_songs)
            )

            model = genai.GenerativeModel(model_name="gemini-1.0-pro")
            convo = model.start_chat(history=[])
            convo.send_message(prompt)
            response = convo.last.text.strip()

            # Log Gemini's response with explanation
            logger.debug(f"Gemini full response: {response}")
            print(f"Gemini full response: {response}")

            # Extract the identity from the response
            lines = response.split("\n", 1)
            identity = lines[0].strip()

            return identity

        except Exception as e:
            logger.warning(f"Gemini identity generation failed: {e}")
            return "Music Explorer"

