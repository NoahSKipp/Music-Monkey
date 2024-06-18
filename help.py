# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 08.05.2024                    #
# ========================================= #

import discord
from discord import app_commands, ui, ButtonStyle
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @app_commands.command(name='help', description='See all commands')
    async def help_command(self, interaction: discord.Interaction):
        embed = self.about_me_embed()
        await interaction.response.send_message(embed=embed, view=self.create_help_menu(), ephemeral=True)

    def about_me_embed(self):
        embed = discord.Embed(
            title="🐵 Meet Music Monkey! 🐵",
            description=(
                "Hello! I'm **Music Monkey**, your friendly music companion on Discord! "
                "I'm here to enhance your gaming sessions with lots of cool features and seamless music playback.\n\n"
                "**Key Features:**\n"
                "• 🎵 Play music directly in your voice channel.\n"
                "• 📋 Manage music queues with ease.\n"
                "• 🔍 Advanced music recommendations, powered by AI.\n"
                "• 🏆 View server-wide music leaderboards.\n"
                "• 📈 Personalized music profiles to track your listening habits.\n"
                "• ✨ Spread the joy of music with our **wondertrade**!"
            ),
            color=discord.Color.blue()
        )

        return embed

    def create_help_menu(self):
        view = ui.View(timeout=None)
        select = ui.Select(
            placeholder='🔍 Choose a category to get help with...',
            options=[
                discord.SelectOption(label='Playback Commands',
                                     description='Control the music playback', emoji='▶️'),
                discord.SelectOption(label='Queue Management', description='Manage your music queue', emoji='📋'),
                discord.SelectOption(label='Settings and Configuration',
                                     description='Customize bot settings', emoji='⚙️'),
                discord.SelectOption(label='Community and Profiles',
                                     description='Engage with your community',
                                     emoji='👥'),
                discord.SelectOption(label='Music Recommendations', description='Get music recommendations',
                                     emoji='🎶'),
                discord.SelectOption(label='Support',
                                     description='Access immediate help and support resources',
                                     emoji='🤝')
            ]
        )
        select.callback = self.select_callback
        view.add_item(select)
        view.add_item(self.create_support_button())
        view.add_item(self.create_invite_button())
        return view

    async def select_callback(self, interaction: discord.Interaction):
        label = interaction.data['values'][0]  # Get the label of the selected option
        description_map = {
            'Playback Commands': self.get_playback_commands(),
            'Queue Management': self.get_queue_management_commands(),
            'Settings and Configuration': self.get_settings_commands(),
            'Community and Profiles': self.get_community_and_profiles_info(),
            'Music Recommendations': self.get_music_recommendations(),
            'Support': self.get_support_info()
        }

        # Ensure to defer the interaction if not already responded to
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            await interaction.followup.send(content=description_map[label], ephemeral=True)
        except discord.NotFound:
            print("Failed to send followup: interaction token expired or invalid")

    def get_playback_commands(self):
        return ("**Playback Commands:**\n"
                "`/play [song|URL]` - Play or add a song to the queue.\n"
                "`/pause` - Pause the current song.\n"
                "`/resume` - Resume the paused music.\n"
                "`/skip` - Skip the current track.\n"
                "`/stop` - Stop the music and clear the queue.\n"
                "`/jump [time]` - Jump to a specific time in the track.\n"
                "`/loop [mode]` - Toggle loop mode for the current track or queue. \n"
                "`/filters` - Select a filter to apply to the playback.\n"
                "`/resetfilter` - Reset the currently applied filter(s).")

    def get_queue_management_commands(self):
        return ("**Queue Management Commands:**\n"
                "`/queue` - Show the current music queue.\n"
                "`/shuffle` - Shuffle the music queue.\n"
                "`/move [position] [new_position]` - Move a song in the queue from one position to another. \n"
                "`/remove [position]` - Remove a specific song from the queue based on its position.\n"
                "`/clear` - Clear the current music queue.\n"
                "`/cleargone` - Clear all songs from the queue that were requested by users who have since left the voice channel.\n"
                "`/autoplay [mode]` - Toggle AutoPlay mode to automatically continue playing songs when the queue is empty.")

    def get_settings_commands(self):
        return ("**Settings and Configuration Commands:**\n"
                "`/dj` - Toggle DJ-only command restrictions.\n"
                "`/setdj` - Set a DJ role for managing the bot.\n"
                "`/updates [enable | disable]` - Toggle receiving bot announcements on or off.\n"
                "`/updates_set` - Set the current channel to receive bot announcements.")

    def get_music_recommendations(self):
        return ("**Music Recommendations:**\n"
                "`/recommend` - Get music recommendations based on your listening history, powered by AI. \n"
                "`/wondertrade [query] [note]` - Submit a song recommendation to anyone else using the bot across any server!\n"
                "`/receive` - Receive a song recommendation from anyone else using the bot across any server!")

    def get_community_and_profiles_info(self):
        return ("**Community and User Profiles:**\n"
                "`/leaderboard` - Show the music leaderboard for this server.\n"
                "`/profile [user]` - Display your own, or another user's, personal music profile.")

    def get_support_info(self):
        return ("**Support:**\n"
                "Need help? Visit our **[Support Server](https://discord.gg/kyamXgVU68)** for more detailed support "
                "from the developer and the community.")

    def create_support_button(self):
        return ui.Button(label="Support", url="https://discord.gg/kyamXgVU68", style=ButtonStyle.link)

    def create_invite_button(self):
        return ui.Button(label="Invite me!", url="https://discord.com/oauth2/authorize?client_id=1228071177239531620",
                         style=ButtonStyle.link)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))

