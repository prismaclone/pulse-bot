import discord
from discord.ext import commands
import os
import random
import asyncio
import aiohttp
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

start_time = datetime.now(timezone.utc)

@bot.event
async def on_ready():
    print("on_ready fired")

    try:
        print("adding HelpView")
        bot.add_view(HelpView())
        print("adding TicketPanelView")
        bot.add_view(TicketPanelView())
        print("adding CloseTicketView")
        bot.add_view(CloseTicketView())
        print("views added")
    except Exception as e:
        print(f"view error: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"sync error: {e}")

    try:
        await bot.change_presence(
            status=discord.Status.online,
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="Managing everything here ⚡"
            )
        )
        print("presence set")
    except Exception as e:
        print(f"presence error: {e}")

    print(f"Pulse is online as {bot.user}")
    
GUILD_ID = 1414144666651197473
MY_GUILD = discord.Object(id=GUILD_ID)

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
  
SUGGESTION_CHANNEL_ID = 1482554718147580087

@bot.tree.command(name="suggest", description="Send a suggestion")
async def suggest(interaction: discord.Interaction, suggestion: str):
    try:
        channel = bot.get_channel(SUGGESTION_CHANNEL_ID)

        if channel is None:
            await interaction.response.send_message(
                "I couldn't find the suggestion channel.",
                ephemeral=True
            )
            return

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

    except Exception as e:
        print(f"suggest error: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                f"Suggest error: {e}",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"Suggest error: {e}",
                ephemeral=True
            )

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

import aiohttp

@bot.tree.command(name="meme", description="Get a random meme")
async def meme(interaction: discord.Interaction):
    async with aiohttp.ClientSession() as session:
        async with session.get("https://meme-api.com/gimme") as response:
            data = await response.json()

    embed = discord.Embed(
        title=data["title"],
        color=discord.Color.random()
    )
    embed.set_image(url=data["url"])
    embed.set_footer(text=f"👍 {data['ups']} | r/{data['subreddit']}")

    await interaction.response.send_message(embed=embed)

