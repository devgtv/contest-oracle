import discord
from discord.ext import tasks
from discord import app_commands
import requests
import datetime
import json
import os

# ===============================
# bot data
# ===============================
TOKEN = "" #Paste the bot token here.

REACTION_EMOJIS = ["🔵", "🟢", "🟡"]
ROLE_NAMES = {"🔵": "Div 1/2", "🟢": "Div 3", "🟡": "Div 4"}

SERVER_CHANNELS_FILE = "server_channels.json"
SENT_CONTESTS_FILE = "sent_contests.json"
REACTION_MESSAGES_FILE = "reaction_messages.json"

# ===============================
# INTENTS
# ===============================
INTENTS = discord.Intents.default()
INTENTS.guilds = True
INTENTS.members = True
INTENTS.message_content = True
INTENTS.messages = True

bot = discord.Client(intents=INTENTS)
tree = app_commands.CommandTree(bot)

# ===============================
# Persistent data
# ===============================
if os.path.exists(SERVER_CHANNELS_FILE):
    with open(SERVER_CHANNELS_FILE, "r") as f:
        SERVER_CHANNELS = json.load(f)
else:
    SERVER_CHANNELS = {}

if os.path.exists(SENT_CONTESTS_FILE):
    with open(SENT_CONTESTS_FILE, "r") as f:
        SENT_CONTESTS = json.load(f)
else:
    SENT_CONTESTS = {}

if os.path.exists(REACTION_MESSAGES_FILE):
    with open(REACTION_MESSAGES_FILE, "r") as f:
        REACTION_MESSAGES = json.load(f)
else:
    REACTION_MESSAGES = {}

def save_server_channels():
    with open(SERVER_CHANNELS_FILE, "w") as f:
        json.dump(SERVER_CHANNELS, f, indent=4)

def save_sent_contests():
    with open(SENT_CONTESTS_FILE, "w") as f:
        json.dump(SENT_CONTESTS, f, indent=4)

def save_reaction_messages():
    with open(REACTION_MESSAGES_FILE, "w") as f:
        json.dump(REACTION_MESSAGES, f, indent=4)

# ===============================
# Global roles for emoji
# ===============================
ROLE_IDS = {}

# ===============================
# Fetch Codeforces contests
# ===============================
def fetch_codeforces_contests():
    url = "https://codeforces.com/api/contest.list?gym=false"
    try:
        res = requests.get(url).json()
    except Exception as e:
        print(f"[DEBUG] Error fetching contests: {e}")
        return []

    if res["status"] != "OK":
        print("[DEBUG] Non-OK status code when fetching contests")
        return []

    contests = res["result"]
    upcoming = []

    for c in contests:
        if c["phase"] == "BEFORE":
            name = c["name"]
            if ("Div. 1" in name or "Div. 2" in name or "Div. 1 + Div. 2" in name):
                upcoming.append((c, "🔵"))
            elif "Div. 3" in name:
                upcoming.append((c, "🟢"))
            elif "Div. 4" in name:
                upcoming.append((c, "🟡"))

    print(f"[DEBUG] Upcoming contests found: {len(upcoming)}")
    return upcoming

# ===============================
# Automatic loop for sending contests
# ===============================
@tasks.loop(minutes=10)
async def check_contests():
    print("[DEBUG] ===== Checking contests =====")
    for guild_id, channel_id in SERVER_CHANNELS.items():
        guild = bot.get_guild(int(guild_id))
        if not guild:
            print(f"[DEBUG] Guild {guild_id} not found")
            continue
        channel = guild.get_channel(channel_id)
        if not channel:
            print(f"[DEBUG] Channel {channel_id} not found in {guild.name}")
            continue

        contests = fetch_codeforces_contests()
        contests = sorted(contests, key=lambda x: x[0]["startTimeSeconds"])

        sent_for_server = SENT_CONTESTS.get(str(guild_id), [])

        for c, emoji in contests:
            contest_id = c["id"]
            if contest_id in sent_for_server:
                continue

            start_time = datetime.datetime.fromtimestamp(c["startTimeSeconds"], datetime.timezone.utc)
            start_str = start_time.strftime("%d/%m %H:%M UTC")
            role_id = ROLE_IDS.get(emoji)
            role_mention = f"<@&{role_id}>" if role_id else ""

            msg = (
                f"{role_mention}\n"
                f"📢 New contest detected!\n"
                f"{c['name']}\n"
                f"Starts: {start_str}\n"
                f"https://codeforces.com/contest/{c['id']}"
            )

            print(f"[DEBUG][{guild.name}] Sending contest: {c['name']} to channel: {channel.name}")
            await channel.send(msg)
            sent_for_server.append(contest_id)
            SENT_CONTESTS[str(guild_id)] = sent_for_server
            save_sent_contests()

