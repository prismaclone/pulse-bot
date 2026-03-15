import os
import ast
import math
import random
import asyncio
from datetime import datetime, timezone

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands


# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")

GUILD_ID = 1414144666651197473
SUGGESTION_CHANNEL_ID = 1482554718147580087

SUPPORT_ROLE_NAME = "Support Staff"
TICKET_CATEGORY_NAME = "tickets"


# =========================
# BOT SETUP
# =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
start_time = datetime.now(timezone.utc)


# =========================
# HELP VIEW
# =========================
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Utility", emoji="⚡", style=discord.ButtonStyle.blurple, custom_id="help_utility")
    async def utility_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚡ Utility Commands",
            description="Useful server and general commands.",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/help` - Show the help menu\n"
                "`/ping` - Check bot latency\n"
                "`/hello` - Say hello\n"
                "`/uptime` - Show bot uptime\n"
                "`/botinfo` - Info about Pulse\n"
                "`/serverinfo` - View server info\n"
                "`/serverstats` - Detailed server stats\n"
                "`/userinfo` - View user info\n"
                "`/avatar` - Show a user's avatar\n"
                "`/support` - Get support server invite"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Utility commands")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Fun", emoji="🎉", style=discord.ButtonStyle.green, custom_id="help_fun")
    async def fun_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎉 Fun Commands",
            description="Fun commands for your server.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/meme` - Get a random meme\n"
                "`/8ball` - Ask the magic 8-ball\n"
                "`/coinflip` - Flip a coin\n"
                "`/choose` - Let Pulse choose for you\n"
                "`/rate` - Rate something\n"
                "`/calc` - Solve a math expression"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Fun commands")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Mod", emoji="🛡️", style=discord.ButtonStyle.red, custom_id="help_mod")
    async def mod_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ Moderation Commands",
            description="Moderation and server management tools.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/purge` - Delete messages\n"
                "`/slowmode` - Set slowmode in this channel\n"
                "`/lockall` - Lock all text channels\n"
                "`/embed` - Send a custom embed\n"
                "`/suggest` - Send a suggestion\n"
                "`/remind` - Set a reminder\n"
                "`/ticketpanel` - Send the support ticket panel"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Moderation tools")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Home", emoji="🏠", style=discord.ButtonStyle.gray, row=1, custom_id="help_home")
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚡ Pulse Help Menu",
            description="Welcome to **Pulse's command center**.\n\nUse the buttons below to browse command categories.",
            color=discord.Color.gold()
        )
        embed.add_field(name="⚡ Utility", value="Profiles, server info, and helpful tools.", inline=False)
        embed.add_field(name="🎉 Fun", value="Memes, games, and random fun commands.", inline=False)
        embed.add_field(name="🛡️ Mod", value="Moderation and server management tools.", inline=False)

        if bot.user:
            embed.set_thumbnail(url=bot.user.display_avatar.url)

        embed.set_footer(text="Pulse • Managing everything here ⚡")
        await interaction.response.edit_message(embed=embed, view=self)


