import os
import discord
from discord.ext import commands

TOKEN = os.getenv("TOKEN")
GUILD_ID = 1414144666651197473

intents = discord.Intents.default()
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

if TOKEN is None:
    raise ValueError("TOKEN environment variable is missing.")

bot.run(TOKEN)
