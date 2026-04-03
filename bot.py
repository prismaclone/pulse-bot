import os
import io
import ast
import json
import time
import math
import random
import shutil
import asyncio
import platform
from datetime import datetime, timezone, timedelta

import aiohttp
import psutil
import discord
from discord.ext import commands
from discord import app_commands

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")

GUILD_ID = 1330034481792552970
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
XP_RESET_INTERVAL = "monthly"  # keep monthly scheduled resets

LEVEL_ROLES = {
    1: 1404861873496784977,
    5: 1404864179134926928,
    10: 1404864410496929862,
    15: 1404864473990168657,
    25: 1404864535491248239,
}

PRESSURE_COOLDOWN = 10
last_pressure = 0
pressure_enabled = True

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
# SAFE JSON HELPERS
# =========================
def _backup_name(filename: str, suffix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{filename}.{suffix}.{timestamp}.bak"


def load_json(filename: str, expected_type=dict):
    if not os.path.exists(filename):
        return expected_type()

    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, expected_type):
            print(f"[WARN] {filename} is not a {expected_type.__name__}; using empty default.")
            return expected_type()

        return data

    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON corrupted in {filename}: {e}")

        # Backup corrupted file
        try:
            corrupt_backup = _backup_name(filename, "corrupt")
            shutil.copy(filename, corrupt_backup)
            print(f"[INFO] Corrupted file backed up to {corrupt_backup}")
        except Exception as backup_error:
            print(f"[WARN] Failed to back up corrupted file {filename}: {backup_error}")

        # Try .bak fallback
        bak_file = f"{filename}.bak"
        if os.path.exists(bak_file):
            try:
                with open(bak_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, expected_type):
                    print(f"[INFO] Loaded backup data from {bak_file}")
                    return data
            except Exception as bak_error:
                print(f"[WARN] Backup file {bak_file} also failed: {bak_error}")

        return expected_type()

    except Exception as e:
        print(f"[ERROR] Failed to load {filename}: {e}")
        return expected_type()


def save_json(filename: str, data) -> bool:
    temp_file = f"{filename}.tmp"
    bak_file = f"{filename}.bak"

    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        if os.path.exists(filename):
            try:
                shutil.copy(filename, bak_file)
            except Exception as backup_error:
                print(f"[WARN] Could not update backup for {filename}: {backup_error}")

        os.replace(temp_file, filename)
        return True

    except Exception as e:
        print(f"[ERROR] Failed to save {filename}: {e}")
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
        except Exception:
            pass
        return False


xp_data = load_json(XP_FILE)
rep_data = load_json(REP_FILE)
warnings_data = load_json(WARNINGS_FILE)

# =========================
# DATA SANITIZERS
# =========================
def sanitize_xp_data():
    global xp_data
    cleaned = {}

    for user_id, info in xp_data.items():
        if not isinstance(info, dict):
            continue

        try:
            cleaned[str(user_id)] = {
                "xp": max(0, int(info.get("xp", 0))),
                "level": max(0, int(info.get("level", 0))),
                "last": float(info.get("last", 0)),
            }
        except (TypeError, ValueError):
            cleaned[str(user_id)] = {
                "xp": 0,
                "level": 0,
                "last": 0.0,
            }

    xp_data = cleaned


def sanitize_rep_data():
    global rep_data
    cleaned = {}

    for user_id, info in rep_data.items():
        if not isinstance(info, dict):
            continue

        try:
            cleaned[str(user_id)] = {
                "rep": int(info.get("rep", 0)),
                "last_given": float(info.get("last_given", 0)),
            }
        except (TypeError, ValueError):
            cleaned[str(user_id)] = {
                "rep": 0,
                "last_given": 0.0,
            }

    rep_data = cleaned


def sanitize_warnings_data():
    global warnings_data
    cleaned = {}

    for guild_id, users in warnings_data.items():
        if not isinstance(users, dict):
            continue

        cleaned_users = {}
        for user_id, count in users.items():
            try:
                cleaned_users[str(user_id)] = max(0, int(count))
            except (TypeError, ValueError):
                cleaned_users[str(user_id)] = 0

        cleaned[str(guild_id)] = cleaned_users

    warnings_data = cleaned


sanitize_xp_data()
sanitize_rep_data()
sanitize_warnings_data()

save_json(XP_FILE, xp_data)
save_json(REP_FILE, rep_data)
save_json(WARNINGS_FILE, warnings_data)

