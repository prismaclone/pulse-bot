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

bot.run(os.getenv("TOKEN"))
