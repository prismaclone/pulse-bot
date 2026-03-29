import os
import io
import json
import time
import random
import asyncio
from datetime import datetime, timezone, timedelta
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands
pressure_enabled = True 

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")

GUILD_ID = 1414144666651197473
SUGGESTION_CHANNEL_ID = 1482554718147580087
TRANSCRIPT_CHANNEL_ID = 1482669955702067200

SUPPORT_ROLE_NAME = "Moderator"
TICKET_CATEGORY_NAME = "Modmail"

XP_FILE = "xp_data.json"
REP_FILE = "rep_data.json"
WARNINGS_FILE = "warnings_data.json"

XP_PER_MESSAGE = (5, 15)
XP_COOLDOWN = 15
REP_COOLDOWN = 86400  # 24 hours

LEVEL_UP_CHANNEL_ID = 1403833600469762058
XP_RESET_INTERVAL = "monthly"  # "daily", "weekly", "monthly", or None

LEVEL_ROLES = {
    1: 1404861873496784977,
    5: 1404864179134926928,
    10: 1404864410496929862,
    15: 1404864473990168657,
    25: 1404864535491248239,
}

# =========================
# JSON HELPERS
# =========================
def load_json(filename: str) -> dict:
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_json(filename: str, data: dict) -> None:
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


xp_data = load_json(XP_FILE)
rep_data = load_json(REP_FILE)
warnings_data = load_json(WARNINGS_FILE)

# =========================
# INTENTS / BOT SETUP
# =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix="p!",
    intents=intents,
    help_command=None
)

start_time = datetime.now(timezone.utc)

# =========================
# DATA HELPERS
# =========================
def ensure_xp_user(user_id: str):
    if user_id not in xp_data:
        xp_data[user_id] = {
            "xp": 0,
            "level": 0,
            "last": 0
        }
        save_json(XP_FILE, xp_data)
    else:
        xp_data[user_id].setdefault("xp", 0)
        xp_data[user_id].setdefault("level", 0)
        xp_data[user_id].setdefault("last", 0)


def ensure_rep_user(user_id: str):
    if user_id not in rep_data:
        rep_data[user_id] = {
            "rep": 0,
            "last_given": 0
        }
        save_json(REP_FILE, rep_data)
    else:
        rep_data[user_id].setdefault("rep", 0)
        rep_data[user_id].setdefault("last_given", 0)


def ensure_warning_bucket(guild_id: int):
    guild_key = str(guild_id)
    if guild_key not in warnings_data:
        warnings_data[guild_key] = {}
        save_json(WARNINGS_FILE, warnings_data)
    return guild_key


def get_warning_count(guild_id: int, user_id: int) -> int:
    guild_key = ensure_warning_bucket(guild_id)
    return warnings_data[guild_key].get(str(user_id), 0)


def add_warning(guild_id: int, user_id: int) -> int:
    guild_key = ensure_warning_bucket(guild_id)
    user_key = str(user_id)
    warnings_data[guild_key][user_key] = warnings_data[guild_key].get(user_key, 0) + 1
    save_json(WARNINGS_FILE, warnings_data)
    return warnings_data[guild_key][user_key]


def clear_warning_count(guild_id: int, user_id: int) -> None:
    guild_key = ensure_warning_bucket(guild_id)
    user_key = str(user_id)
    if user_key in warnings_data[guild_key]:
        del warnings_data[guild_key][user_key]
        save_json(WARNINGS_FILE, warnings_data)

# =========================
# XP HELPERS
# =========================
def get_xp_for_level(level: int) -> int:
    return 100 * (level ** 2)


def get_level_from_xp(xp: int) -> int:
    level = 0
    while xp >= get_xp_for_level(level + 1):
        level += 1
    return level


async def apply_level_roles(member: discord.Member, old_level: int, new_level: int):
    for level_required, role_id in LEVEL_ROLES.items():
        if old_level < level_required <= new_level:
            role = member.guild.get_role(role_id)
            if role:
                try:
                    await member.add_roles(role, reason="Level reward")
                except discord.Forbidden:
                    pass