import discord
from discord.ext import commands

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Utility", emoji="⚡", style=discord.ButtonStyle.blurple)
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
                "`/userinfo` - View user info\n"
                "`/avatar` - Show a user's avatar"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Utility commands")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Fun", emoji="🎉", style=discord.ButtonStyle.green)
    async def fun_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎉 Fun Commands",
            description="Fun little commands for the server.",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/meme` - Get a random meme\n"
                "`/8ball` - Ask the magic 8-ball\n"
                "`/coinflip` - Flip a coin\n"
                "`/choose` - Let Pulse choose for you\n"
                "`/rate` - Rate something"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Fun commands")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Mod", emoji="🛡️", style=discord.ButtonStyle.red)
    async def mod_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🛡️ Moderation Commands",
            description="Commands for moderation and server management.",
            color=discord.Color.red()
        )
        embed.add_field(
            name="Commands",
            value=(
                "`/clear` - Delete messages\n"
                "`/embed` - Send a custom embed\n"
                "`/suggest` - Send a suggestion\n"
                "`/remind` - Set a reminder"
            ),
            inline=False
        )
        embed.set_footer(text="Pulse • Moderation tools")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Home", emoji="🏠", style=discord.ButtonStyle.gray, row=1)
    async def home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚡ Pulse Help Menu",
            description=(
                "Welcome to **Pulse's command center**.\n\n"
                "Use the buttons below to browse command categories."
            ),
            color=discord.Color.gold()
        )

        embed.add_field(
            name="⚡ Utility",
            value="Profiles, server info, and helpful tools.",
            inline=False
        )
        embed.add_field(
            name="🎉 Fun",
            value="Memes, games, and random fun commands.",
            inline=False
        )
        embed.add_field(
            name="🛡️ Mod",
            value="Moderation and server management tools.",
            inline=False
        )

        embed.set_thumbnail(url=interaction.client.user.display_avatar.url)
        embed.set_footer(text="Pulse • Managing everything here ⚡")

        await interaction.response.edit_message(embed=embed, view=self)


@bot.tree.command(name="help", description="Show the Pulse help menu")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ Pulse Help Menu",
        description=(
            "Welcome to **Pulse's command center**.\n\n"
            "Use the buttons below to browse command categories."
        ),
        color=discord.Color.gold()
    )

    embed.add_field(
        name="⚡ Utility",
        value="Profiles, server info, and helpful tools.",
        inline=False
    )
    embed.add_field(
        name="🎉 Fun",
        value="Memes, games, and random fun commands.",
        inline=False
    )
    embed.add_field(
        name="🛡️ Mod",
        value="Moderation and server management tools.",
        inline=False
    )

    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Pulse • Managing everything here ⚡")

    await interaction.response.send_message(embed=embed, view=HelpView())

from datetime import datetime, timezone

from datetime import datetime, timezone

from datetime import datetime, timezone

from datetime import datetime, timezone

@bot.tree.command(name="serverstats", description="View detailed server statistics")
async def serverstats(interaction: discord.Interaction):
    try:
        guild = interaction.guild

        total_members = guild.member_count or 0
        bot_count = sum(1 for member in guild.members if member.bot) if guild.members else 0
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
            value=(
                f"**Total:** {total_members}\n"
                f"**Humans:** {human_count}\n"
                f"**Bots:** {bot_count}"
            ),
            inline=True
        )

        embed.add_field(
            name="🗂️ Channels",
            value=(
                f"**Text:** {text_channels}\n"
                f"**Voice:** {voice_channels}\n"
                f"**Categories:** {category_count}"
            ),
            inline=True
        )

        embed.add_field(
            name="✨ Server Info",
            value=(
                f"**Roles:** {role_count}\n"
                f"**Boosts:** {boosts}\n"
                f"**Boost Tier:** {boost_tier}"
            ),
            inline=True
        )

        embed.add_field(
            name="👑 Owner",
            value=owner.mention if owner else "Unknown",
            inline=True
        )

        embed.add_field(
            name="📅 Created On",
            value=created_at.strftime("%B %d, %Y"),
            inline=True
        )

        embed.add_field(
            name="⏳ Server Age",
            value=f"**{server_age_days} days old**",
            inline=True
        )

        embed.set_footer(text="Pulse • Managing everything here ⚡")

        await interaction.response.send_message(embed=embed)

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error in /serverstats:\n`{e}`",
            ephemeral=True
        )
        print(f"/serverstats error: {e}")

    print(f"Pulse is online as {bot.user}")
    await interaction.response.send_message(embed=embed)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

import discord
from discord.ext import commands

# ---------- CLOSE TICKET VIEW ----------
class CloseTicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.red)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔒 Closing this ticket...", ephemeral=True)
        await interaction.channel.delete()
        
# ---------- OPEN TICKET VIEW ----------
class TicketPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Open Ticket", emoji="🎟️", style=discord.ButtonStyle.green)
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        user = interaction.user

        # Optional: choose a staff role by name
        staff_role = discord.utils.get(guild.roles, name="Support Staff")

        # Create/find ticket category
        category = discord.utils.get(guild.categories, name="𝚂𝚞𝚙𝚙𝚘𝚛𝚝-𝚃𝚒𝚌𝚔𝚎𝚝𝚜")
        if category is None:
            category = await guild.create_category("Tickets")

        # Prevent duplicate tickets
        existing_channel = discord.utils.get(guild.text_channels, name=f"ticket-{user.name.lower()}")
        if existing_channel:
            await interaction.response.send_message(
                f"⚠️ You already have an open ticket: {existing_channel.mention}",
                ephemeral=True
            )
            return

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                manage_channels=True
            )

        channel = await guild.create_text_channel(
            name=f"ticket-{user.name.lower()}",
            category=category,
            overwrites=overwrites
        )

        ticket_embed = discord.Embed(
            title="🎟️ Ticket Opened",
            description=(
                f"Hey {user.mention}, thanks for opening a ticket.\n\n"
                "**Please explain your issue clearly** so staff can help you faster."
            ),
            color=discord.Color.blurple()
        )

        ticket_embed.add_field(
            name="Helpful details to include",
            value=(
                "• What you need help with\n"
                "• When the issue happened\n"
                "• Screenshots or evidence if needed\n"
                "• Any extra context staff should know"
            ),
            inline=False
        )

        ticket_embed.add_field(
            name="Reminder",
            value="Please be patient and avoid ping spamming. A staff member will respond when available.",
            inline=False
        )

        ticket_embed.set_footer(text="Pulse • Support system ⚡")

        if staff_role:
            await channel.send(content=f"{user.mention} {staff_role.mention}", embed=ticket_embed, view=CloseTicketView())
        else:
            await channel.send(content=f"{user.mention}", embed=ticket_embed, view=CloseTicketView())

        await interaction.response.send_message(
            f"✅ Your ticket has been created: {channel.mention}",
            ephemeral=True
        )


# ---------- TICKET PANEL COMMAND ----------
@bot.tree.command(name="ticketpanel", description="Send the support ticket panel")
async def ticketpanel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎟️ Support Tickets",
        description=(
            "Need help from staff?\n\n"
            "Press the button below to open a private support ticket."
        ),
        color=discord.Color.blurple()
    )

    embed.add_field(
        name="When to open a ticket",
        value=(
            "• Reporting a problem or issue\n"
            "• Asking for staff help\n"
            "• Reporting a user privately\n"
            "• Questions that should not be discussed publicly"
        ),
        inline=False
    )

    embed.add_field(
        name="Before opening one",
        value=(
            "• Make sure your question is not already answered\n"
            "• Use one ticket per issue\n"
            "• Be clear and respectful"
        ),
        inline=False
    )

    embed.set_footer(text="Pulse • Managing everything here ⚡")

    await interaction.response.send_message(embed=embed, view=TicketPanelView())

@bot.tree.command(name="testticket", description="Test ticket command")
async def testticket(interaction: discord.Interaction):
    await interaction.response.send_message("test works")

print("starting pulse...")
bot.run(os.getenv("TOKEN"))
