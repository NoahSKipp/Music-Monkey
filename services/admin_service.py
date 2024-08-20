import discord
from discord import Interaction
from discord import app_commands
from database.database import add_restricted_command, remove_restricted_command, get_restricted_commands, \
    get_updates_status, get_updates_channel, get_dj_role, get_dj_only_enabled, set_dj_role, set_dj_only_enabled
from utils.interaction_checks import can_manage_roles
from utils.voting_checks import has_voted
from utils.embeds import create_basic_embed, create_error_embed
from utils.logging import get_logger

ALL_COMMANDS = [
    "play", "pause", "resume", "skip", "stop", "jump", "loop", "lyrics", "filters", "resetfilter", "queue", "shuffle",
    "move", "remove", "clear", "cleargone", "autoplay", "playlist create", "playlist add", "playlist play",
    "playlist view", "playlist guildview", "playlist remove", "playlist dedupe", "playlist edit", "playlist delete",
    "playlist delete", "playlist invite", "playlist invites", "recommend", "wondertrade", "receive", "leaderboard",
    "profile", "monkey", "fact"
]


class AdminService:
    def __init__(self, bot):
        self.bot = bot
        self.logger = get_logger(__name__)

    async def botinfo(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions
        if not await can_manage_roles(interaction):
            self.logger.warning(f"User {interaction.user} tried to access botinfo without proper permissions.")
            return

        try:
            # Fetch restricted commands, DJ role, and DJ-only mode status
            restricted_commands = await get_restricted_commands(interaction.guild.id)
            restricted_list = restricted_commands.split(',') if restricted_commands else []
            current_dj_role_id = await get_dj_role(interaction.guild.id)
            dj_mode_status = await get_dj_only_enabled(interaction.guild.id)

            dj_role = "None"
            if current_dj_role_id:
                current_dj_role = interaction.guild.get_role(current_dj_role_id)
                dj_role = current_dj_role.name if current_dj_role else "None"

            playing_in_guilds = sum(1 for vc in self.bot.voice_clients if vc.playing)
            shard_id = interaction.guild.shard_id + 1
            total_shards = self.bot.shard_count

            # Construct the bot statistics block
            bot_stats_block = (
                "```yaml\n"
                "[Bot Stats]\n"
                f"Shards             : {shard_id}/{total_shards}\n"
                f"Servers            : {len(self.bot.guilds)}\n"
                f"Playing Music In   : {playing_in_guilds} servers\n"
                f"Bot Latency        : {round(self.bot.latency * 1000)} ms\n"
                "```"
            )

            # Construct the DJ information block
            dj_block = (
                "```yaml\n"
                "[DJ Information]\n"
                f"Mode               : {'Enabled' if dj_mode_status else 'Disabled'}\n"
                f"Role               : {dj_role}\n"
                f"Restricted Commands : {', '.join(restricted_list) if restricted_list else 'None'}\n"
                "```"
            )

            # Construct the updates information block
            updates_status = await get_updates_status(interaction.guild.id)
            updates_status_text = "Enabled" if updates_status == 1 else "Disabled"
            updates_channel_id = await get_updates_channel(interaction.guild.id)
            if updates_channel_id:
                updates_channel = interaction.guild.get_channel(updates_channel_id)
                channel_name = updates_channel.name if updates_channel else "None"
            else:
                channel_name = "None"

            updates_block = (
                "```yaml\n"
                "[Updates Information]\n"
                f"Updates Status    : {updates_status_text}\n"
                f"Updates Channel   : #{channel_name}\n"
                "```"
            )

            response = f"{bot_stats_block}\n{dj_block}\n{updates_block}"

            embed = create_basic_embed("Bot Information", response)

            await interaction.followup.send(embed=embed)
            self.logger.info(f"Bot info sent to user {interaction.user} in guild {interaction.guild.name}.")
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while generating bot info: {str(e)}")
            await interaction.followup.send(embed=create_error_embed("Failed to retrieve bot info."), ephemeral=True)

    async def restricted(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions and has voted
        if not (await can_manage_roles(interaction) and await has_voted(interaction.user, interaction.guild, self.bot,
                                                                        interaction)):
            self.logger.warning(
                f"User {interaction.user} tried to access restricted commands without proper permissions.")
            return

        try:
            # Fetch and display restricted commands
            restricted_commands = await get_restricted_commands(interaction.guild.id)
            if restricted_commands:
                commands_list = restricted_commands.split(',')
                embed = create_basic_embed(
                    "DJ Commands",
                    "\n".join(f"- {cmd}" for cmd in commands_list)
                )
                self.logger.info(
                    f"Restricted commands for DJ retrieved by {interaction.user} in guild {interaction.guild.name}.")
            else:
                embed = create_basic_embed("", "No commands are currently restricted.")
                self.logger.info(f"No restricted commands found for DJ in guild {interaction.guild.name}.")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while retrieving restricted commands: {str(e)}")
            await interaction.followup.send(embed=create_error_embed("Failed to retrieve restricted commands."),
                                            ephemeral=True)

    async def add_command(self, interaction: Interaction, command: str):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions and has voted
        if not (await can_manage_roles(interaction) and await has_voted(interaction.user, interaction.guild, self.bot,
                                                                        interaction)):
            return

        try:
            # Add a command to the restricted list if it is not already restricted
            restricted_commands = await get_restricted_commands(interaction.guild.id)
            if restricted_commands and command in restricted_commands.split(','):
                embed = create_error_embed(
                    f"The command `{command}` is already restricted."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            await add_restricted_command(interaction.guild.id, command)
            embed = create_basic_embed(
                "",
                f"Command `{command}` has been restricted."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info(
                f"Command `{command}` restricted by {interaction.user} in guild {interaction.guild.name}.")
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while adding restricted command: {str(e)}")
            embed = create_error_embed(
                "Failed to add restricted command."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def remove_command(self, interaction: Interaction, command: str):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions and has voted
        if not (await can_manage_roles(interaction) and await has_voted(interaction.user, interaction.guild, self.bot,
                                                                        interaction)):
            return

        try:
            # Remove a command from the restricted list if it is currently restricted
            restricted_commands = await get_restricted_commands(interaction.guild.id)
            if not restricted_commands or command not in restricted_commands.split(','):
                embed = create_error_embed(
                    f"The command `{command}` is not currently restricted."
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            await remove_restricted_command(interaction.guild.id, command)
            embed = create_basic_embed("", f"Command `{command}` has been unrestricted.")
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info(
                f"Command `{command}` unrestricted by {interaction.user} in guild {interaction.guild.name}.")
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while removing restricted command: {str(e)}")
            await interaction.followup.send(embed=create_error_embed("Failed to remove restricted command."),
                                            ephemeral=True)

    async def toggle_dj_mode(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions and has voted
        if not (await can_manage_roles(interaction) and await has_voted(interaction.user, interaction.guild, self.bot,
                                                                        interaction)):
            return

        try:
            # Toggle the DJ-only mode
            guild_id = interaction.guild.id
            current_state = await get_dj_only_enabled(guild_id) or False
            new_state = not current_state
            await set_dj_only_enabled(guild_id, new_state)

            embed = create_basic_embed("", f'DJ-only mode is now {"enabled" if new_state else "disabled"}.')
            await interaction.followup.send(embed=embed, ephemeral=True)
            self.logger.info(
                f"DJ-only mode toggled to {'enabled' if new_state else 'disabled'} by {interaction.user} in guild {interaction.guild.name}.")
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while toggling DJ-only mode: {str(e)}")
            await interaction.followup.send(embed=create_error_embed("Failed to toggle DJ-only mode."), ephemeral=True)

    async def set_dj_role(self, interaction: Interaction, role_name: str):
        await interaction.response.defer(ephemeral=True)

        # Check if the user has the required permissions and has voted
        if not (await can_manage_roles(interaction) and await has_voted(interaction.user, interaction.guild, self.bot,
                                                                        interaction)):
            return

        # Find the role by name in the guild
        role = discord.utils.get(interaction.guild.roles, name=role_name)
        if not role:
            embed = create_error_embed(
                "The specified role could not be found in the guild."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return

        try:
            # Set the DJ role
            await set_dj_role(interaction.guild.id, role.id)
            embed = create_basic_embed(
                "",
                f"DJ role has been set to **{role.name}**."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            # Log and send an error message if something goes wrong
            self.logger.error(f"An error occurred while setting DJ role: {str(e)}")
            embed = create_error_embed(
                "Failed to set DJ role."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    async def autocomplete_command(self, interaction: Interaction, current: str):
        return [
            app_commands.Choice(name=cmd, value=cmd)
            for cmd in ALL_COMMANDS
            if current.lower() in cmd.lower()
        ]

    async def autocomplete_role(self, interaction: Interaction, current: str):
        roles = [
            app_commands.Choice(name=role.name, value=role.name)
            for role in interaction.guild.roles
            if current.lower() in role.name.lower() and role.name != "@everyone"
        ]
        return roles[:25]  # Limit to 25 results as per Discord's API limits
