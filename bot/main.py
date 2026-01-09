import discord
from discord.ext import commands

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

def load_extensions():
    bot.load_extension("bot.commands.secret_santa")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
