import os
import io
import math
import json
import time
import random
import asyncio
import aiohttp 
from datetime import datetime, timezone, timedelta

import discord
from discord.ext import commands
from discord import app_commands

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")

# Put your IDs here
GUILD_ID = 1414144666651197473
SUGGESTION_CHANNEL_ID = 1482554718147580087

# Optional: channel where ticket transcripts get sent
TRANSCRIPT_CHANNEL_ID = 1482669955702067200

# Ticket settings
SUPPORT_ROLE_NAME = "Full Pulse Access"
TICKET_CATEGORY_NAME = "Tickets"

# LEVELING

XP_FILE = "xp_data.json"

XP_PER_MESSAGE = (5, 15)  # random XP range
XP_COOLDOWN = 15

LEVEL_UP_CHANNEL_ID = 1403833600469762058 

XP_RESET_INTERVAL = "weekly"  # "daily", "weekly", "monthly", or None

LEVEL_ROLES = {

    1: 1404861873496784977,
    5: 1404864179134926928,   # level: role_id
    10: 1404864410496929862,
    15: 1404864473990168657,
    25: 1404864535491248239
}

def load_xp():
    try:
        with open(XP_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_xp(data):
    with open(XP_FILE, "w") as f:
        json.dump(data, f, indent=4)

xp_data = load_xp()

def get_level(xp):
    return int((xp / 100) ** 0.5)

def get_xp_for_level(level):
    return (level ** 2) * 100

async def xp_reset_task():
    await bot.wait_until_ready()

    while True:
        now = datetime.now()

        if XP_RESET_INTERVAL == "daily":
            next_run = now + timedelta(days=1)

        elif XP_RESET_INTERVAL == "weekly":
            next_run = now + timedelta(days=7)

        elif XP_RESET_INTERVAL == "monthly":
            next_run = now + timedelta(days=30)

        else:
            return

        await asyncio.sleep((next_run - now).total_seconds())

        xp_data.clear()
        save_xp(xp_data)

        print("XP reset completed.")
    
# =========================
# INTENTS / BOT SETUP
# =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
start_time = datetime.now(timezone.utc)

warnings_data = {}   # {guild_id: {user_id: count}}
active_reminders = {}  # optional runtime tracker


# =========================
# HELPERS
# =========================
def is_staff(member: discord.Member) -> bool:
    return any(role.name == SUPPORT_ROLE_NAME for role in member.roles)


def format_uptime() -> str:
    delta = datetime.now(timezone.utc) - start_time
    total_seconds = int(delta.total_seconds())

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def get_warning_count(guild_id: int, user_id: int) -> int:
    return warnings_data.get(guild_id, {}).get(user_id, 0)


def add_warning(guild_id: int, user_id: int) -> int:
    guild_warnings = warnings_data.setdefault(guild_id, {})
    guild_warnings[user_id] = guild_warnings.get(user_id, 0) + 1
    return guild_warnings[user_id]


def clear_warning_count(guild_id: int, user_id: int) -> None:
    if guild_id in warnings_data and user_id in warnings_data[guild_id]:
        del warnings_data[guild_id][user_id]


def parse_duration(duration: str) -> int | None:
    """
    Returns seconds.
    Examples:
    10s, 5m, 2h, 1d
    """
    duration = duration.lower().strip()
    if len(duration) < 2:
        return None

    unit = duration[-1]
    value = duration[:-1]

    if not value.isdigit():
        return None

    value = int(value)

    if unit == "s":
        return value
    if unit == "m":
        return value * 60
    if unit == "h":
        return value * 3600
    if unit == "d":
        return value * 86400

    return None


async def send_staff_only_error(interaction: discord.Interaction):
    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.",
            ephemeral=True
        )


def support_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        return is_staff(interaction.user)
    return app_commands.check(predicate)


