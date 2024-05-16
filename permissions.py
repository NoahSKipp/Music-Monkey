# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.04.2024                    #
# ========================================= #

from discord import Member

def can_manage_roles(member: Member) -> bool:
    return member.guild_permissions.manage_roles

def is_dj(member: Member) -> bool:
    return any(role.name == 'DJ' for role in member.roles)
