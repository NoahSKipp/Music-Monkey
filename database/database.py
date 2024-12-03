# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.04.2024                    #
# ========================================= #

import aiomysql
import os
from dotenv import load_dotenv
import json

# Load environment variables from the .env file
load_dotenv()

# Define MySQL configuration
MYSQL_CONFIG = {
    'host': 'us.mysql.db.bot-hosting.net',
    'port': 3306,
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'db': os.getenv('MYSQL_NAME'),
    'autocommit': True
}


# Setup database
async def setup_database():
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT NOT NULL,
                dj_only_enabled BOOLEAN DEFAULT 0,
                dj_role_id BIGINT,
                restricted_commands TEXT DEFAULT NULL,
                updates_enabled TINYINT DEFAULT 1,
                updates_channel_id BIGINT,
                PRIMARY KEY (guild_id)
            );
            CREATE TABLE IF NOT EXISTS songs (
                song_id VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                artist VARCHAR(255) NOT NULL,
                length INT NOT NULL,
                uri VARCHAR(255) NOT NULL,
                PRIMARY KEY (song_id)
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                PRIMARY KEY (user_id, guild_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            );
            CREATE TABLE IF NOT EXISTS plays (
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                song_id VARCHAR(255) NOT NULL,
                count INT,
                PRIMARY KEY (user_id, guild_id, song_id),
                FOREIGN KEY (user_id, guild_id) REFERENCES users(user_id, guild_id),
                FOREIGN KEY (song_id) REFERENCES songs(song_id)
            );
            CREATE TABLE IF NOT EXISTS wonderTrades (
                user_id BIGINT NOT NULL,
                song_id VARCHAR(255) NOT NULL,
                note VARCHAR(60),
                PRIMARY KEY (user_id, song_id),
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (song_id) REFERENCES songs(song_id)
            );
            CREATE TABLE IF NOT EXISTS playlists (
                playlist_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id BIGINT NOT NULL,
                guild_id BIGINT NOT NULL,
                name VARCHAR(255) NOT NULL,
                privacy TINYINT NOT NULL,
                collaborators TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id),
                FOREIGN KEY (guild_id) REFERENCES guilds(guild_id)
            );
            CREATE TABLE IF NOT EXISTS playlist_songs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                playlist_id INT NOT NULL,
                song_id VARCHAR(255) NOT NULL,
                song_name VARCHAR(255) NOT NULL,
                artist VARCHAR(255) NOT NULL,
                raw_data JSON NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id)
            );
            CREATE TABLE IF NOT EXISTS playlist_invites (
                invite_id INT AUTO_INCREMENT PRIMARY KEY,
                playlist_id INT NOT NULL,
                invitee_id BIGINT NOT NULL,
                FOREIGN KEY (playlist_id) REFERENCES playlists(playlist_id)
            );
            ''')
            await conn.commit()


async def get_dj_only_enabled(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_only_enabled FROM guilds WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            if result is None:
                return False
            return bool(result[0])


async def set_dj_only_enabled(guild_id, dj_only):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE guilds SET dj_only_enabled = %s WHERE guild_id = %s', (dj_only, guild_id))
            await conn.commit()


async def get_dj_role(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_role_id FROM guilds WHERE guild_id = %s', guild_id)
            result = await cur.fetchone()
            return result[0] if result else None


async def set_dj_role(guild_id, role_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE guilds SET dj_role_id = %s WHERE guild_id = %s', (role_id, guild_id))
            await conn.commit()


async def get_restricted_commands(guild_id: int):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT restricted_commands FROM guilds WHERE guild_id=%s', (guild_id,))
            result = await cur.fetchone()
            if result:
                return result[0]  # Assuming the field contains a list or string of commands
            return None


async def add_restricted_command(guild_id: int, command: str):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT restricted_commands FROM guilds WHERE guild_id=%s', (guild_id,))
            result = await cur.fetchone()
            if result:
                commands = result[0]
                if commands:
                    commands = commands.split(',')
                    if command not in commands:
                        commands.append(command)
                        commands = ','.join(commands)
                    else:
                        return  # Command is already restricted
                else:
                    commands = command
                await cur.execute('UPDATE guilds SET restricted_commands=%s WHERE guild_id=%s', (commands, guild_id))
            else:
                await cur.execute('INSERT INTO guilds (guild_id, restricted_commands) VALUES (%s, %s)',
                                  (guild_id, command))
            await conn.commit()


async def remove_restricted_command(guild_id: int, command: str):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT restricted_commands FROM guilds WHERE guild_id=%s', (guild_id,))
            result = await cur.fetchone()
            if result:
                commands = result[0]
                if commands:
                    commands = commands.split(',')
                    if command in commands:
                        commands.remove(command)
                        commands = ','.join(commands) if commands else None
                        await cur.execute('UPDATE guilds SET restricted_commands=%s WHERE guild_id=%s',
                                          (commands, guild_id))
                        await conn.commit()


# Checks if a given guild_id is in the guilds table.
async def enter_guild(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT guild_id FROM guilds WHERE guild_id = %s", guild_id)
            guild = await cur.fetchall()
            if not guild:
                await cur.execute("INSERT INTO guilds (guild_id, dj_only_enabled, dj_role_id) VALUES (%s, 0, NULL)",
                                  guild_id)
                await conn.commit()


# Checks if a given user_id is in the users table, associated with the given guild_id.
async def enter_user(user_id, guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT user_id, guild_id FROM users WHERE  user_id = %s AND guild_id = %s",
                              (user_id, guild_id))
            user = await cur.fetchall()
            if not user:
                await cur.execute("INSERT INTO users (user_id, guild_id) VALUES (%s, %s)", (user_id, guild_id))
                await conn.commit()


# Tries to enter a given song into the songs table. If the song already exists, nothing happens.
async def enter_song(song_id, name, artist, length, uri):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT song_id FROM songs WHERE song_id = %s', song_id)
            result = await cur.fetchone()
            if not result:
                await cur.execute('INSERT INTO songs (song_id, name, artist, length, uri) VALUES (%s, %s, %s, %s, %s)',
                                  (song_id, name, artist, length, uri))
                await conn.commit()


# Tries to enter a given wonder trade into the wonderTrades table. If the song has already been recommended, nothing happens. If the user has already recommended a song, nothing happens.
async def enter_wonder_trade(user_id, song_id, note):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT user_id FROM wonderTrades WHERE user_id = %s', user_id)
            result = await cur.fetchone()
            if not result:
                await cur.execute('SELECT song_id FROM wonderTrades WHERE song_id = %s', song_id)
                result = await cur.fetchone()
                if not result:
                    await cur.execute('INSERT INTO wonderTrades (song_id, user_id, note) VALUES (%s, %s, %s)',
                                      (song_id, user_id, note))
                    await conn.commit()
                    return 'Your recommendation has been submitted!'
                else:
                    return 'This song has already been recommended by someone else. Try recommending another one!'
            else:
                return (
                    'You\'ve already recommended a song! Wait some time for someone to give it a listen and then try again!')


# Submits a wonder trade to the system.
async def submit_wonder_trade(song_id, name, artist, length, uri, user_id, note):
    await enter_song(song_id, name, artist, length, uri)
    return await enter_wonder_trade(user_id, song_id, note)


# Sends a recommendation to the user.
async def receive_wonder_trade(user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT COUNT(*) FROM wonderTrades WHERE user_id != %s', (user_id,))
            count = await cur.fetchone()
            if count and count[0] != 0:
                await cur.execute(
                    'SELECT s.uri, wt.note FROM songs AS s JOIN wonderTrades AS wt ON wt.song_id = s.song_id WHERE wt.user_id != %s ORDER BY RAND() LIMIT 1',
                    (user_id,))
                result = await cur.fetchone()
                if result:
                    return result[0], result[1]
            return '_There are no available wondertrades available at this moment. Try again later!', None


# Deletes a wonder trade based on the song URI.
async def delete_wonder_trade(uri):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'DELETE wonderTrades FROM wonderTrades JOIN songs ON wonderTrades.song_id = songs.song_id WHERE songs.uri = %s',
                uri)
            await conn.commit()


# Increments the play count for the given song, for the given user, in the given guild.
async def increment_plays(user_id, song_id, guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            # Ensure the guild exists
            await enter_guild(guild_id)

            # Ensure the user exists
            await enter_user(user_id, guild_id)

            # Check if the play record exists
            await cur.execute('SELECT count FROM plays WHERE user_id = %s AND song_id = %s AND guild_id = %s',
                              (user_id, song_id, guild_id))
            result = await cur.fetchone()
            if result:
                new_count = result[0] + 1
                await cur.execute('UPDATE plays SET count = %s WHERE user_id = %s AND song_id = %s AND guild_id = %s',
                                  (new_count, user_id, song_id, guild_id))
            else:
                await cur.execute('INSERT INTO plays (user_id, song_id, guild_id, count) VALUES (%s, %s, %s, 1)',
                                  (user_id, song_id, guild_id))

            await conn.commit()


# Returns the total play counts for each user of the given guild, in said guild. In other words, only count of songs played in the given guild.
async def get_leaderboard(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT user_id, SUM(count) AS total_count FROM plays WHERE guild_id = %s GROUP BY user_id ORDER BY total_count DESC;',
                guild_id)
            rows = await cur.fetchall()
            return rows


# Returns the top stats for a given user. Total amount of songs played, total playtime of all songs played, top played artist and top played song.
async def get_user_stats(user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT SUM(count) AS total_count FROM plays WHERE user_id = %s', (user_id,))
            total_songs = await cur.fetchone()
            if not total_songs or total_songs[0] is None:
                total_songs = 0
            else:
                total_songs = total_songs[0]

            await cur.execute(
                'SELECT SUM(songs.length * plays.count) AS total_played_length FROM plays JOIN songs ON plays.song_id = songs.song_id WHERE plays.user_id = %s;',
                (user_id,))
            total_playtime = await cur.fetchone()
            if not total_playtime or total_playtime[0] is None:
                total_playtime = 0
            else:
                total_playtime = total_playtime[0] / 3600000  # Convert milliseconds to hours

            await cur.execute(
                'SELECT songs.artist, SUM(plays.count) AS total_artist_plays FROM plays JOIN songs ON plays.song_id = songs.song_id WHERE plays.user_id = %s GROUP BY songs.artist ORDER BY total_artist_plays DESC LIMIT 1;',
                (user_id,))
            top_artist = await cur.fetchone()
            if not top_artist:
                top_artist = "None"
            else:
                top_artist = top_artist[0]

            await cur.execute(
                'SELECT songs.name, plays.count FROM plays JOIN songs ON plays.song_id = songs.song_id WHERE plays.user_id = %s ORDER BY plays.count DESC LIMIT 1;',
                (user_id,))
            top_song = await cur.fetchone()
            if not top_song:
                top_song = "None"
            else:
                top_song = top_song[0]

            return {
                'top_artist': top_artist,
                'top_song': top_song,
                'total_songs_played': total_songs,
                'total_hours_played': total_playtime
            }


# Sets the updates status of a given guild.
async def set_updates_status(guild_id, status):
    # Convert status to 0 or 1
    if status == 'enable':
        status_value = 1
    elif status == 'disable':
        status_value = 0
    else:
        raise ValueError("Invalid status value. Must be 'enable' or 'disable'.")

    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO guilds (guild_id, updates_enabled) VALUES (%s, %s) ON DUPLICATE KEY UPDATE updates_enabled = %s',
                (guild_id, status_value, status_value))
            await conn.commit()


# Gets the updates status of a given guild.
async def get_updates_status(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT updates_enabled FROM guilds WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            return result[0] if result is not None else 1  # Default to 1 (enabled) if not set


# Sets the updates channel of a given guild.
async def set_updates_channel(guild_id, channel_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO guilds (guild_id, updates_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE updates_channel_id = %s',
                (guild_id, channel_id, channel_id))
            await conn.commit()


# Retrieves the updates channel of a given guild.
async def get_updates_channel(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT updates_channel_id FROM guilds WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            return result[0] if result else None


# Create a new playlist
async def create_playlist(user_id, guild_id, name, privacy):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'INSERT INTO playlists (user_id, guild_id, name, privacy, collaborators) VALUES (%s, %s, %s, %s, %s)',
                (user_id, guild_id, name, privacy, '[]'))
            await conn.commit()


# Get playlist details by name (used for editing a playlist)
async def get_playlist_by_name(name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT * FROM playlists WHERE name = %s', (name,))
            playlist = await cur.fetchone()
            return playlist


# Add a song to a playlist
async def add_song_to_playlist(user_id, name, song_id, song_name, artist, raw_data):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            # Fetch the playlist ID based on the playlist name and user ID
            await cur.execute(
                'SELECT playlist_id, collaborators FROM playlists WHERE name = %s AND (user_id = %s OR FIND_IN_SET(%s, collaborators))',
                (name, user_id, user_id)
            )
            playlist = await cur.fetchone()

            if not playlist:
                return 'Playlist not found'

            playlist_id = playlist[0]  # Ensure playlist_id is correctly obtained

            # Serialize raw_data to JSON string
            raw_data_json = json.dumps(raw_data)

            # Insert the song into the playlist
            await cur.execute(
                'INSERT INTO playlist_songs (playlist_id, song_id, song_name, artist, raw_data) VALUES (%s, %s, %s, %s, %s)',
                (playlist_id, song_id, song_name, artist, raw_data_json)
            )
            await conn.commit()


# Remove a song from a playlist
async def remove_song_from_playlist(user_id, name, song_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT playlist_id, collaborators FROM playlists WHERE name = %s AND (user_id = %s OR FIND_IN_SET(%s, collaborators))',
                (name, user_id, user_id))
            playlist = await cur.fetchone()
            if not playlist:
                return 'Playlist not found'
            playlist_id = playlist[0]
            await cur.execute('DELETE FROM playlist_songs WHERE playlist_id = %s AND song_id = %s',
                              (playlist_id, song_id))
            await conn.commit()


# Dedupe songs in a playlist
async def dedupe_playlist(user_id, name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT playlist_id, collaborators FROM playlists WHERE name = %s AND (user_id = %s OR FIND_IN_SET(%s, collaborators))',
                (name, user_id, user_id))
            playlist = await cur.fetchone()
            if not playlist:
                return 'Playlist not found'
            playlist_id = playlist[0]
            await cur.execute(
                'DELETE ps1 FROM playlist_songs ps1 INNER JOIN playlist_songs ps2 WHERE ps1.playlist_id = %s AND ps1.song_id = ps2.song_id AND ps1.id > ps2.id',
                (playlist_id,))
            await conn.commit()

# View playlist by name
async def view_playlist(name: str):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Fetch playlists with the given name
            await cur.execute(
                'SELECT playlist_id, name, user_id, privacy FROM playlists WHERE name = %s',
                (name,)
            )
            playlists = await cur.fetchall()

            if not playlists:
                return None

            return playlists


# Get playlist contents by playlist ID
async def get_playlist_contents(playlist_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT song_id, song_name, artist, raw_data FROM playlist_songs WHERE playlist_id = %s',
                              (playlist_id,))
            return await cur.fetchall()


# Get playlist details
async def get_playlist(user_id, name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT * FROM playlists WHERE user_id = %s AND name = %s', (user_id, name))
            playlist = await cur.fetchone()
            return playlist


# Invite user to a playlist
async def invite_user_to_playlist(user_id, name, invitee_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            # Ensure the playlist exists
            await cur.execute('''
            SELECT playlist_id, user_id, name FROM playlists
            WHERE user_id = %s AND name = %s
            ''', (user_id, name))
            playlist = await cur.fetchone()
            if not playlist:
                return 'Playlist not found'

            playlist_id = playlist[0]
            creator_id = playlist[1]
            playlist_name = playlist[2]

            # Check if the invitee is already a collaborator
            await cur.execute('''
            SELECT collaborators FROM playlists WHERE playlist_id = %s AND FIND_IN_SET(%s, collaborators)
            ''', (playlist_id, invitee_id))
            collaborator = await cur.fetchone()
            if collaborator:
                return 'User is already a collaborator'

            # Check if the invitee has a pending invite
            await cur.execute('''
            SELECT invite_id FROM playlist_invites WHERE playlist_id = %s AND invitee_id = %s
            ''', (playlist_id, invitee_id))
            invite = await cur.fetchone()
            if invite:
                return 'User already has a pending invite'

            # Add the invite
            await cur.execute('''
            INSERT INTO playlist_invites (playlist_id, invitee_id)
            VALUES (%s, %s)
            ''', (playlist_id, invitee_id))
            await conn.commit()

            return {
                'playlist_name': playlist_name,
                'invitee_id': invitee_id,
                'playlist_id': playlist_id,
                'creator_id': creator_id
            }


# Get user invites
async def get_user_invites(user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('''
            SELECT DISTINCT pi.invite_id, p.name, u.user_id
            FROM playlist_invites pi
            JOIN playlists p ON pi.playlist_id = p.playlist_id
            JOIN users u ON p.user_id = u.user_id
            WHERE pi.invitee_id = %s
            ''', (user_id,))
            invites = await cur.fetchall()
            return invites


# Check if user is playlist creator or collaborator
async def check_playlist_permission(user_id, playlist_name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT playlist_id, collaborators FROM playlists WHERE user_id = %s AND name = %s',
                              (user_id, playlist_name))
            playlist = await cur.fetchone()
            if playlist:
                return True
            await cur.execute('SELECT playlist_id FROM playlists WHERE name = %s AND FIND_IN_SET(%s, collaborators)',
                              (playlist_name, user_id))
            collaborator_playlist = await cur.fetchone()
            if collaborator_playlist:
                return True
            return False


# Add collaborator to a playlist
async def add_collaborator_to_playlist(playlist_id, user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT collaborators FROM playlists WHERE playlist_id = %s', (playlist_id,))
            result = await cur.fetchone()
            if result:
                collaborators = result[0]
                if collaborators:
                    collaborators_list = collaborators.split(',')
                else:
                    collaborators_list = []
                if str(user_id) not in collaborators_list:
                    collaborators_list.append(str(user_id))
                    new_collaborators = ','.join(collaborators_list)
                    await cur.execute('UPDATE playlists SET collaborators = %s WHERE playlist_id = %s',
                                      (new_collaborators, playlist_id))
                    await cur.execute('DELETE FROM playlist_invites WHERE playlist_id = %s AND invitee_id = %s',
                                      (playlist_id, user_id))
                    await conn.commit()


# Get playlists where the user is a collaborator
async def get_collaborator_playlists(user_id: int):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            # Find playlists where the user is listed as a collaborator
            await cur.execute("SELECT * FROM playlists WHERE FIND_IN_SET(%s, collaborators)", (user_id,))
            playlists = await cur.fetchall()
            return playlists


# Update playlist privacy
async def update_playlist_privacy(playlist_id, privacy):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE playlists SET privacy = %s WHERE playlist_id = %s', (privacy, playlist_id))
            await conn.commit()


# Remove collaborator from playlist
async def remove_collaborator_from_playlist(playlist_id, user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT collaborators FROM playlists WHERE playlist_id = %s', (playlist_id,))
            result = await cur.fetchone()
            if result:
                collaborators = result[0]
                if collaborators:
                    collaborators_list = collaborators.split(',')
                    if str(user_id) in collaborators_list:
                        collaborators_list.remove(str(user_id))
                        new_collaborators = ','.join(collaborators_list)
                        await cur.execute('UPDATE playlists SET collaborators = %s WHERE playlist_id = %s',
                                          (new_collaborators, playlist_id))
                        await conn.commit()


# Get playlist collaborators
async def get_playlist_collaborators(playlist_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT collaborators FROM playlists WHERE playlist_id = %s', (playlist_id,))
            result = await cur.fetchone()
            if result:
                collaborators = result[0]
                if collaborators:
                    return collaborators.split(',')
                else:
                    return []
            return []


# Edit playlist name
async def edit_playlist_name(playlist_id, new_name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE playlists SET name = %s WHERE playlist_id = %s', (new_name, playlist_id))
            await conn.commit()


# Accept playlist invite
async def accept_playlist_invite(invite_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT playlist_id, invitee_id FROM playlist_invites WHERE invite_id = %s', (invite_id,))
            invite = await cur.fetchone()
            if not invite:
                return 'Invite not found'
            playlist_id, invitee_id = invite
            await add_collaborator_to_playlist(playlist_id, invitee_id)
            await cur.execute('DELETE FROM playlist_invites WHERE invite_id = %s', (invite_id,))
            await conn.commit()


# Decline playlist invite
async def decline_playlist_invite(invite_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('DELETE FROM playlist_invites WHERE invite_id = %s', (invite_id,))
            await conn.commit()


# Function to check if a user is already a collaborator or has a pending invite
async def is_collaborator(user_id, playlist_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                'SELECT p.playlist_id FROM playlists p LEFT JOIN playlist_invites pi ON p.playlist_id = pi.playlist_id AND pi.invitee_id = %s WHERE p.playlist_id = %s AND (p.collaborators LIKE %s OR pi.invitee_id IS NOT NULL)',
                (user_id, playlist_id, f'%{user_id}%'))
            result = await cur.fetchone()
            return result is not None


# Delete a playlist
async def delete_playlist(user_id, name, playlist_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            # Ensure the playlist exists and the user is the owner
            await cur.execute('''
            SELECT playlist_id FROM playlists
            WHERE playlist_id = %s AND user_id = %s
            ''', (playlist_id, user_id))
            playlist = await cur.fetchone()
            if not playlist:
                return 'Playlist not found'

            # Delete invites related to the playlist
            await cur.execute('''
            DELETE FROM playlist_invites WHERE playlist_id = %s
            ''', (playlist_id,))

            # Delete songs from the playlist
            await cur.execute('''
            DELETE FROM playlist_songs WHERE playlist_id = %s
            ''', (playlist_id,))

            # Delete the playlist itself
            await cur.execute('''
            DELETE FROM playlists WHERE playlist_id = %s AND user_id = %s
            ''', (playlist_id, user_id))
            await conn.commit()

            return 'Playlist deleted'


# Get user playlists
async def get_user_playlists(user_id: int):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT name FROM playlists WHERE user_id = %s", (user_id,))
            playlists = await cur.fetchall()
            return playlists


async def get_user_playlist_by_name(user_id, name):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute('SELECT * FROM playlists WHERE user_id = %s AND name = %s', (user_id, name))
            return await cur.fetchone()


# Get all playlists in a guild
async def get_guild_playlists(guild_id: int):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM playlists WHERE guild_id = %s", (guild_id,))
            playlists = await cur.fetchall()
            return playlists