# =========================
# TICKET VIEWS
# =========================
class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Claim Ticket", emoji="🎟️", style=discord.ButtonStyle.green, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            support_role = discord.utils.get(interaction.guild.roles, name=SUPPORT_ROLE_NAME)

            if support_role is None or support_role not in interaction.user.roles:
                await interaction.response.send_message("❌ Only support staff can claim tickets.", ephemeral=True)
                return

            topic = interaction.channel.topic or ""

            if topic.startswith("claimed_by:"):
                claimed_id = topic.split(":", 1)[1]

                if claimed_id == str(interaction.user.id):
                    await interaction.response.send_message("⚠️ You already claimed this ticket.", ephemeral=True)
                    return

                claimed_member = interaction.guild.get_member(int(claimed_id))
                claimed_name = claimed_member.mention if claimed_member else "someone else"
                await interaction.response.send_message(
                    f"⚠️ This ticket is already claimed by {claimed_name}.",
                    ephemeral=True
                )
                return

            await interaction.channel.edit(topic=f"claimed_by:{interaction.user.id}")

            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if len(embed.fields) >= 2:
                    embed.set_field_at(
                        1,
                        name="Ticket Status",
                        value=f"**Claimed by:** {interaction.user.mention}",
                        inline=False
                    )
                    await interaction.message.edit(embed=embed, view=self)

            await interaction.channel.send(
                f"🎟️ {interaction.user.mention} has claimed this ticket and will be assisting you."
            )
            await interaction.response.send_message("✅ You claimed this ticket.", ephemeral=True)

        except Exception as e:
            print(f"claim_ticket error: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)

    @discord.ui.button(label="Unclaim Ticket", emoji="↩️", style=discord.ButtonStyle.blurple, custom_id="unclaim_ticket")
    async def unclaim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            support_role = discord.utils.get(interaction.guild.roles, name=SUPPORT_ROLE_NAME)

            if support_role is None or support_role not in interaction.user.roles:
                await interaction.response.send_message("❌ Only support staff can unclaim tickets.", ephemeral=True)
                return

            topic = interaction.channel.topic or ""
            if not topic.startswith("claimed_by:"):
                await interaction.response.send_message("⚠️ This ticket is not currently claimed.", ephemeral=True)
                return

            claimed_id = topic.split(":", 1)[1]
            if claimed_id != str(interaction.user.id):
                claimed_member = interaction.guild.get_member(int(claimed_id))
                claimed_name = claimed_member.mention if claimed_member else "another staff member"
                await interaction.response.send_message(
                    f"⚠️ This ticket is claimed by {claimed_name}, not you.",
                    ephemeral=True
                )
                return

            await interaction.channel.edit(topic="unclaimed")

            if interaction.message.embeds:
                embed = interaction.message.embeds[0]
                if len(embed.fields) >= 2:
                    embed.set_field_at(
                        1,
                        name="Ticket Status",
                        value="**Claimed by:** Nobody",
                        inline=False
                    )
                    await interaction.message.edit(embed=embed, view=self)

            await interaction.channel.send(f"↩️ {interaction.user.mention} unclaimed this ticket.")
            await interaction.response.send_message("✅ You unclaimed this ticket.", ephemeral=True)

        except Exception as e:
            print(f"unclaim_ticket error: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            support_role = discord.utils.get(interaction.guild.roles, name=SUPPORT_ROLE_NAME)

            if support_role is None or support_role not in interaction.user.roles:
                await interaction.response.send_message("❌ Only support staff can close tickets.", ephemeral=True)
                return

            await interaction.response.send_message("🔒 Closing this ticket...", ephemeral=True)
            await interaction.channel.delete()

        except Exception as e:
            print(f"close_ticket error: {e}")
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Error: `{e}`", ephemeral=True)


class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", emoji="📩", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            guild = interaction.guild
            user = interaction.user
            support_role = discord.utils.get(guild.roles, name=SUPPORT_ROLE_NAME)
            category = discord.utils.get(guild.categories, name=TICKET_CATEGORY_NAME)

            existing = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
            if existing:
                await interaction.followup.send(
                    f"⚠️ You already have a ticket open: {existing.mention}",
                    ephemeral=True
                )
                return

            bot_member = guild.me or guild.get_member(bot.user.id)

            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
                bot_member: discord.PermissionOverwrite(
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
                    read_message_history=True
                )

            channel = await guild.create_text_channel(
                name=f"ticket-{user.name.lower()}",
                category=category,
                overwrites=overwrites,
                topic="unclaimed"
            )

            ticket_embed = discord.Embed(
                title="🎟️ Ticket Opened",
                description=(
                    f"{user.mention}, thanks for opening a ticket.\n\n"
                    "Please explain your issue clearly so staff can help faster."
                ),
                color=discord.Color.blurple()
            )
            ticket_embed.add_field(
                name="Helpful details",
                value=(
                    "• What you need help with\n"
                    "• When the issue happened\n"
                    "• Screenshots or evidence\n"
                    "• Extra context if needed"
                ),
                inline=False
            )
            ticket_embed.add_field(name="Ticket Status", value="**Claimed by:** Nobody", inline=False)
            ticket_embed.add_field(name="Reminder", value="Please be patient and avoid ping spamming.", inline=False)
            ticket_embed.set_footer(text="Pulse • Support system ⚡")

            mention_text = f"{user.mention}"
            if support_role:
                mention_text += f" {support_role.mention}"

            await channel.send(
                content=mention_text,
                embed=ticket_embed,
                view=TicketControlView()
            )

            await interaction.followup.send(f"✅ Ticket created: {channel.mention}", ephemeral=True)

        except Exception as e:
            print(f"open_ticket error: {e}")
            await interaction.followup.send(f"❌ Error: `{e}`", ephemeral=True)


# =========================
# SAFE CALCULATOR
# =========================
ALLOWED_AST_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Constant,
    ast.Load,
)

def safe_eval(expression: str):
    tree = ast.parse(expression, mode="eval")

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise ValueError("Only basic math is allowed.")

    return eval(compile(tree, filename="<ast>", mode="eval"), {"__builtins__": {}}, {})


# =========================
# EVENTS
# =========================
@bot.event
async def on_ready():
    print("starting pulse...")
    print(f"Pulse is online as {bot.user}")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="the server pulse ⚡"
        )
    )

    bot.add_view(HelpView())
    bot.add_view(TicketPanelView())
    bot.add_view(TicketControlView())

    try:
        guild = discord.Object(id=GUILD_ID)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        print(f"Synced {len(synced)} command(s) to guild {GUILD_ID}")
    except Exception as e:
        print(f"Sync error: {e}")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    print(f"slash command error: {error}")

    if interaction.response.is_done():
        await interaction.followup.send(f"❌ Command error: `{error}`", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Command error: `{error}`", ephemeral=True)


# =========================
# BASIC COMMANDS
# =========================
@bot.tree.command(name="ping", description="Check if Pulse is alive")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"⚡ Pulse latency: {latency}ms")


