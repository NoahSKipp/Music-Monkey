# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 21.04.2024                    #
# ========================================= #

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('tokens.env')

# Discord Bot Token
TOKEN = os.getenv('DISCORD_TOKEN')

# Discord Bot Application ID
APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')

# Gemini API Key
GEMINI = os.getenv('GEMINI_API_KEY')

# Lavalink Node Variables
LAVALINK_HOST = os.getenv('LAVALINK_HOST')
LAVALINK_PASSWORD = os.getenv('LAVALINK_PASSWORD')
LAVALINK_PORT = (os.getenv('LAVALINK_PORT'))

# Lavalink Node 2 Variables
LAVALINK_HOST2 = os.getenv('LAVALINK_HOST2')
LAVALINK_PASSWORD2 = os.getenv('LAVALINK_PASSWORD2')
LAVALINK_PORT2 = (os.getenv('LAVALINK_PORT2'))

# Lavalink Node 3 Variables
LAVALINK_HOST3 = os.getenv('LAVALINK_HOST3')
LAVALINK_PASSWORD3 = os.getenv('LAVALINK_PASSWORD3')
LAVALINK_PORT3 = (os.getenv('LAVALINK_PORT3'))

# Top.gg Variables
TOPGG_TOKEN = os.getenv('TOPGG_TOKEN')
AUTHORIZATION_KEY = os.getenv('AUTHORIZATION_KEY')
BOT_ID = os.getenv('BOT_ID')
PORT = os.getenv('PORT')
EXEMPT_GUILD_ID = int(os.getenv('EXEMPT_GUILD_ID'))
EXEMPT_ROLE_ID = int(os.getenv('EXEMPT_ROLE_ID'))