async def remove_all_level_roles():
    for guild in bot.guilds:
        for member in guild.members:
            roles_to_remove = []
            for role_id in LEVEL_ROLES.values():
                role = guild.get_role(role_id)
                if role and role in member.roles:
                    roles_to_remove.append(role)

            if roles_to_remove:
                try:
                    await member.remove_roles(*roles_to_remove, reason="XP reset")
                except discord.Forbidden:
                    print(f"Couldn't remove XP roles from {member} in {guild.name}")
                except Exception as e:
                    print(f"Error removing XP roles from {member}: {e}")


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

        await remove_all_level_roles()
        xp_data.clear()
        save_json(XP_FILE, xp_data)

        print("XP reset completed.")

# =========================
# GENERAL HELPERS
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


def parse_duration(duration: str) -> int | None:
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


def support_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        if not isinstance(interaction.user, discord.Member):
            return False
        return is_staff(interaction.user)
    return app_commands.check(predicate)


async def send_staff_only_error(interaction: discord.Interaction):
    message = f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command."
    if not interaction.response.is_done():
        await interaction.response.send_message(message, ephemeral=True)
    else:
        await interaction.followup.send(message, ephemeral=True)


async def create_transcript(channel: discord.TextChannel) -> str:
    messages = []
    async for msg in channel.history(limit=None, oldest_first=True):
        created = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC")
        clean_content = msg.content if msg.content else ""
        attachment_text = ""

        if msg.attachments:
            attachment_urls = "\n".join(a.url for a in msg.attachments)
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

    @discord.ui.button(
        label="Open Ticket",
        emoji="🎫",
        style=discord.ButtonStyle.blurple,
        custom_id="persistent_open_ticket"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "❌ This can only be used in a server.",
                ephemeral=True
            )
            return

        category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)
        if category is None:
            category = await guild.create_category(TICKET_CATEGORY_NAME)

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
            ),
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

    @discord.ui.button(
        label="Claim Ticket",
        emoji="🎟️",
        style=discord.ButtonStyle.green,
        custom_id="persistent_claim_ticket"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message(
                f"❌ Only **{SUPPORT_ROLE_NAME}** can claim tickets.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ This can only be used in a ticket channel.",
                ephemeral=True
            )
            return

        topic = interaction.channel.topic or ""
        if "claimed:" in topic:
            claimed_value = topic.split("claimed:")[1].split("|")[0]
            if claimed_value != "none":
                try:
                    claimed_id = int(claimed_value)
                    if claimed_id == interaction.user.id:
                        await interaction.response.send_message(
                            "❌ You already claimed this ticket.",
                            ephemeral=True
                        )
                        return
                    else:
                        await interaction.response.send_message(
                            "❌ This ticket has already been claimed.",
                            ephemeral=True
                        )
                        return
                except ValueError:
                    pass

        owner_id = None
        if "owner:" in topic:
            try:
                owner_id = int(topic.split("owner:")[1].split("|")[0])
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

    @discord.ui.button(
        label="Close Ticket",
        emoji="🔒",
        style=discord.ButtonStyle.red,
        custom_id="persistent_close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not isinstance(interaction.user, discord.Member) or not is_staff(interaction.user):
            await interaction.response.send_message(
                f"❌ Only **{SUPPORT_ROLE_NAME}** can close tickets.",
                ephemeral=True
            )
            return

        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ This can only be used in a ticket channel.",
                ephemeral=True
            )
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
PRESSURE_COOLDOWN = 10
last_pressure = 0
pressure_enabled = True

@bot.event
async def on_message(message):
    ...

@bot.event
async def on_ready():
    print(f"Pulse is online as {bot.user}")

    guild_obj = discord.Object(id=GUILD_ID)

    try:
        synced = await bot.tree.sync(guild=guild_obj)
        print(f"Synced {len(synced)} guild command(s) to {GUILD_ID}")
    except Exception as e:
        print(f"Guild sync error: {e}")

    try:
        global_synced = await bot.tree.sync()
        print(f"Synced {len(global_synced)} global command(s)")
    except Exception as e:
        print(f"Global sync error: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")


@bot.event
async def on_message(message):
    global last_pressure

    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

 

# =========================
# REP SYSTEM
# =========================
@bot.command(name="rep")
async def give_rep(ctx, member: discord.Member):
    if member.bot:
        await ctx.send("🤖 You can't give rep to bots.")
        return

    if member.id == ctx.author.id:
        await ctx.send("💀 You can't rep yourself.")
        return

    giver_id = str(ctx.author.id)
    receiver_id = str(member.id)

    ensure_rep_user(giver_id)
    ensure_rep_user(receiver_id)

    now = time.time()

    if now - rep_data[giver_id]["last_given"] < REP_COOLDOWN:
        remaining = int(REP_COOLDOWN - (now - rep_data[giver_id]["last_given"]))
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        await ctx.send(f"⏳ You can give rep again in **{hours}h {minutes}m**.")
        return

    rep_data[receiver_id]["rep"] += 1
    rep_data[giver_id]["last_given"] = now
    save_json(REP_FILE, rep_data)

    await ctx.send(
        f"⭐ {ctx.author.mention} gave rep to {member.mention}!\n"
        f"🏆 They now have **{rep_data[receiver_id]['rep']} rep**."
    )


@bot.command(name="repcheck")
async def rep_check(ctx, member: discord.Member = None):
    member = member or ctx.author
    user_id = str(member.id)

    ensure_rep_user(user_id)

    await ctx.send(
        f"⭐ {member.mention} has **{rep_data[user_id]['rep']} reputation**."
    )


@bot.command(name="reptop")
async def rep_top(ctx):
    if not rep_data:
        await ctx.send("No rep data yet.")
        return

    sorted_users = sorted(rep_data.items(), key=lambda x: x[1]["rep"], reverse=True)

    leaderboard = ""
    for i, (user_id, data) in enumerate(sorted_users[:10], start=1):
        user = bot.get_user(int(user_id))
        name = user.name if user else "Unknown"
        leaderboard += f"**{i}.** {name} — ⭐ {data['rep']}\n"

    embed = discord.Embed(
        title="🏆 Reputation Leaderboard",
        description=leaderboard,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

# =========================
# BASIC / PROFILE COMMANDS
# =========================
@bot.command()
async def test(ctx):
    await ctx.send("⚡ prefix works!")


@bot.hybrid_command(name="profile", description="Show your full Pulse profile")
async def profile(ctx, user: discord.Member = None):
    target = user or ctx.author
    user_id = str(target.id)

    ensure_xp_user(user_id)
    ensure_rep_user(user_id)

    xp = xp_data[user_id]["xp"]
    level = xp_data[user_id]["level"]
    rep = rep_data[user_id]["rep"]

    current_level_xp = get_xp_for_level(level)
    next_level_xp = get_xp_for_level(level + 1)
    progress = xp - current_level_xp
    needed = next_level_xp - current_level_xp

    embed = discord.Embed(
        title=f"📘 {target.display_name}'s Profile",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="⭐ Level", value=str(level), inline=True)
    embed.add_field(name="⚡ Total XP", value=str(xp), inline=True)
    embed.add_field(name="🏆 Rep", value=str(rep), inline=True)
    embed.add_field(name="📈 Progress", value=f"{progress}/{needed} XP", inline=False)
    embed.set_footer(text=f"Requested by {ctx.author.display_name}")

    await ctx.send(embed=embed)


@bot.hybrid_command(name="rank", description="Check your level and XP")
async def rank(ctx, user: discord.Member = None):
    target = user or ctx.author
    user_id = str(target.id)

    ensure_xp_user(user_id)

    xp = xp_data[user_id]["xp"]
    level = xp_data[user_id]["level"]
    current_level_xp = get_xp_for_level(level)
    next_level_xp = get_xp_for_level(level + 1)

    await ctx.send(
        f"📊 {target.mention}\n"
        f"**Level:** {level}\n"
        f"**Total XP:** {xp}\n"
        f"**Progress:** {xp - current_level_xp}/{next_level_xp - current_level_xp} XP"
    )


@bot.hybrid_command(name="leaderboard", description="Top XP users")
async def leaderboard(ctx):
    sorted_users = sorted(xp_data.items(), key=lambda x: x[1]["xp"], reverse=True)[:10]

    desc = ""
    for i, (user_id, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except Exception:
            name = "Unknown"
        desc += f"**{i}.** {name} — {data['xp']} XP\n"

    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=desc or "No data yet.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)


@bot.hybrid_command(name="ping", description="Check if Pulse is alive")
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"⚡ Pulse latency: **{latency}ms**")


@bot.hybrid_command(name="hello", description="Say hello")
async def hello(ctx):
    await ctx.send(f"hey {ctx.author.mention} 👋")


@bot.hybrid_command(name="uptime", description="Show how long Pulse has been online")
async def uptime(ctx):
    await ctx.send(f"⏳ Pulse uptime: **{format_uptime()}**")


@bot.hybrid_command(name="botinfo", description="Show information about Pulse")
async def botinfo(ctx):
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

    await ctx.send(embed=embed)


@bot.hybrid_command(name="help", description="Show Pulse commands")
async def help_command(ctx):
    embed = discord.Embed(
        title="📘 Pulse Commands",
        description="Here are the current commands for Pulse.",
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="General",
        value=(
            "`/ping` `p!ping`\n"
            "`/hello` `p!hello`\n"
            "`/uptime` `p!uptime`\n"
            "`/botinfo` `p!botinfo`\n"
            "`/help` `p!help`\n"
            "`/profile` `p!profile`\n"
            "`/rank` `p!rank`\n"
            "`/leaderboard` `p!leaderboard`\n"
            "`/avatar` `p!avatar`\n"
            "`/serverinfo` `p!serverinfo`\n"
            "`/userinfo` `p!userinfo`\n"
            "`/membercount` `p!membercount`\n"
            "`/banner` `p!banner`\n"
            "`/roleinfo` `p!roleinfo`"
        ),
        inline=False
    )

    embed.add_field(
        name="Fun",
        value=(
            "`/dadjoke` `p!dadjoke`\n"
            "`/clown` `p!clown`\n"
            "`/ship` `p!ship`\n"
            "`/roast` `p!roast`\n"
            "`/meme` `p!meme`\n"
            "`/8ball` `p!8ball`\n"
            "`/coinflip` `p!coinflip`\n"
            "`/choose` `p!choose`\n"
            "`/rate` `p!rate`"
        ),
        inline=False
    )

    embed.add_field(
        name="Community",
        value=(
            "`p!rep` `p!repcheck` `p!reptop`\n"
            "`/suggest` `p!suggest`\n"
            "`/remind` `p!remind`"
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
            "`/xpreset` `/xpadd` `/removexp`\n"
            "`/say` `/embed` `/lock` `/unlock` `/unlockall`\n"
            "`/purge` `/warn` `/warnings` `/clearwarnings`"
        ),
        inline=False
    )

    await ctx.send(embed=embed)

# =========================
# UTILITY COMMANDS
# =========================
@bot.hybrid_command(name="calc", description="Calculate a math expression")
async def calc(ctx, *, expression: str):
    try:
        result = eval(expression, {"__builtins__": {}})
        await ctx.send(f"🧮 Result: **{result}**")
    except Exception:
        await ctx.send("❌ Invalid expression.")


@bot.hybrid_command(name="avatar", description="Show a user's avatar")
async def avatar(ctx, user: discord.Member = None):
    user = user or ctx.author

    embed = discord.Embed(
        title=f"🖼️ {user.display_name}'s Avatar",
        color=discord.Color.blurple()
    )
    embed.set_image(url=user.display_avatar.url)

    await ctx.send(embed=embed)


@bot.hybrid_command(name="userinfo", description="Show info about a user")
async def userinfo(ctx, user: discord.Member = None):
    user = user or ctx.author

    embed = discord.Embed(
        title=f"👤 User Info - {user}",
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.add_field(name="ID", value=str(user.id), inline=False)
    embed.add_field(name="Display Name", value=user.display_name, inline=True)
    embed.add_field(
        name="Joined Server",
        value=user.joined_at.strftime("%Y-%m-%d %H:%M UTC") if user.joined_at else "Unknown",
        inline=False
    )
    embed.add_field(
        name="Created Account",
        value=user.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        inline=False
    )
    embed.add_field(
        name="Top Role",
        value=user.top_role.mention if user.top_role else "None",
        inline=False
    )

    await ctx.send(embed=embed)


@bot.hybrid_command(name="serverinfo", description="Show server information")
async def serverinfo(ctx):
    guild = ctx.guild
    if guild is None:
        await ctx.send("❌ This command only works in a server.")
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

    await ctx.send(embed=embed)

# =========================
# NEW COMMANDS
# =========================
@bot.hybrid_command(name="membercount", description="Show the server member count")
async def membercount(ctx):
    if ctx.guild is None:
        await ctx.send("❌ This command only works in a server.")
        return

    humans = len([m for m in ctx.guild.members if not m.bot])
    bots = len([m for m in ctx.guild.members if m.bot])

    embed = discord.Embed(
        title=f"👥 {ctx.guild.name} Member Count",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Total", value=str(ctx.guild.member_count), inline=True)
    embed.add_field(name="Humans", value=str(humans), inline=True)
    embed.add_field(name="Bots", value=str(bots), inline=True)

    await ctx.send(embed=embed)


@bot.hybrid_command(name="banner", description="Show a user's banner if they have one")
async def banner(ctx, user: discord.Member = None):
    target = user or ctx.author
    fetched_user = await bot.fetch_user(target.id)

    if not fetched_user.banner:
        await ctx.send("❌ That user does not have a banner set.")
        return

    embed = discord.Embed(
        title=f"🖼️ {target.display_name}'s Banner",
        color=discord.Color.blurple()
    )
    embed.set_image(url=fetched_user.banner.url)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="roleinfo", description="Show information about a role")
async def roleinfo(ctx, *, role: discord.Role):
    embed = discord.Embed(
        title=f"📛 Role Info - {role.name}",
        color=role.color if role.color.value else discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="ID", value=str(role.id), inline=False)
    embed.add_field(name="Members", value=str(len(role.members)), inline=True)
    embed.add_field(name="Color", value=str(role.color), inline=True)
    embed.add_field(name="Mentionable", value=str(role.mentionable), inline=True)
    embed.add_field(name="Hoisted", value=str(role.hoist), inline=True)
    embed.add_field(name="Position", value=str(role.position), inline=True)
    embed.add_field(name="Created", value=role.created_at.strftime("%Y-%m-%d %H:%M UTC"), inline=False)

    await ctx.send(embed=embed)

# =========================
# FUN COMMANDS
# =========================
@bot.hybrid_command(name="dadjoke", description="Get a dad joke")
async def dadjoke(ctx):
    jokes = [
        "I only know 25 letters of the alphabet… I don’t know y.",
        "Why did the scarecrow win an award? Because he was outstanding in his field.",
        "I told my computer I needed a break… it said no problem — it froze.",
        "Why don’t skeletons fight each other? They don’t have the guts.",
        "I’m reading a book about anti-gravity… it’s impossible to put down."
    ]
    await ctx.send(random.choice(jokes))


@bot.hybrid_command(name="clown", description="Call someone a clown 🤡")
async def clown(ctx, user: discord.Member):
    await ctx.send(f"{user.mention} certified clown 🤡")


@bot.hybrid_command(name="ship", description="Ship two users together")
async def ship(ctx, user1: discord.Member, user2: discord.Member):
    percentage = random.randint(0, 100)

    if percentage > 80:
        msg = "💖 PERFECT MATCH"
    elif percentage > 50:
        msg = "💕 pretty solid"
    else:
        msg = "💀 yeah... no"

    await ctx.send(
        f"{user1.mention} ❤️ {user2.mention}\n**{percentage}%** — {msg}"
    )


@bot.hybrid_command(name="roast", description="Roast someone 💀")
async def roast(ctx, user: discord.Member = None):
    target = user or ctx.author

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
        f"{target.mention} your vibe is “I tried nothing and I’m out of ideas”",
        f"{target.mention} you’ve got main character confidence with NPC logic",
        f"{target.mention} you got the strategic thinking of a coin flip",
        f"{target.mention} you make wrong decisions confidently",
    ]

    await ctx.send(random.choice(roasts))


@bot.hybrid_command(name="meme", description="Get a random meme")
async def meme(ctx):
    await ctx.defer()

    url = "https://meme-api.com/gimme"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send("❌ Failed to fetch a meme. Try again.")
                    return

                data = await resp.json()

        embed = discord.Embed(
            title=data.get("title", "Random Meme"),
            color=discord.Color.blurple()
        )
        embed.set_image(url=data["url"])
        embed.set_footer(text=f"👍 {data.get('ups', 0)} | r/{data.get('subreddit', 'unknown')}")

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error fetching meme:\n`{e}`")


@bot.hybrid_command(name="8ball", description="Ask the magic 8-ball a question")
async def eight_ball(ctx, *, question: str):
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
    await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {random.choice(responses)}")


@bot.hybrid_command(name="coinflip", description="Flip a coin")
async def coinflip(ctx):
    await ctx.send(f"🪙 The coin landed on **{random.choice(['Heads', 'Tails'])}**!")


@bot.hybrid_command(name="choose", description="Choose from options separated by commas")
async def choose(ctx, *, options: str):
    choices = [choice.strip() for choice in options.split(",") if choice.strip()]
    if len(choices) < 2:
        await ctx.send("❌ Give me at least 2 options separated by commas.")
        return

    await ctx.send(f"🤔 I choose: **{random.choice(choices)}**")


@bot.hybrid_command(name="rate", description="Rate something from 1 to 10")
async def rate(ctx, *, thing: str):
    score = random.randint(1, 10)
    await ctx.send(f"📊 I rate **{thing}** a **{score}/10**")

# =========================
# COMMUNITY COMMANDS
# =========================
@bot.hybrid_command(name="suggest", description="Send a suggestion")
async def suggest(ctx, *, suggestion: str):
    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

    if channel is None or not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ Suggestion channel not found. Check `SUGGESTION_CHANNEL_ID`.")
        return

    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=discord.Color.gold(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
    embed.set_footer(text=f"User ID: {ctx.author.id}")

    msg = await channel.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")

    await ctx.send("✅ Your suggestion has been sent!")


@bot.hybrid_command(name="remind", description="Set a reminder")
async def remind(ctx, time: str, *, reminder: str):
    seconds = parse_duration(time)
    if seconds is None:
        await ctx.send("❌ Invalid time format. Use `10s`, `5m`, `2h`, or `1d`.")
        return

    await ctx.send(
        f"⏰ Okay {ctx.author.mention}, I’ll remind you in **{time}**: {reminder}"
    )

    await asyncio.sleep(seconds)

    try:
        await ctx.author.send(f"⏰ Reminder: **{reminder}**")
    except discord.Forbidden:
        if ctx.channel:
            await ctx.channel.send(f"{ctx.author.mention} ⏰ Reminder: **{reminder}**")

# =========================
# STAFF COMMANDS
# =========================
@bot.tree.command(name="pressure", description="Control the pressure response feature")
@app_commands.describe(mode="on, off, or toggle")
async def pressure_slash(interaction: discord.Interaction, mode: str = None):
    global pressure_enabled

    # 🔒 Role check
    role = discord.utils.get(interaction.user.roles, name=SUPPORT_ROLE_NAME)
    if role is None:
        await interaction.response.send_message(
            f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this.",
            ephemeral=True
        )
        return

    # 📊 No argument → show status
    if mode is None:
        status = "ON" if pressure_enabled else "OFF"
        await interaction.response.send_message(
            f"⚡ Pressure response is currently **{status}**.",
            ephemeral=True
        )
        return

    mode = mode.lower()

    # 🔘 Handle modes
    if mode in ["on", "enable"]:
        pressure_enabled = True
        msg = "🟢 Pressure responses enabled."
    elif mode in ["off", "disable"]:
        pressure_enabled = False
        msg = "🔴 Pressure responses disabled."
    elif mode == "toggle":
        pressure_enabled = not pressure_enabled
        msg = f"⚡ Pressure responses {'enabled' if pressure_enabled else 'disabled'}."
    else:
        await interaction.response.send_message(
            "❌ Use `on`, `off`, or `toggle`.",
            ephemeral=True
        )
        return

    await interaction.response.send_message(msg)
    
@bot.hybrid_command(name="xpreset", description="Reset all XP and remove level roles")
@commands.guild_only()
async def xpreset(ctx):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    await ctx.defer()

    await remove_all_level_roles()
    xp_data.clear()
    save_json(XP_FILE, xp_data)

    channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
    if channel:
        await channel.send("🔄 XP has been manually reset.")

    await ctx.send("✅ XP reset completed.")


@bot.hybrid_command(name="xpadd", description="Add XP to a user")
@commands.guild_only()
async def xpadd(ctx, user: discord.Member, amount: int):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    if amount <= 0:
        await ctx.send("❌ XP amount must be greater than 0.")
        return

    user_id = str(user.id)
    ensure_xp_user(user_id)

    old_level = xp_data[user_id]["level"]
    xp_data[user_id]["xp"] += amount
    new_level = get_level_from_xp(xp_data[user_id]["xp"])
    xp_data[user_id]["level"] = new_level
    save_json(XP_FILE, xp_data)

    msg = f"✅ Added **{amount} XP** to {user.mention}."

    if new_level > old_level:
        msg += f"\n🎉 They leveled up to **Level {new_level}**!"

        channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        if channel:
            await channel.send(f"🎉 {user.mention} leveled up to **Level {new_level}**!")

        await apply_level_roles(user, old_level, new_level)

    await ctx.send(msg)


@bot.hybrid_command(name="removexp", description="Remove XP from a user")
@commands.guild_only()
async def removexp(ctx, member: discord.Member, amount: int):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    if amount <= 0:
        await ctx.send("❌ XP amount must be greater than 0.")
        return

    user_id = str(member.id)
    ensure_xp_user(user_id)

    xp_data[user_id]["xp"] = max(0, xp_data[user_id]["xp"] - amount)
    xp_data[user_id]["level"] = get_level_from_xp(xp_data[user_id]["xp"])
    save_json(XP_FILE, xp_data)

    await ctx.send(
        f"✅ Removed **{amount} XP** from {member.mention}.\n"
        f"They now have **{xp_data[user_id]['xp']} XP**."
    )


@bot.hybrid_command(name="say", description="Make Pulse send a message")
@commands.guild_only()
async def say(ctx, *, message: str):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    await ctx.send("✅ Sent.")
    await ctx.channel.send(message)


@bot.hybrid_command(name="embed", description="Send an embed message")
@commands.guild_only()
async def embed_command(ctx, title: str, *, description: str):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    embed = discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    await ctx.send("✅ Embed sent.")
    await ctx.channel.send(embed=embed)


@bot.hybrid_command(name="lock", description="Lock the current channel")
@commands.guild_only()
async def lock(ctx):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("❌ This command only works in text channels.")
        return

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    await ctx.send("🔒 Channel locked.")


@bot.hybrid_command(name="unlock", description="Unlock the current channel")
@commands.guild_only()
async def unlock(ctx):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("❌ This command only works in text channels.")
        return

    overwrite = ctx.channel.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await ctx.channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    await ctx.send("🔓 Channel unlocked.")


@bot.hybrid_command(name="unlockall", description="Unlock all text channels")
@commands.guild_only()
async def unlockall(ctx):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    await ctx.defer()

    for channel in ctx.guild.text_channels:
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = True
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)

    await ctx.send("🔓 All text channels have been unlocked.")


@bot.hybrid_command(name="purge", description="Delete messages")
@commands.guild_only()
async def purge(ctx, amount: int):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    if not isinstance(ctx.channel, discord.TextChannel):
        await ctx.send("❌ This command only works in text channels.")
        return

    if amount < 1:
        await ctx.send("❌ Amount must be at least 1.")
        return

    await ctx.defer()
    deleted = await ctx.channel.purge(limit=amount)
    await ctx.send(f"🧹 Deleted **{len(deleted)}** message(s).")


@bot.hybrid_command(name="warn", description="Warn a user")
@commands.guild_only()
async def warn(ctx, user: discord.Member, *, reason: str = "No reason provided"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    count = add_warning(ctx.guild.id, user.id)

    embed = discord.Embed(
        title="⚠️ User Warned",
        color=discord.Color.orange(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.add_field(name="Total Warnings", value=str(count), inline=False)

    await ctx.send(embed=embed)


@bot.hybrid_command(name="warnings", description="Check a user's warnings")
@commands.guild_only()
async def warnings(ctx, user: discord.Member):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    count = get_warning_count(ctx.guild.id, user.id)
    await ctx.send(f"⚠️ {user.mention} has **{count}** warning(s).")


@bot.hybrid_command(name="clearwarnings", description="Clear a user's warnings")
@commands.guild_only()
async def clearwarnings(ctx, user: discord.Member):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    clear_warning_count(ctx.guild.id, user.id)
    await ctx.send(f"✅ Cleared warnings for {user.mention}.")

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
        await interaction.response.send_message(
            "❌ This command only works in ticket channels.",
            ephemeral=True
        )
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
        await interaction.response.send_message(
            "❌ This command only works in ticket channels.",
            ephemeral=True
        )
        return

    await interaction.channel.set_permissions(user, overwrite=None)
    await interaction.response.send_message(f"✅ Removed {user.mention} from the ticket.")


@bot.tree.command(name="rename", description="Rename the current ticket channel")
@support_only()
@app_commands.describe(name="The new channel name")
async def rename(interaction: discord.Interaction, name: str):
    if not isinstance(interaction.channel, discord.TextChannel):
        await interaction.response.send_message(
            "❌ This command only works in text channels.",
            ephemeral=True
        )
        return

    await interaction.channel.edit(name=name)
    await interaction.response.send_message(f"✅ Channel renamed to **{name}**.")

# =========================
# RUN BOT
# =========================
if TOKEN is None:
    raise ValueError("TOKEN environment variable is not set.")

bot.run(TOKEN)