async def create_transcript(channel: discord.TextChannel) -> str:
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        created = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        clean_content = msg.content if msg.content else ""
        attachment_text = ""

        if msg.attachments:
            attachment_urls = "\n".join([a.url for a in msg.attachments])
            attachment_text = f"\n[Attachments]\n{attachment_urls}"

        messages.append(
            f"[{created}] {msg.author} ({msg.author.id}): {clean_content}{attachment_text}"
        )

    if not messages:
        return "No messages found in this ticket."

    return "\n".join(messages)


# =========================
# TICKET VIEWS
# =========================
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", emoji="🎫", style=discord.ButtonStyle.blurple, custom_id="persistent_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ This can only be used in a server.", ephemeral=True)
            return

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

        # Check if user already has an open ticket
        existing = discord.utils.get(category.text_channels, name=f"ticket-{interaction.user.id}")
        if existing:
            await interaction.response.send_message(
                f"❌ You already have an open ticket: {existing.mention}",
                ephemeral=True
            )
            return

        support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),
            guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                read_message_history=True
            )
        }

        if support_role:
            overwrites[support_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_messages=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{interaction.user.id}",
            category=category,
            overwrites=overwrites,
            topic=f"owner:{interaction.user.id}|claimed:none"
        )

        embed = discord.Embed(
            title="🎫 Support Ticket",
            description=(
                f"Hello {interaction.user.mention}, your ticket has been created.\n\n"
                "A staff member will be with you soon."
            ),
            color=discord.Color.blurple(),
            timestamp=datetime.now(timezone.utc)
        )

        if support_role:
            embed.add_field(
                name="Staff Access",
                value=f"Only users with **{SUPPORT_ROLE_NAME}** can see ticket controls.",
                inline=False
            )

        await channel.send(
            content=f"{interaction.user.mention}" + (f" {support_role.mention}" if support_role else ""),
            embed=embed,
            view=TicketControlView()
        )

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", emoji="🎟️", style=discord.ButtonStyle.green, custom_id="persistent_claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message(
                f"❌ Only **{SUPPORT_ROLE_NAME}** can claim tickets.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ This can only be used in a ticket channel.", ephemeral=True)
            return

        topic = interaction.channel.topic or ""
        if "claimed:" in topic:
            claimed_value = topic.split("claimed:")[1].split("|")[0] if "|" in topic.split("claimed:")[1] else topic.split("claimed:")[1]
            if claimed_value != "none":
                try:
                    claimed_id = int(claimed_value)
                    if claimed_id == interaction.user.id:
                        await interaction.response.send_message("❌ You already claimed this ticket.", ephemeral=True)
                        return
                    else:
                        await interaction.response.send_message("❌ This ticket has already been claimed.", ephemeral=True)
                        return
                except ValueError:
                    pass

        owner_id = None
        if "owner:" in topic:
            try:
                owner_value = topic.split("owner:")[1].split("|")[0]
                owner_id = int(owner_value)
            except Exception:
                owner_id = None

        new_topic = f"owner:{owner_id if owner_id else 'unknown'}|claimed:{interaction.user.id}"
        await interaction.channel.edit(topic=new_topic)

        claim_embed = discord.Embed(
            title="🎟️ Ticket Claimed",
            description=f"{interaction.user.mention} has claimed this ticket and will be assisting you.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )

        await interaction.response.send_message(embed=claim_embed)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="persistent_close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message(
                f"❌ Only **{SUPPORT_ROLE_NAME}** can close tickets.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message("❌ This can only be used in a ticket channel.", ephemeral=True)
            return

        await interaction.response.send_message("📝 Closing ticket and generating transcript...")

        transcript_text = await create_transcript(interaction.channel)

        transcript_channel = interaction.guild.get_channel(TRANSCRIPT_CHANNEL_ID) if TRANSCRIPT_CHANNEL_ID else None
        if transcript_channel and isinstance(transcript_channel, discord.TextChannel):
            file_data = io.BytesIO(transcript_text.encode("utf-8"))
            transcript_file = discord.File(file_data, filename=f"{interaction.channel.name}-transcript.txt")

            embed = discord.Embed(
                title="📄 Ticket Transcript",
                description=f"Transcript from {interaction.channel.mention}",
                color=discord.Color.orange(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)

            await transcript_channel.send(embed=embed, file=transcript_file)

        await asyncio.sleep(2)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


# =========================
# EVENTS
# =========================
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    user_id = str(message.author.id)

    if user_id not in xp_data:
        xp_data[user_id] = {"xp": 0, "last": 0}

    now = time.time()

    if now - xp_data[user_id]["last"] < XP_COOLDOWN:
        await bot.process_commands(message)
        return

    xp_gain = random.randint(*XP_PER_MESSAGE)
    xp_data[user_id]["xp"] += xp_gain
    xp_data[user_id]["last"] = now

    old_level = get_level(xp_data[user_id]["xp"] - xp_gain)
    new_level = get_level(xp_data[user_id]["xp"])

    if new_level > old_level:
        # 🎉 level up message
        channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        if channel:
            await channel.send(f"🎉 {message.author.mention} leveled up to **Level {new_level}**!")

        # 🎭 role rewards
        if new_level in LEVEL_ROLES:
            role = message.guild.get_role(LEVEL_ROLES[new_level])
            if role:
                await message.author.add_roles(role)

    save_xp(xp_data)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the server pulse ⚡"
        )
    )

    print(f"Pulse is online as {bot.user}")

    try:
        guild_obj = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Synced {len(synced)} guild command(s) to {GUILD_ID}")
    except Exception as e:
        print(f"Guild sync error: {e}")

    try:
        global_synced = await bot.tree.sync()
        print(f"Synced {len(global_synced)} global command(s)")
    except Exception as e:
        print(f"Global sync error: {e}")

    # 🔥 ADD THIS RIGHT HERE
    bot.loop.create_task(xp_reset_task())

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CheckFailure):
        await send_staff_only_error(interaction)
        return

    if not interaction.response.is_done():
        await interaction.response.send_message(
            f"❌ Something went wrong:\n`{error}`",
            ephemeral=True
        )
    else:
        await interaction.followup.send(
            f"❌ Something went wrong:\n`{error}`",
            ephemeral=True
        )


