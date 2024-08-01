# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 31.07.2024                    #
# ========================================= #

import discord
from discord.ext import commands
from discord import app_commands, Interaction, ui
from datetime import datetime
from database import add_restricted_command, remove_restricted_command, get_restricted_commands, get_updates_status, \
    get_updates_channel, get_dj_role, get_dj_only_enabled, set_dj_role, set_dj_only_enabled
import database as db
from permissions import can_manage_roles

# Define all possible commands for autocomplete
ALL_COMMANDS = [
    "play", "pause", "resume", "skip", "stop", "jump", "loop", "lyrics", "filters", "resetfilter", "queue", "shuffle",
    "move", "remove", "clear", "cleargone", "autoplay", "playlist create", "playlist add", "playlist play",
    "playlist view", "playlist guildview", "playlist remove", "playlist dedupe", "playlist edit", "playlist delete",
    "playlist delete", "playlist invite", "playlist invites", "recommend", "wondertrade", "receive", "leaderboard",
    "profile", "monkey", "fact"
]

async def command_autocomplete(interaction: Interaction, current: str):
    return [
        app_commands.Choice(name=cmd, value=cmd)
        for cmd in ALL_COMMANDS
        if current.lower() in cmd.lower()
    ]

class RoleSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder='Choose a DJ role...', min_values=1, max_values=1, options=options)
        self.selected_role_id = None

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.view.user_id:
            await interaction.response.send_message("You do not have permission to interact with this.", ephemeral=True)
            return

        self.selected_role_id = int(self.values[0])
        role_name = next((option.label for option in self.options if option.value == self.values[0]), 'Unknown Role')
        await interaction.response.send_message(f"The DJ role has been set to **{role_name}**.", ephemeral=True)
        self.view.stop()

class SelectRoleView(discord.ui.View):
    def __init__(self, options, user_id):
        super().__init__()
        self.user_id = user_id
        self.add_item(RoleSelect(options))