@bot.tree.command(name="hello", description="Say hello")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hey {interaction.user.mention} ⚡")


@bot.tree.command(name="avatar", description="Get a user's avatar")
@app_commands.describe(member="The user whose avatar you want to see")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"{member.display_name}'s Avatar", color=discord.Color.gold())
    embed.set_image(url=member.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="userinfo", description="Show info about a user")
@app_commands.describe(member="The user to view info for")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user

    embed = discord.Embed(title="👤 User Info", color=discord.Color.gold())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Username", value=str(member), inline=False)
    embed.add_field(name="ID", value=member.id, inline=False)
    embed.add_field(
        name="Joined Server",
        value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown",
        inline=False
    )
    embed.add_field(
        name="Account Created",
        value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverinfo", description="Show info about the server")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild

    embed = discord.Embed(title="🌐 Server Info", color=discord.Color.gold())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(name="Server Name", value=guild.name, inline=False)
    embed.add_field(name="Members", value=guild.member_count, inline=False)
    embed.add_field(name="Owner", value=str(guild.owner) if guild.owner else "Unknown", inline=False)
    embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="serverstats", description="View detailed server statistics")
async def serverstats(interaction: discord.Interaction):
    guild = interaction.guild

    total_members = guild.member_count or 0
    bot_count = sum(1 for member in guild.members if member.bot)
    human_count = total_members - bot_count

    text_channels = len(guild.text_channels)
    voice_channels = len(guild.voice_channels)
    category_count = len(guild.categories)
    role_count = len(guild.roles)

    boosts = guild.premium_subscription_count or 0
    boost_tier = guild.premium_tier
    owner = guild.owner

    created_at = guild.created_at
    now = datetime.now(timezone.utc)
    server_age_days = (now - created_at).days

    embed = discord.Embed(
        title=f"📊 {guild.name} Statistics",
        description="A full look at this server's current stats.",
        color=discord.Color.blurple()
    )

    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.add_field(
        name="👥 Members",
        value=f"**Total:** {total_members}\n**Humans:** {human_count}\n**Bots:** {bot_count}",
        inline=True
    )
    embed.add_field(
        name="🗂️ Channels",
        value=f"**Text:** {text_channels}\n**Voice:** {voice_channels}\n**Categories:** {category_count}",
        inline=True
    )
    embed.add_field(
        name="✨ Server Info",
        value=f"**Roles:** {role_count}\n**Boosts:** {boosts}\n**Boost Tier:** {boost_tier}",
        inline=True
    )
    embed.add_field(name="👑 Owner", value=owner.mention if owner else "Unknown", inline=True)
    embed.add_field(name="📅 Created On", value=created_at.strftime("%B %d, %Y"), inline=True)
    embed.add_field(name="⏳ Server Age", value=f"**{server_age_days} days old**", inline=True)
    embed.set_footer(text="Pulse • Managing everything here ⚡")

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="say", description="Make Pulse say something")
@app_commands.describe(message="The message Pulse should send")
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message(message)


