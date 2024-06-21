# ========================================= #
# Author: Noah S. Kipp                      #
# Collaborator: Samuel Jaden Garcia Munoz   #
# Created on: 25.04.2024                    #
# ========================================= #

import aiomysql
import os
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()

# Define MySQL configuration

MYSQL_CONFIG = {
    'host': 'mysql.db.bot-hosting.net',
    'port': 3306,
    'user': os.getenv('MYSQL_USER'),
    'password': os.getenv('MYSQL_PASSWORD'),
    'db': 's68136_MusicProfiles',
    'autocommit': True
}


# Creates tables for the MySQL DB.
async def setup_database():
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT NOT NULL,
                dj_only_enabled BOOLEAN DEFAULT 0,
                dj_role_id BIGINT,
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
            ''')
            await conn.commit()


# Returns the dj_only_enabled attribute of a given guild.
async def get_dj_only_enabled(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_only_enabled FROM guilds WHERE guild_id = %s', guild_id)
            result = await cur.fetchone()
            return bool(result[0])


# Sets the dj_only_enabled attribute of a given guild.
async def set_dj_only_enabled(guild_id, dj_only):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE guilds SET dj_only_enabled = %s WHERE guild_id = %s', (dj_only, guild_id))
            await conn.commit()


# Gets the DJ role of a given guild.
async def get_dj_role(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_role_id FROM guilds WHERE guild_id = %s', guild_id)
            result = await cur.fetchone()
            return result[0] if result else None


# Sets the given role as the DJ role of a given guild.
async def set_dj_role(guild_id, role_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('UPDATE guilds SET dj_role_id = %s WHERE guild_id = %s', (role_id, guild_id))
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


# Tries to enter a given wonder trade into the wonderTrades table. If the song has already been recommended,
# nothing happens. If the user has already recommended a song, nothing happens.
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
                return ('You\'ve already recommended a song! Wait some time for someone to give it a listen and '
                        'then try again!')


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
                await cur.execute('SELECT s.uri, wt.note FROM songs AS s JOIN wonderTrades AS wt ON wt.song_id = '
                                  's.song_id WHERE wt.user_id != %s ORDER BY RAND() LIMIT 1', (user_id,))
                result = await cur.fetchone()
                if result:
                    return result[0], result[1]
            return '_There are no available wondertrades available at this moment. Try again later!', None


async def delete_wonder_trade(uri):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('DELETE wonderTrades FROM wonderTrades JOIN songs ON wonderTrades.song_id = '
                              'songs.song_id WHERE songs.uri = %s', uri)
            await conn.commit()


# Increments the play count for the given song, for the given user, in the given guild.
async def increment_plays(user_id, song_id, guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            # Search for an entry for the given song, user and guild.
            await cur.execute('SELECT count FROM plays WHERE user_id = %s AND song_id = %s and guild_id = %s',
                              (user_id, song_id, guild_id))
            result = await cur.fetchone()
            # If an entry is found, increment the play count by one.
            if result:
                new_count = result[0] + 1
                await cur.execute('UPDATE plays SET count = %s WHERE user_id = %s AND song_id = %s and guild_id = %s',
                                  (new_count, user_id, song_id, guild_id))
            # Otherwise, create an entry in the table for the given song, user and guild.
            else:
                await cur.execute('INSERT INTO plays (user_id, song_id, guild_id, count) VALUES (%s, %s, %s, 1)',
                                  (user_id, song_id, guild_id))
            await conn.commit()


# Returns the total play counts for each user of the given guild, in said guild.
# In other words, only count of songs played in the given guild.
async def get_leaderboard(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT user_id, SUM(count) AS total_count FROM plays WHERE guild_id = %s GROUP BY '
                              'user_id ORDER BY total_count DESC;', guild_id)
            rows = await cur.fetchall()
            return rows


# Returns the top stats for a given user.
# Total amount of songs played, total playtime of all songs played, top played artist and top played song.
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
                'SELECT SUM(songs.length * plays.count) AS total_played_length FROM plays JOIN songs ON '
                'plays.song_id = songs.song_id WHERE plays.user_id = %s;', (user_id,)
            )
            total_playtime = await cur.fetchone()
            if not total_playtime or total_playtime[0] is None:
                total_playtime = 0
            else:
                total_playtime = total_playtime[0] / 3600000  # Convert milliseconds to hours

            await cur.execute(
                'SELECT songs.artist, SUM(plays.count) AS total_artist_plays FROM plays JOIN songs ON '
                'plays.song_id = songs.song_id WHERE plays.user_id = %s GROUP BY songs.artist ORDER BY '
                'total_artist_plays DESC LIMIT 1;', (user_id,)
            )
            top_artist = await cur.fetchone()
            if not top_artist:
                top_artist = "None"
            else:
                top_artist = top_artist[0]

            await cur.execute(
                'SELECT songs.name, plays.count FROM plays JOIN songs ON plays.song_id = songs.song_id '
                'WHERE plays.user_id = %s ORDER BY plays.count DESC LIMIT 1;', (user_id,)
            )
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
                'INSERT INTO guilds (guild_id, updates_enabled) VALUES (%s, %s) '
                'ON DUPLICATE KEY UPDATE updates_enabled = %s',
                (guild_id, status_value, status_value)
            )
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
                'INSERT INTO guilds (guild_id, updates_channel_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE '
                'updates_channel_id = %s',
                (guild_id, channel_id, channel_id))
            await conn.commit()


# Retrieves the updates channel of a given guild.
async def get_updates_channel(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT updates_channel_id FROM guilds WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            return result[0] if result else None