# =========================
# BASIC COMMANDS
# =========================
@bot.tree.command(name="rank", description="Check your level and XP")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user
    user_id = str(target.id)

    if user_id not in xp_data:
        await interaction.response.send_message("No data yet.", ephemeral=True)
        return

    xp = xp_data[user_id]["xp"]
    level = get_level(xp)
    next_xp = get_xp_for_level(level + 1)

    await interaction.response.send_message(
        f"📊 {target.mention}\nLevel: **{level}**\nXP: **{xp}/{next_xp}**"
    )

@bot.tree.command(name="leaderboard", description="Top XP users")
async def leaderboard(interaction: discord.Interaction):
    sorted_users = sorted(xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]

    desc = ""
    for i, (user_id, data) in enumerate(sorted_users, 1):
        user = await bot.fetch_user(int(user_id))
        desc += f"**{i}.** {user.name} — {data['xp']} XP\n"

    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=desc or "No data yet.",
        color=discord.Color.gold()
    )

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="ping", description="Check if Pulse is alive")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"⚡ Pulse latency: **{latency}ms**")


@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"hey {interaction.user.mention} 👋")


@bot.tree.command(name="uptime", description="Show how long Pulse has been online")
async def uptime(interaction: discord.Interaction):
    await interaction.response.send_message(f"⏳ Pulse uptime: **{format_uptime()}**")


