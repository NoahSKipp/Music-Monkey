import random
import discord
import google.generativeai as genai
from utils.embeds import create_basic_embed, create_error_embed
from utils.voting_checks import has_voted
from utils.interaction_checks import restriction_check
from utils.logging import get_logger
import config

# Configure the API key for Google Gemini
genai.configure(api_key=config.GEMINI)

logger = get_logger(__name__)

class MonkeyService:
    def __init__(self, bot):
        self.bot = bot

    async def get_monkey_image(self, interaction: discord.Interaction):
        # Perform the restriction check
        if not await restriction_check(interaction):
            return

        # Check if the user has voted
        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        try:
            width = 500
            height = 350
            random_value = random.randint(1, 1000)  # Generate a random value between 1 and 1000
            url = f"https://placemonkeys.com/{width}/{height}?random={random_value}"

            embed = create_basic_embed(
                "Here's a random monkey picture for you! 🐒",
                ""
            )
            embed.set_image(url=url)
            await interaction.followup.send(embed=embed, ephemeral=False)
        except Exception as e:
            logger.error(f"Error generating monkey image: {e}")
            embed = create_error_embed(
                "Failed to retrieve a monkey image. Please try again later."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            raise e

    async def get_monkey_fact(self, interaction: discord.Interaction):
        # Perform the restriction check
        if not await restriction_check(interaction):
            return

        # Check if the user has voted
        if not await has_voted(interaction.user, interaction.guild, self.bot, interaction):
            return

        try:
            prompt = "Tell me a random fact about monkeys."

            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            ]

            model = genai.GenerativeModel(model_name="gemini-1.0-pro", safety_settings=safety_settings)
            convo = model.start_chat(history=[])
            convo.send_message(prompt)
            response = convo.last.text

            embed = create_basic_embed(
                "Monkey Fact 🐒",
                response
            )
            await interaction.followup.send(embed=embed, ephemeral=False)
        except Exception as e:
            logger.error(f"Error generating monkey fact: {e}")
            embed = create_error_embed(
                "Failed to retrieve monkey fact. Please try again later."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            raise e