@bot.tree.command(name="poll", description="Create a yes/no poll")
@app_commands.describe(question="The poll question")
async def poll(interaction: discord.Interaction, question: str):
    embed = discord.Embed(title="📊 Poll", description=question, color=discord.Color.gold())
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

    embed = discord.Embed(title="⚡ Pulse Uptime", color=discord.Color.gold())
    embed.add_field(name="Online For", value=f"{days}d {hours}h {minutes}m {seconds}s", inline=False)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="botinfo", description="Show info about Pulse")
async def botinfo(interaction: discord.Interaction):
    guild_count = len(bot.guilds)
    command_count = len(bot.tree.get_commands())

    embed = discord.Embed(
        title="🤖 Pulse Bot Info",
        description="Modern server utility bot.",
        color=discord.Color.gold()
    )
    embed.add_field(name="Name", value=str(bot.user), inline=False)
    embed.add_field(name="Servers", value=guild_count, inline=False)
    embed.add_field(name="Commands", value=command_count, inline=False)
    embed.add_field(name="Latency", value=f"{round(bot.latency * 1000)}ms", inline=False)

    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    await interaction.response.send_message(embed=embed)


# =========================
# FUN COMMANDS
# =========================
@bot.tree.command(name="8ball", description="Ask the magic 8-ball a question")
@app_commands.describe(question="Your question for the magic 8-ball")
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

    embed = discord.Embed(title="🎱 Magic 8-Ball", color=discord.Color.gold())
    embed.add_field(name="Question", value=question, inline=False)
    embed.add_field(name="Answer", value=random.choice(responses), inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="coinflip", description="Flip a coin")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])

    embed = discord.Embed(
        title="🪙 Coin Flip",
        description=f"The coin landed on **{result}**!",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="choose", description="Choose between options separated by commas")
@app_commands.describe(options="Example: pizza, burgers, tacos")
async def choose(interaction: discord.Interaction, options: str):
    split_options = [option.strip() for option in options.split(",") if option.strip()]

    if len(split_options) < 2:
        await interaction.response.send_message(
            "❌ Give me at least 2 options separated by commas.",
            ephemeral=True
        )
        return

    choice = random.choice(split_options)
    embed = discord.Embed(
        title="🤔 Choice Picker",
        description=f"I choose: **{choice}**",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="rate", description="Rate something out of 10")
@app_commands.describe(thing="The thing you want rated")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(1, 10)

    embed = discord.Embed(
        title="⭐ Rating",
        description=f"**{thing}** gets a **{score}/10**",
        color=discord.Color.gold()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="calc", description="Calculate a math expression")
@app_commands.describe(expression="Example: 5+5*2")
async def calc(interaction: discord.Interaction, expression: str):
    try:
        result = safe_eval(expression)

        embed = discord.Embed(
            title="🧮 Calculator",
            description=f"**Expression:** `{expression}`\n**Result:** `{result}`",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed)

    except Exception:
        await interaction.response.send_message("❌ Invalid expression.", ephemeral=True)


@bot.tree.command(name="meme", description="Get a random meme")
async def meme(interaction: discord.Interaction):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://meme-api.com/gimme") as response:
                data = await response.json()

        embed = discord.Embed(
            title=data.get("title", "Random Meme"),
            color=discord.Color.random()
        )
        embed.set_image(url=data["url"])
        embed.set_footer(text=f"👍 {data.get('ups', 0)} | r/{data.get('subreddit', 'unknown')}")
        await interaction.response.send_message(embed=embed)

    except Exception as e:
        print(f"meme error: {e}")
        await interaction.response.send_message("❌ Couldn't fetch a meme right now.", ephemeral=True)


# =========================
# UTILITY / MOD COMMANDS
# =========================
@bot.tree.command(name="embed", description="Send a simple embed")
@app_commands.describe(title="Embed title", description="Embed description")
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    embed = discord.Embed(title=title, description=description, color=discord.Color.gold())
    embed.set_footer(text=f"Requested by {interaction.user}")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="remind", description="Set a reminder in minutes")