# ===============================
# Command /reactionrole
# ===============================
@tree.command(name="reactionrole", description="Sets up reaction roles and creates roles automatically")
@app_commands.default_permissions(administrator=True)
async def reactionrole(interaction: discord.Interaction):
    global ROLE_IDS
    guild = interaction.guild
    print(f"[DEBUG] Command /reactionrole executed on server: {guild.name} ({guild.id})")
    ROLE_IDS = {}

    for emoji, name in ROLE_NAMES.items():
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name)
            print(f"[DEBUG] Role created: {role.name} ({role.id})")
        else:
            print(f"[DEBUG] Existing role: {role.name} ({role.id})")
        ROLE_IDS[emoji] = role.id

    desc = (
        "React with the contests you want to receive alerts for:\n\n"
        "🔵 Div 1/2\n"
        "🟢 Div 3\n"
        "🟡 Div 4"
    )
    embed = discord.Embed(title="Reaction Roles — Codeforces", description=desc, color=discord.Color.blue())
    msg = await interaction.channel.send(embed=embed)
    for emoji in REACTION_EMOJIS:
        await msg.add_reaction(emoji)

    REACTION_MESSAGES[str(guild.id)] = msg.id
    save_reaction_messages()

    await interaction.response.send_message("Reaction roles configured and roles created automatically!", ephemeral=True)

# ===============================
# Command /listdivs
# ===============================
@tree.command(name="listdivs", description="Shows upcoming contests by division")
async def listdivs(interaction: discord.Interaction):
    print(f"[DEBUG] Command /listdivs called on server: {interaction.guild.name} ({interaction.guild.id})")
    await interaction.response.defer(ephemeral=False)

    contests = fetch_codeforces_contests()
    contests = sorted(contests, key=lambda x: x[0]["startTimeSeconds"])

    if not contests:
        await interaction.followup.send("No upcoming contests found.", ephemeral=True)
        return

    msg = ""
    for c, emoji in contests[:10]:
        start_time = datetime.datetime.fromtimestamp(c["startTimeSeconds"], datetime.timezone.utc)
        start_str = start_time.strftime("%d/%m %H:%M UTC")
        div = ROLE_NAMES.get(emoji, "")
        msg += f"**{c['name']}** ({div}) — Starts: {start_str}\n🔗 https://codeforces.com/contest/{c['id']}\n\n"

    await interaction.followup.send(msg, ephemeral=False)

# ===============================
# Command /setchannel
# ===============================
@tree.command(name="setchannel", description="Sets the Codeforces notification channel")
@app_commands.default_permissions(administrator=True)
async def setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    SERVER_CHANNELS[str(interaction.guild.id)] = channel.id
    save_server_channels()
    print(f"[DEBUG] Command /setchannel called on server: {interaction.guild.name} ({interaction.guild.id})")
    print(f"[DEBUG] Notification channel set to: {channel.name} ({channel.id})")
    await interaction.response.send_message(f"Notification channel set to {channel.mention}!", ephemeral=True)

# ===============================
# Add/remove reaction events
# ===============================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.user_id == bot.user.id:
        return

    message_id = REACTION_MESSAGES.get(str(payload.guild_id))
    if payload.message_id != message_id:
        return

    emoji = payload.emoji.name
    if emoji not in ROLE_IDS:
        return

    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(ROLE_IDS[emoji])
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.add_roles(role)
        print(f"[DEBUG] Added role {role.name} to {member.name} ({guild.name})")

@bot.event
async def on_raw_reaction_remove(payload):
    message_id = REACTION_MESSAGES.get(str(payload.guild_id))
    if payload.message_id != message_id:
        return

    emoji = payload.emoji.name
    if emoji not in ROLE_IDS:
        return

    guild = bot.get_guild(payload.guild_id)
    role = guild.get_role(ROLE_IDS[emoji])
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.remove_roles(role)
        print(f"[DEBUG] Removed role {role.name} from {member.name} ({guild.name})")

# ===============================
# Event on_ready
# ===============================
@bot.event
async def on_ready():
    global ROLE_IDS
    print(f"[DEBUG] Bot connected as {bot.user}")

    # Automatically creates roles if they don't exist.
    for guild in bot.guilds:
        print(f"[DEBUG] Initializing roles on server: {guild.name} ({guild.id})")
        for emoji, name in ROLE_NAMES.items():
            role = discord.utils.get(guild.roles, name=name)
            if not role:
                role = await guild.create_role(name=name)
                print(f"[DEBUG] Role created: {role.name} ({role.id})")
            ROLE_IDS[emoji] = role.id

    await tree.sync()
    check_contests.start()
    print("[DEBUG] Contest check loop started.")

bot.run(TOKEN)
