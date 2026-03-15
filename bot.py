import discord
from discord.ext import commands
import os

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the server pulse ⚡"
        )
    )

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
    await interaction.response.defer()
    await interaction.followup.send(f"Hey {interaction.user.mention} ⚡")

@bot.tree.command(name="avatar", description="Get a user's avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    member = member or interaction.user
    await interaction.followup.send(member.display_avatar.url)

@bot.tree.command(name="help", description="Show Pulse commands")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Pulse Commands",
        description="Here are my current commands:",
        color=0xFFD43B
    )

    embed.add_field(name="/ping", value="Check bot latency", inline=False)
    embed.add_field(name="/hello", value="Say hello", inline=False)
    embed.add_field(name="/avatar", value="Show a user's avatar", inline=False)
    embed.add_field(name="/userinfo", value="Show info about a user", inline=False)
    embed.add_field(name="/serverinfo", value="Show info about the server", inline=False)
    embed.add_field(name="/say", value="Make Pulse send a message", inline=False)
    embed.add_field(name="/poll", value="Create a yes/no poll", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="Show info about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user

    embed = discord.Embed(
        title="👤 User Info",
        color=0xFFD43B
    )

    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=str(member), inline=False)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown", inline=False)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Show info about the server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    embed = discord.Embed(
        title="🌐 Server Info",
        color=0xFFD43B
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Server Name", value=guild.name, inline=False)
    embed.add_field(name="Members", value=guild.member_count, inline=False)
    embed.add_field(name="Owner", value=str(guild.owner), inline=False)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="say", description="Make Pulse say something")
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)

@bot.tree.command(name="poll", description="Create a yes/no poll")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(
        title="📊 Poll",
        description=question,
        color=0xFFD43B
    )
    embed.set_footer(text=f"Poll by {interaction.user}")

    await interaction.response.send_message(embed=embed)
    msg = await interaction.original_response()
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    try:
        await interaction.response.send_message(f"Hey {interaction.user.mention} ⚡")
    except Exception as e:
        print(f"hello error: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("Something broke 😭", ephemeral=True)
        else:
            await interaction.followup.send("Something broke 😭", ephemeral=True)

bot.run(os.getenv("TOKEN"))
