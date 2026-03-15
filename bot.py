import discord
from discord.ext import commands
import os
import random
import asyncio
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

start_time = datetime.now(timezone.utc)

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
    await interaction.response.send_message(f"Hey {interaction.user.mention} ⚡")
@bot.tree.command(name="avatar", description="Get a user's avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    await interaction.response.defer()

    member = member or interaction.user
    await interaction.followup.send(member.display_avatar.url)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Utility", style=discord.ButtonStyle.primary, emoji="⚡")
    async def utility_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚡ Pulse Utility Commands",
            description="Useful server and profile commands.",
            color=0xFFD43B
        )
        embed.add_field(name="/ping", value="Check Pulse latency", inline=False)
        embed.add_field(name="/hello", value="Say hello", inline=False)
        embed.add_field(name="/avatar", value="Show a user's avatar", inline=False)
        embed.add_field(name="/userinfo", value="Show info about a user", inline=False)
        embed.add_field(name="/serverinfo", value="Show info about the server", inline=False)
        embed.add_field(name="/say", value="Make Pulse send a message", inline=False)
        embed.add_field(name="/poll", value="Create a yes/no poll", inline=False)
        embed.add_field(name="/uptime", value="Show how long Pulse has been online", inline=False)
        embed.add_field(name="/botinfo", value="Show info about Pulse", inline=False)
        embed.add_field(name="/8ball", value="Ask the magic 8-ball a question", inline=False)
        embed.add_field(name="/embed", value="Send a simple embed", inline=False)
        embed.add_field(name="/remind", value="Set a reminder", inline=False)
        embed.add_field(name="/suggest", value="Post a suggestion", inline=False)
        embed.add_field(name="/coinflip", value="Flip a coin", inline=False)
        embed.add_field(name="/choose", value="Choose between options", inline=False)
        embed.add_field(name="/rate", value="Rate something out of 10", inline=False)


        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Fun", style=discord.ButtonStyle.success, emoji="🎉")
    async def fun_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎉 Pulse Fun Commands",
            description="Fun commands for your server.",
            color=0xFFD43B
        )
        embed.add_field(name="/8ball", value="Ask the magic 8-ball a question", inline=False)
        embed.add_field(name="/coinflip", value="Flip a coin", inline=False)
        embed.add_field(name="/meme", value="Get a random meme", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Mod", style=discord.ButtonStyle.danger, emoji="🛡️")
    async def mod_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ Pulse Moderation Commands",
            description="Moderation tools.",
            color=0xFFD43B
        )
        embed.add_field(name="/clear", value="Delete messages", inline=False)
        embed.add_field(name="/timeout", value="Timeout a member", inline=False)
        embed.add_field(name="/kick", value="Kick a member", inline=False)
        embed.add_field(name="/ban", value="Ban a member", inline=False)

        await interaction.response.edit_message(embed=embed, view=self)


@bot.tree.command(name="help", description="Show Pulse help menu")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Pulse Help Menu",
        description="Use the buttons below to view command categories.",
        color=0xFFD43B
    )
    embed.add_field(name="Utility", value="Profiles, server tools, and general commands", inline=False)
    embed.add_field(name="Fun", value="Games and silly commands", inline=False)
    embed.add_field(name="Mod", value="Moderation tools", inline=False)
    embed.set_footer(text="Pulse • modern server utility")

    await interaction.response.send_message(embed=embed, view=HelpView())

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

@bot.tree.command(name="uptime", description="Show how long Pulse has been online")
async def uptime(interaction: discord.Interaction):
    now = datetime.now(timezone.utc)
    delta = now - start_time

    days = delta.days
    hours, remainder = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    embed = discord.Embed(
        title="⚡ Pulse Uptime",
        color=0xFFD43B
    )
    embed.add_field(
        name="Online For",
        value=f"{days}d {hours}h {minutes}m {seconds}s",
        inline=False
    )
    embed.add_field(
        name="Latency",
        value=f"{round(bot.latency * 1000)}ms",
        inline=False
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="botinfo", description="Show info about Pulse")
async def botinfo(interaction: discord.Interaction):
    guild_count = len(bot.guilds)
    command_count = len(bot.tree.get_commands())

    embed = discord.Embed(
        title="🤖 Pulse Bot Info",
        description="Modern server utility bot.",
        color=0xFFD43B
    )
    embed.add_field(name="Name", value=str(bot.user), inline=False)
    embed.add_field(name="Servers", value=guild_count, inline=False)
    embed.add_field(name="Commands", value=command_count, inline=False)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=False)

    if bot.user and bot.user.display_avatar:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question")
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        "Yes.",
        "No.",
        "Definitely.",
        "Absolutely not.",
        "Maybe.",
        "Probably.",
        "Ask again later.",
        "It is certain.",
        "Very doubtful.",
        "Without a doubt."
    ]

    embed = discord.Embed(
        title="🎱 Magic 8-Ball",
        color=0xFFD43B
    )
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="embed", description="Send a simple embed")
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=0xFFD43B
    )
    embed.set_footer(text=f"Requested by {interaction.user}")

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="remind", description="Set a reminder in minutes")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    if minutes <= 0:
        await interaction.response.send_message("Minutes must be more than 0.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"⏰ Okay {interaction.user.mention}, I’ll remind you in {minutes} minute(s).",
        ephemeral=True
    )

    await asyncio.sleep(minutes * 60)

    try:
        await interaction.followup.send(
            f"⏰ Reminder for {interaction.user.mention}: {reminder}"
        )
    except Exception as e:
        print(f"remind error: {e}")

@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])

    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"The coin landed on **{result}**!",
        color=0xFFD43B
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="choose", description="Choose between options separated by commas")
async def choose(interaction: discord.Interaction, options: str):
    split_options = [option.strip() for option in options.split(",") if option.strip()]

    if len(split_options) < 2:
        await interaction.response.send_message(
            "Give me at least 2 options separated by commas.",
            ephemeral=True
        )
        return

    choice = random.choice(split_options)

    embed = discord.Embed(
        title="🤔 Choice Picker",
        description=f"I choose: **{choice}**",
        color=0xFFD43B
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rate", description="Rate something out of 10")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(1, 10)

    embed = discord.Embed(
        title="⭐ Rating",
        description=f"**{thing}** gets a **{score}/10**",
        color=0xFFD43B
    )

    await interaction.response.send_message(embed=embed)
SUGGESTION_CHANNEL_ID = 123456789012345678

@bot.tree.command(name="suggest", description="Send a suggestion")
async def suggest(interaction: discord.Interaction, suggestion: str):

    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=0xFFD43B
    )

    embed.set_footer(text=f"Suggested by {interaction.user}")

    message = await channel.send(embed=embed)
    await message.add_reaction("⬆️")
    await message.add_reaction("⬇️")

    await interaction.response.send_message(
        "Your suggestion has been submitted!",
        ephemeral=True
    )
  

bot.run(os.getenv("TOKEN"))
