import aiomysql

MYSQL_CONFIG = {
    'host': 'mysql.db.bot-hosting.net',
    'port': 3306,
    'user': 'u68136_arhT5YVMs1',
    'password': '=OxP4plpddEllbs=Ekzh=yS@',
    'db': 's68136_MusicProfiles',
    'autocommit': True
}


# Creates tables for the MySQL DB.
async def setup_database():
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('''
            CREATE TABLE IF NOT EXISTS guilds (
                guild_id BIGINT PRIMARY KEY NOT NULL,
                dj_only_enabled BOOLEAN DEFAULT 0,
                dj_role_id BIGINT
            );
            CREATE TABLE IF NOT EXISTS songs (
                song_id BIGINT PRIMARY KEY NOT NULL,
                name VARCHAR(255) NOT NULL,
                artist VARCHAR(255) NOT NULL,
                length INT(255) NOT NULL
            );
            CREATE TABLE IF NOT EXISTS plays (
                user_id BIGINT PRIMARY KEY NOT NULL,
                song_id BIGINT FOREIGN KEY NOT NULL,
                guild_id BIGINT FOREIGN KEY NOT NULL,
                count INT
            );
            ''')
            await conn.commit()


async def fetch_all_guild_settings():
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT guild_id, dj_only_commands, dj_role_id FROM guild_settings")
            rows = await cur.fetchall()
            return {row['guild_id']: {'dj_only_commands': bool(row['dj_only_commands']), 'dj_role_id': row['dj_role_id']} for row in rows}

async def get_dj_only_commands(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_only_commands FROM guild_settings WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            if result is None:
                await cur.execute('INSERT INTO guild_settings (guild_id, dj_only_commands) VALUES (%s, %s)', (guild_id, False))
                await conn.commit()
                return False
            return bool(result[0])

async def set_dj_only_commands(guild_id, dj_only):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('REPLACE INTO guild_settings (guild_id, dj_only_commands) VALUES (%s, %s)', (guild_id, dj_only))
            await conn.commit()

async def set_dj_role(guild_id, role_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('REPLACE INTO guild_settings (guild_id, dj_role_id) VALUES (%s, %s)', (guild_id, role_id))
            await conn.commit()

async def get_dj_role(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT dj_role_id FROM guild_settings WHERE guild_id = %s', (guild_id,))
            result = await cur.fetchone()
            return result[0] if result else None

async def increment_song_play(guild_id, user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT plays_count FROM song_plays WHERE guild_id = %s AND user_id = %s', (guild_id, user_id))
            result = await cur.fetchone()
            if result:
                new_count = result[0] + 1
                await cur.execute('UPDATE song_plays SET plays_count = %s WHERE guild_id = %s AND user_id = %s', (new_count, guild_id, user_id))
            else:
                await cur.execute('INSERT INTO song_plays (guild_id, user_id, plays_count) VALUES (%s, %s, 1)', (guild_id, user_id))
            await conn.commit()

async def get_leaderboard(guild_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('SELECT user_id, plays_count FROM song_plays WHERE guild_id = %s ORDER BY plays_count DESC', (guild_id,))
            rows = await cur.fetchall()
            return rows

async def update_music_stats(user_id, artist, title, duration):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('''
                INSERT INTO user_music_stats (user_id, total_songs_played, total_duration_millis)
                VALUES (%s, 1, %s)
                ON DUPLICATE KEY UPDATE
                    total_songs_played = total_songs_played + 1,
                    total_duration_millis = total_duration_millis + %s
            ''', (user_id, duration, duration))

            await cur.execute('''
                INSERT INTO artist_counts (user_id, artist, count)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    count = count + 1
            ''', (user_id, artist))

            await cur.execute('''
                INSERT INTO song_counts (user_id, song, count)
                VALUES (%s, %s, 1)
                ON DUPLICATE KEY UPDATE
                    count = count + 1
            ''', (user_id, title))

            await conn.commit()

async def fetch_music_profile(user_id):
    async with aiomysql.connect(**MYSQL_CONFIG) as conn:
        async with conn.cursor() as cur:
            await cur.execute('''
                SELECT total_songs_played, total_duration_millis FROM user_music_stats WHERE user_id = %s
            ''', (user_id,))
            stats = await cur.fetchone()
            if not stats:
                return None

            await cur.execute('''
                SELECT artist FROM artist_counts WHERE user_id = %s ORDER BY count DESC LIMIT 1
            ''', (user_id,))
            top_artist = await cur.fetchone()

            await cur.execute('''
                SELECT song FROM song_counts WHERE user_id = %s ORDER BY count DESC LIMIT 1
            ''', (user_id,))
            top_song = await cur.fetchone()

            total_hours_played = stats[1] / 3600000  # Convert milliseconds to hours
            return {
                'top_artist': top_artist[0] if top_artist else 'No data',
                'top_song': top_song[0] if top_song else 'No data',
                'total_songs_played': stats[0],
                'total_hours_played': total_hours_played
            }