# =========================
# DATA HELPERS
# =========================
def ensure_xp_user(user_id: str):
    user_id = str(user_id)

    if user_id not in xp_data or not isinstance(xp_data[user_id], dict):
        xp_data[user_id] = {
            "xp": 0,
            "level": 0,
            "last": 0.0
        }

    xp_data[user_id].setdefault("xp", 0)
    xp_data[user_id].setdefault("level", 0)
    xp_data[user_id].setdefault("last", 0.0)

    try:
        xp_data[user_id]["xp"] = max(0, int(xp_data[user_id]["xp"]))
    except (TypeError, ValueError):
        xp_data[user_id]["xp"] = 0

    try:
        xp_data[user_id]["level"] = max(0, int(xp_data[user_id]["level"]))
    except (TypeError, ValueError):
        xp_data[user_id]["level"] = 0

    try:
        xp_data[user_id]["last"] = float(xp_data[user_id]["last"])
    except (TypeError, ValueError):
        xp_data[user_id]["last"] = 0.0


def ensure_rep_user(user_id: str):
    user_id = str(user_id)

    if user_id not in rep_data or not isinstance(rep_data[user_id], dict):
        rep_data[user_id] = {
            "rep": 0,
            "last_given": 0.0
        }

    rep_data[user_id].setdefault("rep", 0)
    rep_data[user_id].setdefault("last_given", 0.0)

    try:
        rep_data[user_id]["rep"] = int(rep_data[user_id]["rep"])
    except (TypeError, ValueError):
        rep_data[user_id]["rep"] = 0

    try:
        rep_data[user_id]["last_given"] = float(rep_data[user_id]["last_given"])
    except (TypeError, ValueError):
        rep_data[user_id]["last_given"] = 0.0


def ensure_warning_bucket(guild_id: int):
    guild_key = str(guild_id)
    if guild_key not in warnings_data or not isinstance(warnings_data[guild_key], dict):
        warnings_data[guild_key] = {}
    return guild_key


def get_warning_count(guild_id: int, user_id: int) -> int:
    guild_key = ensure_warning_bucket(guild_id)
    try:
        return int(warnings_data[guild_key].get(str(user_id), 0))
    except (TypeError, ValueError):
        return 0


def add_warning(guild_id: int, user_id: int) -> int:
    guild_key = ensure_warning_bucket(guild_id)
    user_key = str(user_id)
    warnings_data[guild_key][user_key] = get_warning_count(guild_id, user_id) + 1
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
                except Exception as e:
                    print(f"[WARN] Failed to add level role {role_id} to {member}: {e}")


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
                    print(f"[WARN] Couldn't remove XP roles from {member} in {guild.name}")
                except Exception as e:
                    print(f"[WARN] Error removing XP roles from {member}: {e}")


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
            print("[INFO] XP resets are disabled.")
            return

        wait_seconds = max(1, (next_run - now).total_seconds())
        await asyncio.sleep(wait_seconds)

        await remove_all_level_roles()
        xp_data.clear()
        save_json(XP_FILE, xp_data)

        print("[INFO] XP reset completed.")

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


def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)


def format_bytes(num: int) -> str:
    step_unit = 1024
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if num < step_unit:
            return f"{num:.2f} {unit}" if unit != "B" else f"{num} {unit}"
        num /= step_unit
    return f"{num:.2f} PB"


def health_emoji(value: float, warn: float, bad: float) -> str:
    if value >= bad:
        return "🔴"
    if value >= warn:
        return "🟠"
    return "🟢"


def safe_count_channels(guilds):
    text_channels = 0
    voice_channels = 0
    categories = 0
    forums = 0
    stages = 0

    for guild in guilds:
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                text_channels += 1
            elif isinstance(channel, discord.VoiceChannel):
                voice_channels += 1
            elif isinstance(channel, discord.CategoryChannel):
                categories += 1
            elif isinstance(channel, discord.ForumChannel):
                forums += 1
            elif isinstance(channel, discord.StageChannel):
                stages += 1

    return text_channels, voice_channels, categories, forums, stages


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


