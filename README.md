[![GitHub Profile](https://img.shields.io/badge/NoahSKipp-GitHub-blue?logo=github)](https://github.com/NoahSKipp)
[![GitHub Profile](https://img.shields.io/badge/iiPaper-GitHub-blue?logo=github)](https://github.com/iiPaper)
[![License](https://img.shields.io/badge/Creative%20Commons%20License-CC%20BY--NC%204.0-information)](https://github.com/NoahSKipp/Music-Monkey/blob/main/LICENSE)
[![Discord](https://img.shields.io/discord/136026412669861888?color=7289DA&label=Discord&logo=discord)](https://discord.gg/kyamXgVU68)
[![Invite Music Monkey](https://img.shields.io/badge/Invite-Music%20Monkey-blue.svg?style=flat-square)](https://discord.com/oauth2/authorize?client_id=1228071177239531620)
[![Latest Release](https://img.shields.io/github/v/release/NoahSKipp/music-monkey?label=Latest%20Release&logo=github)](https://github.com/NoahSKipp/music-monkey/releases/latest)
[![CodeFactor](https://www.codefactor.io/repository/github/noahskipp/music-monkey/badge?s=7d0d36f3ae02ebc4c5139dce9dc932bc42f5bcdb)](https://www.codefactor.io/repository/github/noahskipp/music-monkey)



![Music Monkey](https://i.imgur.com/7T0l5ZI.png)

Welcome to Music Monkey, your friendly music companion on Discord! Enhance your gaming sessions with seamless music playback and a variety of cool features.

## Table of Contents
- [Features](#features)
- [Getting Started](#getting-started)
- [Setting Up Music Monkey](#setting-up-music-monkey)
- [Commands](#commands)
  - [Playback Commands](#playback-commands)
  - [Queue Management Commands](#queue-management-commands)
  - [Settings and Configuration Commands](#settings-and-configuration-commands)
  - [Music Recommendations](#music-recommendations)
  - [Community and User Profiles](#community-and-user-profiles)
- [Support and Contributions](#support-and-contributions)
- [Authors](#authors)
- [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

- 🎵 **Play Music:** Play music directly in your voice channel.
- 📋 **Manage Queues:** Easily manage music queues.
- 🔍 **Music Recommendations:** Get advanced music recommendations powered by AI.
- 🏆 **Leaderboards:** View server-wide music leaderboards.
- 📈 **Personalized Profiles:** Track your listening habits with personalized music profiles.
- ✨ **Wondertrade:** Share music recommendations across different servers.

## Getting Started

To add Music Monkey to your server, click the [invite link](https://discord.com/oauth2/authorize?client_id=1228071177239531620).

For support and more detailed help, join our [Support Server](https://discord.gg/kyamXgVU68).

## Setting Up Music Monkey

To set up and host Music Monkey yourself, follow these steps:

1. **Clone the Repository:**
```git clone https://github.com/NoahSKipp/Music-Monkey.git```

2. **Install Dependencies:**
```pip install -r requirements.txt```

3. **Configuration:**

   - Create a `.env` file in the root directory and add the necessary environment variables:

     ```env
     # Discord Bot Token
     TOKEN='your_discord_bot_token'

     # Discord Bot Application ID
     APPLICATION_ID='your_application_id'

     # Gemini API Key
     GEMINI='your_gemini_api_key'

     # Lavalink Node Variables
     LAVALINK_HOST='your_lavalink_host'
     LAVALINK_PASSWORD='your_lavalink_password'
     LAVALINK_PORT=your_lavalink_port

     # Lavalink Node 2 Variables (optional)
     LAVALINK_HOST2='your_second_lavalink_host'
     LAVALINK_PASSWORD2='your_second_lavalink_password'
     LAVALINK_PORT2=your_second_lavalink_port

     # Database Login
     MYSQL_USER='your_database_username'
     MYSQL_PASSWORD='your_database_password'
     ```
   
   - If you want to use more/less than two Lavalink nodes, add them to the `.env` file accordingly.
  
   - If you're adding/removing nodes, modify the node pool in `main.py` accordingly.

5. **Run the Bot:**

   To start the bot, run the following command in your terminal from the root directory of the project, or simply run that file through your IDE:

   ```sh
   python main.py

## Commands

Music Monkey comes with a variety of commands to control music playback, manage queues, customize settings, and more.

### Playback Commands
- `/play [song|URL]` - Play or add a song to the queue.
- `/pause` - Pause the current song.
- `/resume` - Resume the paused music.
- `/skip` - Skip the current track.
- `/stop` - Stop the music and clear the queue.
- `/jump [time]` - Jump to a specific time in the track.
- `/loop [mode]` - Toggle loop mode for the current track or queue.
- `/filters` - Select a filter to apply to the playback.
- `/resetfilter` - Reset the currently applied filter(s).

### Queue Management Commands
- `/queue` - Show the current music queue.
- `/shuffle` - Shuffle the music queue.
- `/move [position] [new_position]` - Move a song in the queue from one position to another.
- `/remove [position]` - Remove a specific song from the queue based on its position.
- `/clear` - Clear the current music queue.
- `/cleargone` - Clear all songs from the queue that were requested by users who have since left the voice channel.
- `/autoplay [mode]` - Toggle AutoPlay mode to automatically continue playing songs when the queue is empty.

### Settings and Configuration Commands
- `/dj` - Toggle DJ-only command restrictions.
- `/setdj [role]` - Set a DJ role for managing the bot.

### Music Recommendations
- `/recommend` - Get music recommendations based on your listening history, powered by AI.
- `/wondertrade [query] [note]` - Submit a song recommendation to anyone else using the bot across any server!
- `/receive` - Receive a song recommendation from anyone else using the bot across any server!

### Community and User Profiles
- `/leaderboard` - Show the music leaderboard for this server.
- `/profile [user]` - Display your own, or another user's, personal music profile.

## Support and Suggestions

For support and more detailed help, join our [Support Server](https://discord.gg/kyamXgVU68).

If you're facing any issues or would like to suggest a new feature, feel free to contact us on our support server using the designated channel.
If you've encountered a bug, open an [issue](https://github.com/NoahSKipp/Music-Monkey/issues) or use our [support server](https://discord.gg/kyamXgVU68)'s designated channel.

## Authors

- **Noah Samuel Kipp**
- **Samuel Jaden Garcia Munoz**

## License

This project is licensed under the Creative Commons Attribution-NonCommercial 4.0 International License (CC BY-NC 4.0).

## Acknowledgments

Special thanks to everyone who has contributed to the development and testing of Music Monkey. Your support is greatly appreciated!

---
