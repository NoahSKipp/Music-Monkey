import discord
from discord import ui
from utils.embeds import create_basic_embed, create_error_embed
from utils.logging import get_logger

class FirstJoinService:
    def __init__(self, bot):
        self.bot = bot
        self.creator_ids = ['338735185900077066']
        self.logger = get_logger(__name__)  # Initialize the logger

    async def handle_guild_join(self, guild: discord.Guild):
        channel = self.get_appropriate_channel(guild)

        if channel:
            embed = create_basic_embed(
                title="🎉 Hello from Music Monkey! 🎉",
                description=(
                    "Hey there! I'm **Music Monkey**, your new music buddy! <a:monkeyflip:1237140606296522762>\n\n"
                    "**Getting Started**\n"
                    "• Join a voice channel and type `/play` to queue up your favorite tunes.\n\n"
                    "**Explore Features**\n"
                    "• View all my features and commands through the dropdown menu below or by using the `/help` command anytime.\n\n"
                    "**Join Our Community**\n"
                    "• Make sure to join our [support server](https://discord.gg/6WqKtrXjhn) to report any issues, suggest new features, "
                    "and stay up to date with the latest updates.\n\n"
                    "**Important Notices**\n"
                    "• Occasionally, we announce **maintenance or large updates** to all servers. To configure how you receive these notifications, use the `/updates` command.\n\n"
                    "Can't wait to jam with you! 🎵"
                )
            )

            view = self.create_help_menu()
            self.add_buttons_to_view(view)

            try:
                await channel.send(embed=embed, view=view)
                self.logger.info(f"Welcome message sent to {guild.name} in {channel.name}")
            except discord.HTTPException as e:
                self.logger.error(f"Failed to send welcome message in guild {guild.name}: {str(e)}")

    def get_appropriate_channel(self, guild: discord.Guild):
        if guild.system_channel:
            return guild.system_channel
        return next((chan for chan in guild.text_channels if chan.permissions_for(guild.me).send_messages), None)

    def create_help_menu(self):
        view = ui.View(timeout=180)
        select = ui.Select(
            placeholder='🔍 Choose a category to get help with...',
            options=[
                discord.SelectOption(label='Playback Commands', description='Control the music playback', emoji='▶️'),
                discord.SelectOption(label='Queue Management', description='Manage your music queue', emoji='📋'),
                discord.SelectOption(label='Playlist Management', description='Manage your playlists', emoji='🎵'),
                discord.SelectOption(label='Settings and Configuration', description='Customize bot settings', emoji='⚙️'),
                discord.SelectOption(label='Community and Profiles', description='Engage with your community', emoji='👥'),
                discord.SelectOption(label='Music Recommendations', description='Get music recommendations', emoji='🎶'),
                discord.SelectOption(label='Fun', description='Fun commands to use', emoji='🎉'),
                discord.SelectOption(label='Support', description='Access immediate help and support resources', emoji='🤝')
            ]
        )
        select.callback = self.select_callback
        view.add_item(select)
        return view

    def add_buttons_to_view(self, view: ui.View):
        support_button = discord.ui.Button(label="Support", url="https://discord.gg/6WqKtrXjhn", style=discord.ButtonStyle.link)
        website_button = discord.ui.Button(label="Website", url="https://getmusicmonkey.com", style=discord.ButtonStyle.link)
        vote_button = discord.ui.Button(label="Vote", url="https://top.gg/bot/1228071177239531620/vote", style=discord.ButtonStyle.link)

        view.add_item(support_button)
        view.add_item(website_button)
        view.add_item(vote_button)

    async def select_callback(self, interaction: discord.Interaction):
        label = interaction.data['values'][0]  # Get the label of the selected option
        description_map = {
            'Playback Commands': self.get_playback_commands(),
            'Queue Management': self.get_queue_management_commands(),
            'Playlist Management': self.get_playlist_management_commands(),
            'Settings and Configuration': self.get_settings_commands(),
            'Community and Profiles': self.get_community_and_profiles_info(),
            'Music Recommendations': self.get_music_recommendations(),
            'Support': self.get_support_info(),
            'Fun': self.get_fun_commands()
        }

        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        try:
            await interaction.followup.send(content=description_map[label], ephemeral=True)
            self.logger.info(f"Help menu option '{label}' selected by {interaction.user} in guild {interaction.guild.name}")
        except discord.NotFound:
            self.logger.error("Failed to send follow-up: interaction token expired or invalid")

    def get_playback_commands(self):
        return ("**Playback Commands:**\n"
                "`/play [song|URL] [source]` - Play or add a song to the queue.\n"
                "`/pause` - Pause the current song.\n"
                "`/resume` - Resume the paused music.\n"
                "`/skip` - Skip the current track.\n"
                "`/stop` - Stop the music and clear the queue.\n"
                "`/jump [time]` - Jump to a specific time in the track.\n"
                "`/loop [mode]` - Toggle loop mode for the current track or queue.\n"
                "`/lyrics` - Displays the lyrics for the current song.\n"
                "`/filters` - Select a filter to apply to the playback.\n"
                "`/resetfilter` - Reset the currently applied filter(s).\n\n")

    def get_queue_management_commands(self):
        return ("**Queue Management Commands:**\n"
                "`/queue` - Show the current music queue.\n"
                "`/shuffle` - Shuffle the music queue.\n"
                "`/move [position] [new_position]` - Move a song in the queue from one position to another.\n"
                "`/remove [position]` - Remove a specific song from the queue based on its position.\n"
                "`/clear` - Clear the current music queue.\n"
                "`/cleargone` - Clear all songs from the queue that were requested by users who have since left the voice channel.\n"
                "`/autoplay [mode]` - Toggle AutoPlay mode to automatically continue playing songs when the queue is empty.\n\n")

    def get_playlist_management_commands(self):
        return ("**Playlist Management Commands:**\n"
                "`/playlist create [name] [privacy]` - Create a new playlist with the specified name and privacy setting.\n"
                "`/playlist add [name] [query]` - Add a song to the specified playlist.\n"
                "`/playlist play [name]` - Play all songs from the specified playlist.\n"
                "`/playlist view [name]` - View the contents of the specified playlist.\n"
                "`/playlist guildview` - View all playlists created in the current server.\n"
                "`/playlist remove [name] [query]` - Remove a song from the specified playlist.\n"
                "`/playlist dedupe [name]` - Remove duplicate songs from the specified playlist.\n"
                "`/playlist edit [name]` - Edit the settings of the specified playlist.\n"
                "`/playlist delete [name]` - Delete the specified playlist.\n"
                "`/playlist invite [name] [user]` - Invite a user to collaborate on the specified playlist.\n"
                "`/playlist invites` - View your playlist invites.\n\n")

    def get_settings_commands(self):
        return ("**Settings and Configuration Commands:**\n"
                "`/botinfo` - Displays the bot configuration details.\n"
                "`/dj add [command_name]` - Add a command to the DJ list.\n"
                "`/dj remove [command_name]` - Remove a command from the DJ restricted list.\n"
                "`/dj toggle` - Toggle DJ-only command restrictions.\n"
                "`/dj set` - Set a DJ role for managing the bot.\n"
                "`/updates toggle [enable | disable]` - Toggle receiving bot announcements on or off.\n"
                "`/updates set` - Set the current channel to receive bot announcements.\n\n")

    def get_music_recommendations(self):
        return ("**Music Recommendations:**\n"
                "`/recommend` - Get music recommendations based on your listening history, powered by AI.\n"
                "`/wondertrade [query] [note]` - Submit a song recommendation to anyone else using the bot across any server!\n"
                "`/receive` - Receive a song recommendation from anyone else using the bot across any server!\n\n")

    def get_community_and_profiles_info(self):
        return ("**Community and User Profiles:**\n"
                "`/leaderboard` - Show the music leaderboard for this server.\n"
                "`/profile [user]` - Display your own, or another user's, personal music profile.\n\n")

    def get_support_info(self):
        return ("**Support:**\n"
                "Need help? Visit our **[Support Server](https://discord.gg/6WqKtrXjhn)** for more detailed support "
                "from the developer and the community.\n"
                "Encountered an error? Feel free to report it by using the `/report` command!\n\n")

    def get_fun_commands(self):
        return ("**Fun Commands:**\n"
                "`/monkey` - Get a random picture of a monkey.\n"
                "`/fact` - Get a random fact about monkeys.\n\n")