def safe_eval_expression(expression: str):
    allowed_names = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "pow": pow,
        "sum": sum,
        "pi": math.pi,
        "e": math.e,
    }

    node = ast.parse(expression, mode="eval")

    for subnode in ast.walk(node):
        if isinstance(subnode, ast.Name):
            if subnode.id not in allowed_names:
                raise ValueError("Disallowed name used.")
        elif isinstance(subnode, ast.Call):
            if not isinstance(subnode.func, ast.Name) or subnode.func.id not in allowed_names:
                raise ValueError("Disallowed function call.")
        elif isinstance(subnode, (ast.Import, ast.ImportFrom, ast.Attribute, ast.Subscript, ast.Lambda)):
            raise ValueError("Unsafe expression.")

    return eval(compile(node, "<string>", "eval"), {"__builtins__": {}}, allowed_names)

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
@bot.event
async def on_ready():
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())

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

    if not hasattr(bot, "xp_task_started"):
        bot.loop.create_task(xp_reset_task())
        bot.xp_task_started = True


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    raise error


@bot.event
async def on_message(message):
    global last_pressure

    if message.author.bot or not message.guild:
        await bot.process_commands(message)
        return

    # pressure response
    if pressure_enabled and "pressure" in message.content.lower():
        now = time.time()
        if now - last_pressure > PRESSURE_COOLDOWN:
            if random.randint(1, 3) == 1:
                await message.channel.send("YOURE UNDER THE PRESSURE!!!! 😂")
                last_pressure = now

    # xp system
    user_id = str(message.author.id)
    ensure_xp_user(user_id)

    now = time.time()
    if now - xp_data[user_id]["last"] < XP_COOLDOWN:
        await bot.process_commands(message)
        return

    xp_gain = random.randint(*XP_PER_MESSAGE)
    xp_data[user_id]["xp"] += xp_gain
    xp_data[user_id]["last"] = now

    old_level = xp_data[user_id]["level"]
    new_level = get_level_from_xp(xp_data[user_id]["xp"])
    xp_data[user_id]["level"] = new_level

    if new_level > old_level:
        channel = bot.get_channel(LEVEL_UP_CHANNEL_ID)
        if channel:
            try:
                await channel.send(
                    f"🎉 {message.author.mention} leveled up to **Level {new_level}**!"
                )
            except Exception as e:
                print(f"[WARN] Failed sending level-up message: {e}")

        await apply_level_roles(message.author, old_level, new_level)

    save_json(XP_FILE, xp_data)
    await bot.process_commands(message)

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

    await ctx.send(f"⭐ {member.mention} has **{rep_data[user_id]['rep']} reputation**.")


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
# DIAGNOSTICS / PROFILE / CORE
# =========================
@bot.hybrid_command(name="diagnose", description="Extremely advanced diagnostics for Pulse")
async def diagnose(ctx: commands.Context):
    try:
        await ctx.defer()
    except Exception:
        pass

    now = datetime.now(timezone.utc)
    uptime_seconds = (now - start_time).total_seconds()

    process = psutil.Process(os.getpid())

    psutil.cpu_percent(interval=None)
    cpu_percent = psutil.cpu_percent(interval=0.3)

    virtual_mem = psutil.virtual_memory()
    disk_path = "C:\\" if os.name == "nt" else "/"
    disk_usage = psutil.disk_usage(disk_path)
    swap_mem = psutil.swap_memory()

    process_mem = process.memory_info()
    process_cpu = process.cpu_percent(interval=0.1)
    process_threads = process.num_threads()
    process_created = datetime.fromtimestamp(process.create_time(), tz=timezone.utc)

    bot_latency_ms = round(bot.latency * 1000)

    api_latency_ms = None
    api_status = "Unknown"
    try:
        api_start = time.perf_counter()
        async with aiohttp.ClientSession() as session:
            async with session.get("https://discord.com/api/v10/gateway", timeout=5) as resp:
                api_latency_ms = round((time.perf_counter() - api_start) * 1000)
                api_status = str(resp.status)
    except Exception as e:
        api_status = f"Error: {type(e).__name__}"

    guild_count = len(bot.guilds)
    user_count = sum((g.member_count or 0) for g in bot.guilds)

    text_channels, voice_channels, categories, forums, stages = safe_count_channels(bot.guilds)

    slash_count = len(bot.tree.get_commands())
    prefix_count = len(bot.commands)
    cogs_count = len(bot.cogs)

    shard_count = bot.shard_count or 1
    shard_id = ctx.guild.shard_id if ctx.guild else 0

    python_version = platform.python_version()
    discord_version = discord.__version__
    system_name = platform.system()
    system_release = platform.release()
    machine = platform.machine()
    processor = platform.processor() or "Unknown"

    boot_time = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)
    system_uptime = (now - boot_time).total_seconds()

    warnings = []

    cpu_flag = health_emoji(cpu_percent, 65, 85)
    ram_flag = health_emoji(virtual_mem.percent, 70, 90)
    disk_flag = health_emoji(disk_usage.percent, 80, 92)

    proc_ram_mb = process_mem.rss / 1024 / 1024

    if cpu_percent >= 85:
        warnings.append("High system CPU usage detected.")
    if virtual_mem.percent >= 90:
        warnings.append("Very high system RAM usage detected.")
    if disk_usage.percent >= 92:
        warnings.append("Disk space is critically high.")
    if bot_latency_ms >= 250:
        warnings.append("Gateway latency is elevated.")
    if api_latency_ms is not None and api_latency_ms >= 500:
        warnings.append("Discord REST/API latency is elevated.")
    if process_cpu >= 50:
        warnings.append("Pulse process CPU usage is unusually high.")
    if proc_ram_mb >= 700:
        warnings.append("Pulse process memory usage is high.")

    if not warnings:
        overall_status = "🟢 Stable"
        color = discord.Color.green()
    elif len(warnings) <= 2:
        overall_status = "🟠 Warning"
        color = discord.Color.orange()
    else:
        overall_status = "🔴 Critical"
        color = discord.Color.red()

    latency_class = (
        "Excellent" if bot_latency_ms < 100
        else "Good" if bot_latency_ms < 180
        else "Fair" if bot_latency_ms < 250
        else "Poor"
    )

    embed = discord.Embed(
        title="⚡ Pulse Deep Diagnostics",
        description=(
            f"**Overall Status:** {overall_status}\n"
            f"**Checked:** <t:{int(now.timestamp())}:R>"
        ),
        color=color,
        timestamp=now
    )

    embed.add_field(
        name="🌐 Connection",
        value=(
            f"**Gateway Ping:** `{bot_latency_ms} ms`\n"
            f"**API Ping:** `{api_latency_ms if api_latency_ms is not None else 'N/A'} ms`\n"
            f"**API Status:** `{api_status}`\n"
            f"**Shard:** `{shard_id}/{max(shard_count - 1, 0)}`"
        ),
        inline=False
    )

    embed.add_field(
        name="⏱️ Runtime",
        value=(
            f"**Bot Uptime:** `{format_duration(uptime_seconds)}`\n"
            f"**System Uptime:** `{format_duration(system_uptime)}`\n"
            f"**Process Started:** <t:{int(process_created.timestamp())}:R>\n"
            f"**System Boot:** <t:{int(boot_time.timestamp())}:R>"
        ),
        inline=False
    )

    embed.add_field(
        name="🖥️ System Health",
        value=(
            f"{cpu_flag} **CPU:** `{cpu_percent}%`\n"
            f"{ram_flag} **RAM:** `{virtual_mem.percent}%` "
            f"(`{format_bytes(virtual_mem.used)}` / `{format_bytes(virtual_mem.total)}`)\n"
            f"{disk_flag} **Disk:** `{disk_usage.percent}%` "
            f"(`{format_bytes(disk_usage.used)}` / `{format_bytes(disk_usage.total)}`)\n"
            f"🟣 **Swap:** `{swap_mem.percent}%` "
            f"(`{format_bytes(swap_mem.used)}` / `{format_bytes(swap_mem.total)}`)"
        ),
        inline=False
    )

    embed.add_field(
        name="🤖 Pulse Process",
        value=(
            f"**Process CPU:** `{process_cpu:.1f}%`\n"
            f"**Process RAM:** `{proc_ram_mb:.2f} MB`\n"
            f"**Threads:** `{process_threads}`\n"
            f"**PID:** `{process.pid}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📦 Environment",
        value=(
            f"**OS:** `{system_name} {system_release}`\n"
            f"**Architecture:** `{machine}`\n"
            f"**Processor:** `{processor[:80]}`\n"
            f"**Python:** `{python_version}`\n"
            f"**discord.py:** `{discord_version}`"
        ),
        inline=False
    )

    embed.add_field(
        name="📊 Discord Stats",
        value=(
            f"**Servers:** `{guild_count}`\n"
            f"**Users:** `{user_count}`\n"
            f"**Text Channels:** `{text_channels}`\n"
            f"**Voice Channels:** `{voice_channels}`\n"
            f"**Categories:** `{categories}`\n"
            f"**Forums:** `{forums}`\n"
            f"**Stage Channels:** `{stages}`"
        ),
        inline=False
    )

    embed.add_field(
        name="⚙️ Command System",
        value=(
            f"**Slash Commands:** `{slash_count}`\n"
            f"**Prefix Commands:** `{prefix_count}`\n"
            f"**Cogs Loaded:** `{cogs_count}`\n"
            f"**Latency Class:** `{latency_class}`"
        ),
        inline=False
    )

    warning_text = "\n".join(f"• {warning}" for warning in warnings[:8]) if warnings else "• No active issues detected."
    embed.add_field(name="🚨 Alerts", value=warning_text, inline=False)
    embed.set_footer(text="Pulse Advanced Diagnostic Engine • Internal health sweep complete")

    await ctx.send(embed=embed)


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
    level = get_level_from_xp(xp)
    xp_data[user_id]["level"] = level
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

    save_json(XP_FILE, xp_data)
    await ctx.send(embed=embed)


@bot.hybrid_command(name="rank", description="Check your level and XP")
async def rank(ctx, user: discord.Member = None):
    target = user or ctx.author
    user_id = str(target.id)

    ensure_xp_user(user_id)

    xp = xp_data[user_id]["xp"]
    level = get_level_from_xp(xp)
    xp_data[user_id]["level"] = level

    current_level_xp = get_xp_for_level(level)
    next_level_xp = get_xp_for_level(level + 1)

    save_json(XP_FILE, xp_data)

    await ctx.send(
        f"📊 {target.mention}\n"
        f"**Level:** {level}\n"
        f"**Total XP:** {xp}\n"
        f"**Progress:** {xp - current_level_xp}/{next_level_xp - current_level_xp} XP"
    )


@bot.hybrid_command(name="leaderboard", description="Top XP users")
async def leaderboard(ctx):
    sorted_users = sorted(
        xp_data.items(),
        key=lambda x: int(x[1].get("xp", 0)),
        reverse=True
    )[:10]

    desc = ""
    for i, (user_id, data) in enumerate(sorted_users, 1):
        try:
            user = await bot.fetch_user(int(user_id))
            name = user.name
        except Exception:
            name = "Unknown"
        desc += f"**{i}.** {name} — {int(data.get('xp', 0))} XP\n"

    embed = discord.Embed(
        title="🏆 Leaderboard",
        description=desc or "No data yet.",
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

# =========================
# GENERAL / UTILITY COMMANDS
# =========================
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


@bot.hybrid_command(name="calc", description="Calculate a math expression")
async def calc(ctx, *, expression: str):
    try:
        result = safe_eval_expression(expression)
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


@bot.hybrid_command(name="embed", description="Send a simple embed")
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
    await ctx.send(embed=embed)


@bot.hybrid_command(name="say", description="Make Pulse say something")
async def say(ctx, *, message: str):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    await ctx.send(message)


@bot.hybrid_command(name="remind", description="Set a reminder")
async def remind(ctx, duration: str, *, reminder_text: str):
    seconds = parse_duration(duration)
    if seconds is None:
        await ctx.send("❌ Use a valid duration like `10s`, `5m`, `2h`, or `1d`.")
        return

    await ctx.send(f"⏰ Okay {ctx.author.mention}, I’ll remind you in **{duration}**.")

    async def reminder_task():
        await asyncio.sleep(seconds)
        try:
            await ctx.send(f"🔔 {ctx.author.mention} reminder: {reminder_text}")
        except Exception:
            pass

    bot.loop.create_task(reminder_task())


@bot.hybrid_command(name="suggest", description="Send a suggestion")
async def suggest(ctx, *, suggestion: str):
    channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

    if channel is None or not isinstance(channel, discord.TextChannel):
        await ctx.send("❌ Suggestion channel not found.")
        return

    embed = discord.Embed(
        title="💡 New Suggestion",
        description=suggestion,
        color=discord.Color.blurple(),
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)

    msg = await channel.send(embed=embed)
    try:
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")
    except Exception:
        pass

    await ctx.send("✅ Your suggestion has been submitted.")

# =========================
# FUN COMMANDS
# =========================
dad_jokes = [
    "Why don't skeletons fight each other? They don't have the guts.",
    "I only know 25 letters of the alphabet. I don't know y.",
    "What do you call fake spaghetti? An impasta.",
    "Why did the scarecrow win an award? Because he was outstanding in his field."
]

roasts = [
    "You bring everyone so much joy... when you leave the room.",
    "I'd agree with you, but then we'd both be wrong.",
    "You're proof that even Discord has lag in real life.",
    "You have something on your chin... no, the third one down."
]

eight_ball_responses = [
    "Yes.",
    "No.",
    "Maybe.",
    "Definitely.",
    "Absolutely not.",
    "Ask again later.",
    "Without a doubt.",
    "Very unlikely.",
    "Signs point to yes.",
    "I wouldn't count on it."
]

@bot.hybrid_command(name="dadjoke", description="Get a dad joke")
async def dadjoke(ctx):
    await ctx.send(f"😂 {random.choice(dad_jokes)}")


@bot.hybrid_command(name="clown", description="Call someone a clown")
async def clown(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"🤡 {member.mention} has officially been declared a clown.")


@bot.hybrid_command(name="ship", description="Ship two users")
async def ship(ctx, user1: discord.Member, user2: discord.Member):
    score = random.randint(1, 100)
    if score >= 90:
        verdict = "soulmates fr"
    elif score >= 70:
        verdict = "kinda cute ngl"
    elif score >= 40:
        verdict = "could work maybe"
    else:
        verdict = "uh... maybe as friends"

    await ctx.send(f"💖 {user1.mention} + {user2.mention} = **{score}%**\nVerdict: **{verdict}**")


@bot.hybrid_command(name="roast", description="Roast a user")
async def roast(ctx, member: discord.Member = None):
    member = member or ctx.author
    await ctx.send(f"🔥 {member.mention} — {random.choice(roasts)}")


@bot.hybrid_command(name="8ball", with_app_command=True, description="Ask the magic 8-ball a question")
async def eightball(ctx, *, question: str):
    await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {random.choice(eight_ball_responses)}")


@bot.hybrid_command(name="coinflip", description="Flip a coin")
async def coinflip(ctx):
    await ctx.send(f"🪙 It landed on **{random.choice(['Heads', 'Tails'])}**.")


@bot.hybrid_command(name="choose", description="Choose between options separated by |")
async def choose(ctx, *, options: str):
    parts = [p.strip() for p in options.split("|") if p.strip()]
    if len(parts) < 2:
        await ctx.send("❌ Give me at least two options separated by `|`.")
        return

    await ctx.send(f"🤔 I choose: **{random.choice(parts)}**")

# =========================
# WARNINGS / MODERATION
# =========================
@bot.hybrid_command(name="warn", description="Warn a user")
@commands.guild_only()
async def warn(ctx, user: discord.Member, *, reason: str = "No reason provided"):
    if not isinstance(ctx.author, discord.Member) or not is_staff(ctx.author):
        await ctx.send(f"❌ You need the **{SUPPORT_ROLE_NAME}** role to use this command.")
        return

    total = add_warning(ctx.guild.id, user.id)
    await ctx.send(f"⚠️ Warned {user.mention}.\n**Reason:** {reason}\nThey now have **{total}** warning(s).")


@bot.hybrid_command(name="warnings", description="Check a user's warnings")
@commands.guild_only()
async def warnings(ctx, user: discord.Member):
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
# HELP COMMAND
# =========================
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
            "`/roleinfo` `p!roleinfo`\n"
            "`/calc` `p!calc`"
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
            "`/8ball` `p!8ball`\n"
            "`/coinflip` `p!coinflip`\n"
            "`/choose` `p!choose`"
        ),
        inline=False
    )

    embed.add_field(
        name="Utility / Community",
        value=(
            "`/suggest` `p!suggest`\n"
            "`/remind` `p!remind`\n"
            "`/embed` `p!embed`\n"
            "`p!rep`\n"
            "`p!repcheck`\n"
            "`p!reptop`\n"
            "`/diagnose` `p!diagnose`"
        ),
        inline=False
    )

    embed.add_field(
        name="Moderation",
        value=(
            "`/warn` `p!warn`\n"
            "`/warnings` `p!warnings`\n"
            "`/clearwarnings` `p!clearwarnings`\n"
            "`/say` `p!say`"
        ),
        inline=False
    )

    embed.add_field(
        name="Tickets",
        value=(
            "`/ticketpanel`\n"
            "`/adduser`\n"
            "`/removeuser`\n"
            "`/rename`"
        ),
        inline=False
    )

    embed.set_footer(text="Pulse • slash + prefix hybrid system")
    await ctx.send(embed=embed)

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