class AllRestrictedCommandsView(ui.View):
    def __init__(self, restricted_commands):
        super().__init__()
        self.restricted_commands = restricted_commands

    @ui.button(label="All DJ Commands", style=discord.ButtonStyle.primary, disabled=True)
    async def show_all_restricted(self, interaction: Interaction, button: ui.Button):
        embed = discord.Embed(
            title="All DJ Commands",
            description="\n".join(f"- {cmd}" for cmd in self.restricted_commands),
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    async def ensure_manage_roles_permission(self, interaction: Interaction):
        if not can_manage_roles(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return False
        return True

    @discord.app_commands.checks.cooldown(1, 3)
    @discord.app_commands.command(name='config', description='Displays configuration details')
    async def config(self, interaction: Interaction):
        if not await self.ensure_manage_roles_permission(interaction):
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch data
        restricted_commands = await get_restricted_commands(interaction.guild.id)
        restricted_list = restricted_commands.split(',') if restricted_commands else []
        current_dj_role_id = await get_dj_role(interaction.guild.id)
        dj_mode_status = await get_dj_only_enabled(interaction.guild.id)

        # Determine DJ role name
        if current_dj_role_id:
            current_dj_role = interaction.guild.get_role(current_dj_role_id)
            dj_role_name = current_dj_role.name if current_dj_role else "Unknown Role"
        else:
            dj_role_name = "None"

        # Create embed
        embed = discord.Embed(
            title="Bot Config",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        # DJ Commands
        if restricted_list:
            display_commands = restricted_list[:3]
            remaining_count = len(restricted_list) - 3
            if remaining_count > 0:
                display_commands.append("...")
            embed.add_field(name="DJ Commands", value="\n".join(f"- {cmd}" for cmd in display_commands), inline=True)
        else:
            embed.add_field(name="DJ Commands", value="No DJ commands.", inline=True)

        # DJ Mode and DJ Role
        embed.add_field(name="DJ Mode", value="Enabled" if dj_mode_status else "Disabled", inline=True)
        embed.add_field(name="DJ Role", value=dj_role_name, inline=True)

        # Updates Status and Updates Channel
        updates_status = await get_updates_status(interaction.guild.id)
        updates_status_text = "Enabled" if updates_status == 1 else "Disabled"
        updates_channel_id = await get_updates_channel(interaction.guild.id)
        if updates_channel_id:
            updates_channel = interaction.guild.get_channel(updates_channel_id)
            channel_name = updates_channel.name if updates_channel else "Unknown Channel"
        else:
            channel_name = "Unknown Channel"

        embed.add_field(name="Updates Status", value=updates_status_text, inline=True)
        embed.add_field(name="Updates Channel", value=f"#{channel_name}", inline=True)

        # Add an invisible field to force the layout
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Bot Latency, Bot Uptime, Bot Region
        embed.add_field(name="Bot Latency", value=f"{round(self.bot.latency * 1000)} ms", inline=True)
        bot_uptime = datetime.utcnow() - self.bot.uptime
        embed.add_field(name="Bot Uptime", value=str(bot_uptime).split('.')[0], inline=True)
        embed.add_field(name="Bot Region", value="US East", inline=True)

        # View for restricted commands
        view = AllRestrictedCommandsView(restricted_list)
        if len(restricted_list) > 3:
            view.children[0].disabled = False

        await interaction.followup.send(embed=embed, view=view)

    @config.error
    async def config_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

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

class DJCommands(commands.GroupCog, group_name="dj"):
    def __init__(self, bot):
        self.bot = bot

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

    async def ensure_manage_roles_permission(self, interaction: Interaction):
        if not can_manage_roles(interaction.user):
            await interaction.response.send_message("You do not have permission to use this command.", ephemeral=True)
            return False
        return True

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='list', description='Displays the list of DJ commands')
    async def restricted(self, interaction: Interaction):
        if not await self.ensure_manage_roles_permission(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        restricted_commands = await get_restricted_commands(interaction.guild.id)
        if restricted_commands:
            commands_list = restricted_commands.split(',')
            embed = discord.Embed(title="DJ Commands",
                                  description="\n".join(f"- {cmd}" for cmd in commands_list))
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("No commands are currently restricted.")

    @restricted.error
    async def restricted_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='add', description='Add a command to the DJ list')
    @app_commands.describe(command_name='Name of the command to restrict')
    @app_commands.autocomplete(command_name=command_autocomplete)
    async def add(self, interaction: Interaction, command_name: str):
        if not await self.ensure_manage_roles_permission(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        if command_name not in ALL_COMMANDS:
            await interaction.followup.send(f"The command `{command_name}` is not a valid command.", ephemeral=True)
            return
        restricted_commands = await get_restricted_commands(interaction.guild.id)
        if restricted_commands and command_name in restricted_commands.split(','):
            await interaction.followup.send(f"The command `{command_name}` is already restricted.", ephemeral=True)
            return
        await add_restricted_command(interaction.guild.id, command_name)
        await interaction.followup.send(f"Command `{command_name}` has been restricted.", ephemeral=True)

    @add.error
    async def add_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='remove', description='Remove a command from the DJ restricted list')
    @app_commands.describe(command_name='Name of the command to unrestrict')
    @app_commands.autocomplete(command_name=command_autocomplete)
    async def remove(self, interaction: Interaction, command_name: str):
        if not await self.ensure_manage_roles_permission(interaction):
            return
        await interaction.response.defer(ephemeral=True)
        restricted_commands = await get_restricted_commands(interaction.guild.id)
        if not restricted_commands or command_name not in restricted_commands.split(','):
            await interaction.followup.send(f"The command `{command_name}` is not currently restricted.",
                                            ephemeral=True)
            return
        await remove_restricted_command(interaction.guild.id, command_name)
        await interaction.followup.send(f"Command `{command_name}` has been unrestricted.", ephemeral=True)

    @remove.error
    async def remove_error(self, interaction: Interaction, error: app_commands.AppCommandError):
        await self.error_handler(interaction, error)

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='toggle', description='Toggle DJ-only command restrictions')
    async def toggle_dj_mode(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "You do not have the required permissions to use this command.",
                ephemeral=True
            )
            return

        guild_id = interaction.guild_id
        current_state = await db.get_dj_only_enabled(guild_id) or False
        new_state = not current_state
        await db.set_dj_only_enabled(guild_id, new_state)

        await interaction.followup.send(f'DJ-only mode is now {"enabled" if new_state else "disabled"}.')

    @discord.app_commands.checks.cooldown(1, 3)
    @app_commands.command(name='set', description='Set a DJ role')
    async def set_dj_role(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.followup.send(
                "You do not have the required permissions to use this command.",
                ephemeral=True
            )
            return

        roles = [role for role in interaction.guild.roles if role.name != "@everyone" and not role.is_bot_managed()]
        options = [
            discord.SelectOption(label=role.name, value=str(role.id), description=f"Set {role.name} as the DJ role")
            for role in roles
        ]
        view = SelectRoleView(options, interaction.user.id)
        await interaction.followup.send("Please select a DJ role from the menu:", view=view, ephemeral=True)

        # Wait for the view to finish
        await view.wait()

        selected_role_id = None
        for item in view.children:
            if isinstance(item, RoleSelect):
                selected_role_id = item.selected_role_id
                break

        if selected_role_id:
            await db.set_dj_role(interaction.guild_id, selected_role_id)
            role = interaction.guild.get_role(selected_role_id)
            if role:
                await interaction.followup.send(f"DJ role has been set to **{role.name}**.")
            else:
                await interaction.followup.send("Selected DJ role not found.")
        else:
            await interaction.followup.send("No DJ role selected.")

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

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
    await bot.add_cog(DJCommands(bot))
