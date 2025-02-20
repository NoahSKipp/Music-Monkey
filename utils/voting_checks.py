import discord
import aiohttp
import config
from utils.embeds import create_basic_embed
from datetime import datetime, timedelta
import logging

# Set up logging configuration
logging.basicConfig(level=logging.DEBUG,  # Set to INFO or ERROR in production
                    format='%(asctime)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

# In-memory caches
voting_cache = {}  # Caches Top.gg voting status

# Cache expiration times
VOTING_TTL = timedelta(hours=24)  # Cache voting status for 24 hours

# List of globally exempt user IDs
EXEMPT_USER_IDS = [128663613312466945, 514288378464960513, 338735185900077066]


async def log_api_call(api_name):
    """Log every API call made to track usage."""
    logger.info(f"API call made to: {api_name}")


async def log_cache_status(user_id, is_hit):
    """Log cache hits or misses."""
    if is_hit:
        logger.debug(f"Cache hit for user {user_id}.")
    else:
        logger.debug(f"Cache miss for user {user_id}.")


async def log_rate_limit(response, api_name):
    """Logs rate limit information for API responses."""
    remaining = response.headers.get('X-RateLimit-Remaining', 0)
    reset_time = response.headers.get('X-RateLimit-Reset', 0)
    if remaining == '0':
        reset_timestamp = datetime.utcfromtimestamp(int(reset_time))
        logger.warning(f"Rate limit hit for {api_name}. Reset time: {reset_timestamp}. No further calls can be made until reset.")


async def get_user_with_fallback(bot, user_id):
    """Fetches a user with a fallback to Discord API if not cached and updates the member cache."""
    # Check the centralized member cache
    cached_member = bot.get_cached_member(user_id)
    if cached_member:
        logger.debug(f"User {user_id} found in the member cache.")
        return cached_member

    # Check the global user cache
    user = bot.get_user(user_id)
    if user:
        logger.debug(f"User {user_id} found in bot's global user cache.")
        return user

    # Fallback to Discord API
    try:
        logger.debug(f"User {user_id} not found in cache. Fetching from Discord API...")
        user = await bot.fetch_user(user_id)

        # Attempt to cache the user dynamically if they're a member of any guild
        for guild in bot.guilds:
            member = guild.get_member(user.id) or await guild.fetch_member(user.id)
            if member:
                bot.member_cache[user.id] = member
                logger.debug(f"User {user.id} added to member cache from guild {guild.id}.")
                break  # Stop checking once the user is found in a guild

        return user
    except discord.NotFound:
        logger.warning(f"User {user_id} not found via Discord API.")
    except discord.HTTPException as e:
        logger.error(f"Failed to fetch user {user_id}: {e}")
    return None


async def is_user_exempt(user: discord.User, guild: discord.Guild, bot) -> bool:
    """Checks if the user is exempt from voting checks."""
    # Check if the user is globally exempt
    if user.id in EXEMPT_USER_IDS:
        logger.debug(f"User {user.id} is globally exempt from voting checks.")
        return True

    exempt_guild = bot.get_guild(config.EXEMPT_GUILD_ID)

    # Check if the bot is used in the exempt guild
    if guild.id == config.EXEMPT_GUILD_ID:
        logger.debug(f"Bot is being used in the exempt guild {config.EXEMPT_GUILD_ID}. Bypassing voting checks.")
        return True

    # Check if the user is a member of the exempt guild and has the exempt role
    if exempt_guild:
        exempt_member = exempt_guild.get_member(user.id)  # Try to get the member from the guild cache
        if not exempt_member:
            try:
                exempt_member = await exempt_guild.fetch_member(user.id)  # Fetch from Discord API
            except discord.NotFound:
                logger.warning(f"User {user.id} is not a member of the exempt guild {config.EXEMPT_GUILD_ID}.")
                return False  # User is not in the exempt guild
            except discord.HTTPException as e:
                logger.error(f"Failed to fetch member {user.id} in exempt guild: {e}")
                return False  # Handle API failure gracefully

        # Ensure the fetched object is a Member and check roles
        if isinstance(exempt_member, discord.Member):
            roles = [role.id for role in exempt_member.roles]
            logger.debug(f"Roles for user {user.id} in exempt guild {config.EXEMPT_GUILD_ID}: {roles}")
            if config.EXEMPT_ROLE_ID in roles:
                logger.debug(f"User {user.id} has exempt role {config.EXEMPT_ROLE_ID} in exempt guild {config.EXEMPT_GUILD_ID}. Bypassing voting checks.")
                return True
        else:
            logger.warning(f"Exempt member {user.id} is not a Member object. Type: {type(exempt_member)}. Skipping role check.")

    logger.debug(f"User {user.id} is not exempt.")
    return False


async def check_topgg_vote(user: discord.User, interaction: discord.Interaction, bot, is_source_check=False):
    """Checks if a user has voted on Top.gg, caching only `True` results."""
    logger.debug(f"Checking Top.gg voting status for user {user.id}...")

    # Check cache for `True` values only
    cache_entry = voting_cache.get(user.id)
    if cache_entry:
        time_elapsed = datetime.utcnow() - cache_entry["timestamp"]
        if time_elapsed < VOTING_TTL:
            logger.debug(f"Cache hit for user {user.id}. Voted: True")
            return True

    # No cache or cache expired, call Top.gg API
    logger.debug(f"Cache miss for user {user.id}. Calling Top.gg API...")
    url = f"https://top.gg/api/bots/{config.BOT_ID}/check?userId={user.id}"
    headers = {
        "Authorization": f"Bearer {config.TOPGG_TOKEN}",
        "X-Auth-Key": config.AUTHORIZATION_KEY
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            await log_rate_limit(response, "Top.gg API")
            logger.debug(f"Top.gg response status for user {user.id}: {response.status}")
            if response.status == 200:
                data = await response.json()
                voted = data.get("voted") == 1
                if voted:
                    # Cache only `True` results
                    voting_cache[user.id] = {"voted": True, "timestamp": datetime.utcnow()}
                    logger.debug(f"User {user.id} voted. Cached voting status as True.")
                return voted
            else:
                logger.warning(f"Failed to verify vote status for user {user.id}. Response status: {response.status}")
                error_details = await response.text()
                logger.error(f"Error details: {error_details}")

                embed = create_basic_embed(
                    title="Error",
                    description="Could not verify your voting status. Please try again later.",
                )
                await send_interaction_response(interaction, embed)
                return False


async def send_interaction_response(interaction: discord.Interaction, embed: discord.Embed):
    """Send an interaction response or follow-up."""
    if not interaction.response.is_done():
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.followup.send(embed=embed, ephemeral=True)


async def has_voted(user: discord.User, guild: discord.Guild, bot, interaction: discord.Interaction) -> bool:
    """Checks if a user has voted or is exempt, using the centralized member cache."""
    if await is_user_exempt(user, guild, bot):
        return True

    # Perform the normal voting check if no exemptions apply
    voted = await check_topgg_vote(user, interaction, bot)

    if not voted:
        # Inform the user to vote
        embed = create_basic_embed(
            title="Unlock This Feature!",
            description=(
                "This feature is available to our awesome voters.\n"
                "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk.\n"
                "Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! 🎉"
            )
        )
        await send_interaction_response(interaction, embed)

    return voted


async def has_voted_sources(user: discord.User, guild: discord.Guild, bot, interaction: discord.Interaction) -> bool:
    """Checks if a user has voted for source access or is exempt, using the centralized member cache."""
    if await is_user_exempt(user, guild, bot):
        return True

    # Perform the normal voting check if no exemptions apply
    voted = await check_topgg_vote(user, interaction, bot, is_source_check=True)

    if not voted:
        # Inform the user to vote
        embed = create_basic_embed(
            title="Unlock This Feature!",
            description=(
                "Playing tracks from sources other than Deezer is a special feature just for our awesome voters.\n"
                "Please take a moment to [vote for Music Monkey on Top.gg](https://top.gg/bot/1228071177239531620/vote) to unlock this perk.\n"
                "Server Boosters and active members of [our community](https://discord.gg/6WqKtrXjhn) get to skip this step! 🎉"
            )
        )
        await send_interaction_response(interaction, embed)

    return voted