@app_commands.describe(minutes="How many minutes until the reminder", reminder="What you want to be reminded about")
async def remind(interaction: discord.Interaction, minutes: int, reminder: str):
    if minutes <= 0:
        await interaction.response.send_message("❌ Minutes must be more than 0.", ephemeral=True)
        return

    await interaction.response.send_message(
        f"⏰ Okay {interaction.user.mention}, I’ll remind you in {minutes} minute(s).",
        ephemeral=True
    )

    await asyncio.sleep(minutes * 60)

    try:
        await interaction.followup.send(f"⏰ Reminder for {interaction.user.mention}: {reminder}")
    except Exception as e:
        print(f"remind error: {e}")


@bot.tree.command(name="suggest", description="Send a suggestion")
@app_commands.describe(suggestion="Your suggestion")
async def suggest(interaction: discord.Interaction, suggestion: str):
    try:
        channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

        if channel is None:
            await interaction.response.send_message(
                "❌ I couldn't find the suggestion channel.",
                ephemeral=True
            )
            return

        embed = discord.Embed(
            title="💡 New Suggestion",
            description=suggestion,
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Suggested by {interaction.user}")

        message = await channel.send(embed=embed)
        await message.add_reaction("⬆️")
        await message.add_reaction("⬇️")

        await interaction.response.send_message("✅ Your suggestion has been submitted!", ephemeral=True)

    except Exception as e:
        print(f"suggest error: {e}")
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Suggest error: `{e}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Suggest error: `{e}`", ephemeral=True)


@bot.tree.command(name="support", description="Join the official support server")
async def support(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔧 Bot Support",
        description="Need help with commands, bugs, or setup?",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="📌 Support Server",
        value="[Join Here](https://discord.gg/Q9tjKS6rjK)",
        inline=False
    )
    embed.add_field(
        name="💬 What you can do there",
        value="• Get help\n• Report bugs\n• Suggest features\n• Chat with the community",
        inline=False
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="help", description="Show the Pulse help menu")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Pulse Help Menu",
        description="Welcome to **Pulse's command center**.\n\nUse the buttons below to browse command categories.",
        color=discord.Color.gold()
    )
    embed.add_field(name="⚡ Utility", value="Profiles, server info, and helpful tools.", inline=False)
    embed.add_field(name="🎉 Fun", value="Memes, games, and random fun commands.", inline=False)
    embed.add_field(name="🛡️ Mod", value="Moderation and server management tools.", inline=False)

    if bot.user:
        embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.set_footer(text="Pulse • Managing everything here ⚡")
    await interaction.response.send_message(embed=embed, view=HelpView())


@bot.tree.command(name="purge", description="Delete messages in bulk")
@app_commands.describe(amount="Number of messages to delete")
async def purge(interaction: discord.Interaction, amount: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message("❌ You need Manage Messages permission.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be more than 0.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted {len(deleted)} messages.", ephemeral=True)


@bot.tree.command(name="lockall", description="Lock all text channels in the server")
async def lockall(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels permission.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    guild = interaction.guild
    default_role = guild.default_role
    count = 0

    for channel in guild.text_channels:
        try:
            await channel.set_permissions(default_role, send_messages=False)
            count += 1
        except Exception as e:
            print(f"Failed to lock {channel.name}: {e}")

    await interaction.followup.send(f"🔒 Locked {count} channels.", ephemeral=True)


@bot.tree.command(name="slowmode", description="Set slowmode for this channel")
@app_commands.describe(seconds="Slowmode delay in seconds")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if not interaction.user.guild_permissions.manage_channels:
        await interaction.response.send_message("❌ You need Manage Channels permission.", ephemeral=True)
        return

    if seconds < 0:
        await interaction.response.send_message("❌ Slowmode can't be negative.", ephemeral=True)
        return

    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"🐢 Slowmode set to **{seconds} seconds**.", ephemeral=True)


# =========================
# TICKET COMMAND
# =========================
@bot.tree.command(name="ticketpanel", description="Send the ticket panel")
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎟️ Support Tickets",
        description="Press the button below to open a private support ticket.",
        color=discord.Color.blurple()
    )
    embed.add_field(
        name="Use tickets for",
        value=(
            "• Reporting issues\n"
            "• Asking staff for help\n"
            "• Reporting users\n"
            "• Private questions"
        ),
        inline=False
    )
    embed.set_footer(text="Pulse • Managing everything here ⚡")

    await interaction.response.send_message(embed=embed, view=TicketPanelView())


# =========================
# RUN BOT
# =========================
if TOKEN is None:
    raise ValueError("TOKEN environment variable is missing.")

bot.run(TOKEN)