@bot.tree.command(name="botinfo", description="Show information about Pulse")
async def botinfo(interaction: discord.Interaction):
    guild_count = len(bot.guilds)
    user_count = sum(g.member_count or 0 for g in bot.guilds)

    embed = discord.Embed(
        title="⚡ Pulse Bot Info",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="Servers", value=str(guild_count))
    embed.add_field(name="Users", value=str(user_count))
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms")
    embed.add_field(name="Uptime", value=format_uptime(), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="Show Pulse commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📘 Pulse Commands",
        description="Here are the current commands for Pulse.",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="General",
        value=(
            "`/ping` `/hello` `/uptime` `/botinfo` `/help`\n"
            "`/avatar` `/serverinfo` `/userinfo`"
        ),
        inline=False
    )

    embed.add_field(
        name="Fun",
        value=(
            "`/8ball` `/coinflip` `/choose` `/rate`"
        ),
        inline=False
    )

    embed.add_field(
        name="Community",
        value=(
            "`/suggest` `/remind`"
        ),
        inline=False
    )

    embed.add_field(
        name="Tickets",
        value=(
            "`/ticketpanel` `/adduser` `/removeuser` `/rename`"
        ),
        inline=False
    )

    embed.add_field(
        name="Staff Only",
        value=(
            "`/say` `/embed` `/lock` `/unlock` `/unlockall`\n"
            "`/purge` `/warn` `/warnings` `/clearwarnings`"
        ),
        inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


# =========================
# UTILITY COMMANDS
# =========================
@bot.tree.command(name="calc", description="Calculate a math expression")
@app_commands.describe(expression="Example: 5+5*2")
async def calc(interaction: discord.Interaction, expression: str):
    try:
        result = eval(expression, {"__builtins__": {}})
        await interaction.response.send_message(f"🧮 Result: **{result}**")
    except:
        await interaction.response.send_message("❌ Invalid expression.", ephemeral=True)

@bot.tree.command(name="avatar", description="Show a user's avatar")
@app_commands.describe(user="The user to view")
async def avatar(interaction: discord.Interaction, user: discord.Member | None = None):
    user = user or interaction.user

    embed = discord.Embed(
        title=f"🖼️ {user.display_name}'s Avatar",
        color=discord.Color.blurple()
    )
    embed.set_image(url=user.display_avatar.url)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show info about a user")
@app_commands.describe(user="The user to view")
async def userinfo(interaction: discord.Interaction, user: discord.Member | None = None):
    user = user or interaction.user

    embed = discord.Embed(
        title=f"👤 User Info - {user}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=str(user.id), inline=False)
    embed.add_field(name="Display Name", value=user.display_name, inline=True)
    embed.add_field(name="Joined Server", value=user.joined_at.strftime("%Y-%m-%d %H:%M UTC") if user.joined_at else "Unknown", inline=False)
    embed.add_field(name="Created Account", value=user.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)
    embed.add_field(name="Top Role", value=user.top_role.mention if user.top_role else "None", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Show server information")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("❌ This command only works in a server.", ephemeral=True)
        return

    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)

    embed = discord.Embed(
        title=f"🛠️ Server Info - {guild.name}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Owner", value=str(guild.owner), inline=False)
    embed.add_field(name="Members", value=str(guild.member_count), inline=True)
    embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
    embed.add_field(name="Text Channels", value=str(text_channels), inline=True)
    embed.add_field(name="Voice Channels", value=str(voice_channels), inline=True)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)

    await interaction.response.send_message(embed=embed)


# =========================
# FUN COMMANDS
# =========================
@bot.tree.command(name="dadjoke", description="Get a dad joke")
async def dadjoke(interaction: discord.Interaction):
    jokes = [
        "I only know 25 letters of the alphabet… I don’t know y.",
        "Why did the scarecrow win an award? Because he was outstanding in his field.",
        "I told my computer I needed a break… it said no problem — it froze.",
        "Why don’t skeletons fight each other? They don’t have the guts.",
        "I’m reading a book about anti-gravity… it’s impossible to put down."
    ]

    await interaction.response.send_message(random.choice(jokes))

@bot.tree.command(name="clown", description="Call someone a clown 🤡")
@app_commands.describe(user="The clown")
async def clown(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(f"{user.mention} certified clown 🤡")

@bot.tree.command(name="ship", description="Ship two users together")
@app_commands.describe(user1="First user", user2="Second user")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member):
    percentage = random.randint(0, 100)

    if percentage > 80:
        msg = "💖 PERFECT MATCH"
    elif percentage > 50:
        msg = "💕 pretty solid"
    else:
        msg = "💀 yeah... no"

    await interaction.response.send_message(
        f"{user1.mention} ❤️ {user2.mention}\n**{percentage}%** — {msg}"
    )

@bot.tree.command(name="roast", description="Roast someone 💀")
@app_commands.describe(user="The user to roast")
async def roast(interaction: discord.Interaction, user: discord.Member = None):
    target = user or interaction.user

    roasts = [
        f"{target.mention} you have the personality of a loading screen",
        f"{target.mention} you’re not dumb, just... aggressively average",
        f"{target.mention} your brain runs on low battery mode 24/7 🔋",
        f"{target.mention} you make WiFi signals look strong",
        f"{target.mention} you’re like a software bug… nobody knows how you got here",
        f"{target.mention} you’d lose a staring contest with a wall",
        f"{target.mention} you have the confidence of someone who’s never been correct",
        f"{target.mention} you’re the human version of a typo",
        f"{target.mention} you don’t need a GPS… you’re already lost",
        f"{target.mention} you bring absolutely nothing to the table… not even snacks",
        f"{target.mention} your thoughts take a detour before arriving",
        f"{target.mention} you make silence feel productive",
        f"{target.mention} you’re like a tutorial nobody asked for",
        f"{target.mention} you got the brainpower of a disconnected mouse",
        f"{target.mention} your logic expired years ago",
        f"{target.mention} you’re running on vibes and no updates",
        f"{target.mention} you’re proof that autocorrect gives up sometimes",
        f"{target.mention} you couldn’t pour water out of a boot with instructions",
        f"{target.mention} you’re the reason instructions exist",
        f"{target.mention} you’re not slow… you just take scenic routes mentally",
        f"{target.mention} you’ve got two brain cells and they’re fighting for third place",
        f"{target.mention} you make buffering look fast",
        f"{target.mention} you’re like a broken pencil… pointless",
        f"{target.mention} you bring confusion wherever you go",
        f"{target.mention} your decisions need a patch update",
        f"{target.mention} you’re like a group project member who does nothing",
        f"{target.mention} your thoughts are still in beta testing",
        f"{target.mention} you couldn’t win a race standing still",
        f"{target.mention} you’re like a pop-up ad… unwanted and confusing",
        f"{target.mention} you make lag look smooth",
        f"{target.mention} you’re the reason the mute button exists",
        f"{target.mention} you think outside the box because you lost the instructions",
        f"{target.mention} you’re like expired milk… questionable and unpleasant",
        f"{target.mention} you got the attention span of a goldfish on caffeine",
        f"{target.mention} you’re not clueless… just aggressively uninformed",
        f"{target.mention} you make mistakes look intentional",
        f"{target.mention} your vibe is “I tried nothing and I’m out of ideas”",
        f"{target.mention} you couldn’t find your way out of a straight line",
        f"{target.mention} you’re like a test answer that’s not even one of the options",
        f"{target.mention} you bring chaos without purpose",
        f"{target.mention} you’re the human equivalent of a wrong turn",
        f"{target.mention} you operate on 1% brain capacity and it shows",
        f"{target.mention} you’re like a lag spike in real life",
        f"{target.mention} you couldn’t organize a one-piece puzzle",
        f"{target.mention} you got outsmarted by autocorrect",
        f"{target.mention} your plans have no sequel because they flop immediately",
        f"{target.mention} you make confusion your personality",
        f"{target.mention} you’re like a blank notification… pointless",
        f"{target.mention} you’ve got main character confidence with NPC logic",
        f"{target.mention} you’re like a missed call… nobody needed it",
        f"{target.mention} your ideas come with a warning label",
        f"{target.mention} you couldn’t pass a tutorial level",
        f"{target.mention} you’re like a glitched character stuck in idle",
        f"{target.mention} you got the strategic thinking of a coin flip",
        f"{target.mention} you make simple things complicated professionally",
        f"{target.mention} you’re like background noise… always there, never useful",
        f"{target.mention} you couldn’t solve a problem even if it introduced itself",
        f"{target.mention} you bring zero stats to the team",
        f"{target.mention} you’re like a broken clock… but never right",
        f"{target.mention} you got the energy of a drained battery",
        f"{target.mention} you’re like a tutorial skip… now everything makes less sense",
        f"{target.mention} you couldn’t follow a straight line with directions",
        f"{target.mention} you’re like a typo in a password… completely wrong",
        f"{target.mention} you got lost in your own thought process",
        f"{target.mention} you make basic logic look advanced",
        f"{target.mention} you’re like a silent alarm… completely ineffective",
        f"{target.mention} you couldn’t even fake being smart convincingly",
        f"{target.mention} you’re like a disconnected cable… nothing works",
        f"{target.mention} you got the coordination of a broken joystick",
        f"{target.mention} you make bad ideas look consistent",
        f"{target.mention} you’re like a useless update… nobody asked for it",
        f"{target.mention} you couldn’t outthink a loading bar",
        f"{target.mention} you’re like a skipped cutscene… now nothing makes sense",
        f"{target.mention} you got the reaction time of a frozen screen",
        f"{target.mention} you make confusion look like a skill",
        f"{target.mention} you’re like a blank map marker… leading nowhere",
        f"{target.mention} you couldn’t plan your way out of a menu screen",
        f"{target.mention} you’re like a broken shortcut… does nothing",
        f"{target.mention} you got the problem-solving skills of a coin toss",
        f"{target.mention} you make mistakes your personality trait",
        f"{target.mention} you’re like a dead end… no progress possible",
        f"{target.mention} you couldn’t follow a step-by-step guide",
        f"{target.mention} you’re like an empty file… no content",
        f"{target.mention} you got the logic of a random generator",
        f"{target.mention} you make nonsense look intentional",
        f"{target.mention} you’re like a failed connection… try again later",
        f"{target.mention} you couldn’t even confuse people correctly",
        f"{target.mention} you’re like a broken button… no response",
        f"{target.mention} you got the consistency of a glitch",
        f"{target.mention} you make chaos look organized",
        f"{target.mention} you’re like a lost signal… completely gone",
        f"{target.mention} you couldn’t solve a problem with infinite hints",
        f"{target.mention} you’re like a background error… always there",
        f"{target.mention} you got the timing of a delayed message",
        f"{target.mention} you make wrong decisions confidently",
    ]

    await interaction.response.send_message(random.choice(roasts))

@bot.tree.command(name="meme", description="Get a random meme")
async def meme(interaction: discord.Interaction):
    await interaction.response.defer()  # prevents "application did not respond"

    url = "https://meme-api.com/gimme"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await interaction.followup.send("❌ Failed to fetch a meme. Try again.")
                    return

                data = await resp.json()

        embed = discord.Embed(
            title=data.get("title", "Random Meme"),
            color=discord.Color.blurple()
        )
        embed.set_image(url=data["url"])
        embed.set_footer(text=f"👍 {data.get('ups', 0)} | r/{data.get('subreddit', 'unknown')}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error fetching meme:\n`{e}`")

@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your question")
async def eight_ball(interaction: discord.Interaction, question: str):
    responses = [
        "Yes.",
        "No.",
        "Maybe.",
        "Definitely.",
        "Absolutely not.",
        "Without a doubt.",
        "Very likely.",
        "Probably not.",
        "Ask again later.",
        "The signs point to yes."
    ]
    await interaction.response.send_message(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")


@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    await interaction.response.send_message(f"🪙 The coin landed on **{random.choice(['Heads', 'Tails'])}**!")


@bot.tree.command(name="choose", description="Choose from options separated by commas")
@app_commands.describe(options="Example: pizza, tacos, burgers")
async def choose(interaction: discord.Interaction, options: str):
    choices = [choice.strip() for choice in options.split(",") if choice.strip()]
    if len(choices) < 2:
        await interaction.response.send_message("❌ Give me at least 2 options separated by commas.", ephemeral=True)
        return

    await interaction.response.send_message(f"🤔 I choose: **{random.choice(choices)}**")


@bot.tree.command(name="rate", description="Rate something from 1 to 10")
@app_commands.describe(thing="What should Pulse rate?")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(1, 10)
    await interaction.response.send_message(f"📊 I rate **{thing}** a **{score}/10**")


# =========================
# COMMUNITY COMMANDS
# =========================
@bot.tree.command(name="suggest", description="Send a suggestion")
@app_commands.describe(suggestion="Your suggestion")
async def suggest(interaction: discord.Interaction, suggestion: str):
    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

    if channel is None or not isinstance(channel, discord.TextChannel):
        await interaction.response.send_message(
            "❌ Suggestion channel not found. Check `SUGGESTION_CHANNEL_ID`.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=str(interaction.user), icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"User ID: {interaction.user.id}")

    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    await interaction.response.send_message("✅ Your suggestion has been sent!", ephemeral=True)


@bot.tree.command(name="remind", description="Set a reminder")
@app_commands.describe(time="Example: 10s, 5m, 2h, 1d", reminder="What should I remind you about?")
async def remind(interaction: discord.Interaction, time: str, reminder: str):
    seconds = parse_duration(time)
    if seconds is None:
        await interaction.response.send_message(
            "❌ Invalid time format. Use things like `10s`, `5m`, `2h`, or `1d`.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(
        f"⏰ Okay {interaction.user.mention}, I’ll remind you in **{time}**: {reminder}",
        ephemeral=True
    )

    await asyncio.sleep(seconds)

    try:
        await interaction.user.send(f"⏰ Reminder: **{reminder}**")
    except discord.Forbidden:
        channel_msg = f"{interaction.user.mention} ⏰ Reminder: **{reminder}**"
        if interaction.channel:
            await interaction.channel.send(channel_msg)


# =========================
# STAFF COMMANDS
# =========================
@bot.tree.command(name="xpadd", description="Add XP to a user")
@support_only()
@app_commands.describe(user="The user to give XP to", amount="How much XP to add")
async def xpadd(interaction: discord.Interaction, user: discord.Member, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ XP amount must be greater than 0.", ephemeral=True)
        return

    user_id = str(user.id)

    if user_id not in xp_data:
        xp_data[user_id] = {"xp": 0, "last": 0}

    old_level = get_level(xp_data[user_id]["xp"])
    xp_data[user_id]["xp"] += amount
    new_level = get_level(xp_data[user_id]["xp"])

    save_xp(xp_data)

    msg = f"✅ Added **{amount} XP** to {user.mention}."

    if new_level > old_level:
        msg += f"\n🎉 They leveled up to **Level {new_level}**!"

        if LEVEL_UP_CHANNEL_ID:
            channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
            if channel:
                await channel.send(f"🎉 {user.mention} leveled up to **Level {new_level}**!")

        for level_required, role_id in LEVEL_ROLES.items():
            if old_level < level_required <= new_level:
                role = interaction.guild.get_role(role_id)
                if role:
                    try:
                        await user.add_roles(role, reason="Level reward from xpadd command")
                    except discord.Forbidden:
                        pass

    await interaction.response.send_message(msg)

@bot.tree.command(name="say", description="Make Pulse send a message")
@support_only()
@app_commands.describe(message="The message to send")
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("✅ Sent.", ephemeral=True)
    await interaction.channel.send(message)


@bot.tree.command(name="embed", description="Send an embed message")
@support_only()
@app_commands.describe(title="Embed title", description="Embed description")
async def embed_command(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    await interaction.response.send_message("✅ Embed sent.", ephemeral=True)
    await interaction.channel.send(embed=embed)


@bot.tree.command(name="lock", description="Lock the current channel")
@support_only()
async def lock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in text channels.", ephemeral=True)
        return

    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = False
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

    await interaction.response.send_message("🔒 Channel locked.")


@bot.tree.command(name="unlock", description="Unlock the current channel")
@support_only()
async def unlock(interaction: discord.Interaction):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in text channels.", ephemeral=True)
        return

    overwrite = interaction.channel.overwrites_for(interaction.guild.default_role)
    overwrite.send_messages = True
    await interaction.channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

    await interaction.response.send_message("🔓 Channel unlocked.")


@bot.tree.command(name="unlockall", description="Unlock all text channels")
@support_only()
async def unlockall(interaction: discord.Interaction):
    await interaction.response.defer()

    for channel in interaction.guild.text_channels:
        overwrite = channel.overwrites_for(interaction.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(interaction.guild.default_role, overwrite=overwrite)

    await interaction.followup.send("🔓 All text channels have been unlocked.")


@bot.tree.command(name="purge", description="Delete messages")
@support_only()
@app_commands.describe(amount="How many messages to delete")
async def purge(interaction: discord.Interaction, amount: int):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in text channels.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("❌ Amount must be at least 1.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted **{len(deleted)}** message(s).", ephemeral=True)


@bot.tree.command(name="warn", description="Warn a user")
@support_only()
@app_commands.describe(user="The user to warn", reason="Reason for the warning")
async def warn(interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided"):
    count = add_warning(interaction.guild.id, user.id)

    embed = discord.Embed(
        title="⚠️ User Warned",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Moderator", value=interaction.user.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=str(count), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="warnings", description="Check a user's warnings")
@support_only()
@app_commands.describe(user="The user to check")
async def warnings(interaction: discord.Interaction, user: discord.Member):
    count = get_warning_count(interaction.guild.id, user.id)
    await interaction.response.send_message(
        f"⚠️ {user.mention} has **{count}** warning(s)."
    )


@bot.tree.command(name="clearwarnings", description="Clear a user's warnings")
@support_only()
@app_commands.describe(user="The user to clear warnings for")
async def clearwarnings(interaction: discord.Interaction, user: discord.Member):
    clear_warning_count(interaction.guild.id, user.id)
    await interaction.response.send_message(f"✅ Cleared warnings for {user.mention}.")


# =========================
# TICKET COMMANDS
# =========================
@bot.tree.command(name="ticketpanel", description="Send the ticket panel")
@support_only()
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎫 Support Tickets",
        description="Press the button below to open a ticket.",
        color=discord.Color.blurple()
    )
    await interaction.response.send_message(embed=embed, view=TicketPanelView())


@bot.tree.command(name="adduser", description="Add a user to the current ticket")
@support_only()
@app_commands.describe(user="The user to add")
async def adduser(interaction: discord.Interaction, user: discord.Member):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in ticket channels.", ephemeral=True)
        return

    await interaction.channel.set_permissions(
        user,
        view_channel=True,
        send_messages=True,
        read_message_history=True,
        attach_files=True,
        embed_links=True
    )

    await interaction.response.send_message(f"✅ Added {user.mention} to the ticket.")


@bot.tree.command(name="removeuser", description="Remove a user from the current ticket")
@support_only()
@app_commands.describe(user="The user to remove")
async def removeuser(interaction: discord.Interaction, user: discord.Member):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in ticket channels.", ephemeral=True)
        return

    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from the ticket.")


@bot.tree.command(name="rename", description="Rename the current ticket channel")
@support_only()
@app_commands.describe(name="The new channel name")
async def rename(interaction: discord.Interaction, name: str):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message("❌ This command only works in text channels.", ephemeral=True)
        return

    await interaction.channel.edit(name=name)
    await interaction.response.send_message(f"✅ Channel renamed to **{name}**.")


# =========================
# RUN
# =========================
if TOKEN is None:
    raise ValueError("TOKEN environment variable is missing.")

print("booting pulse...")
bot.run(TOKEN)
