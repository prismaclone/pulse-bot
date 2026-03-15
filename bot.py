import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Pulse is online as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Sync error: {e}")

@bot.tree.command(name="ping", description="Check if Pulse is alive")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"⚡ Pulse latency: {latency}ms")

@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hey {interaction.user.mention} ⚡")

@bot.tree.command(name="avatar", description="Get a user's avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    await interaction.response.send_message(member.display_avatar.url)

