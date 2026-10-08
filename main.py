import discord
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
import requests
import datetime
import json
import logging
import os

# ===============================
# Logging
# ===============================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("contest_oracle")
logging.getLogger("discord").setLevel(logging.WARNING)

# ===============================
# bot data
# ===============================
load_dotenv()

TOKEN = os.environ.get("DISCORD_TOKEN", "").strip()

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
# Roles per guild for emoji
# ===============================
ROLE_IDS: dict[str, dict[str, int]] = {}

async def ensure_guild_roles(guild: discord.Guild) -> dict[str, int]:
    """Create (if missing) and return {emoji: role_id} for a guild."""
    mapping: dict[str, int] = {}
    for emoji, name in ROLE_NAMES.items():
        role = discord.utils.get(guild.roles, name=name)
        if role is None:
            role = await guild.create_role(name=name)
            log.info("[%s] Role created: %s (%s)", guild.name, role.name, role.id)
        mapping[emoji] = role.id
    ROLE_IDS[str(guild.id)] = mapping
    return mapping

# ===============================
# Fetch Codeforces contests
# ===============================
def fetch_codeforces_contests():
    url = "https://codeforces.com/api/contest.list?gym=false"
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
        payload = res.json()
    except (requests.RequestException, ValueError) as e:
        log.error("Error fetching contests: %s", e)
        return []

    if payload.get("status") != "OK":
        log.error("Codeforces API returned a non-OK status: %s", payload.get("status"))
        return []

    contests = payload.get("result") or []
    upcoming = []

    for c in contests:
        if c.get("phase") != "BEFORE":
            continue
        name = c.get("name", "")
        if ("Div. 1" in name or "Div. 2" in name or "Div. 1 + Div. 2" in name):
            upcoming.append((c, "🔵"))
        elif "Div. 3" in name:
            upcoming.append((c, "🟢"))
        elif "Div. 4" in name:
            upcoming.append((c, "🟡"))

    log.info("Upcoming contests found: %s", len(upcoming))
    return upcoming

# ===============================
# Automatic loop for sending contests
# ===============================
async def notify_guild(guild_id, channel_id, contests):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        log.warning("Guild %s not found", guild_id)
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        log.warning("Channel %s not found in %s", channel_id, guild.name)
        return

    sent_for_server = SENT_CONTESTS.get(str(guild_id), [])

    for c, emoji in contests:
        contest_id = c["id"]
        if contest_id in sent_for_server:
            continue

        start_time = datetime.datetime.fromtimestamp(c["startTimeSeconds"], datetime.timezone.utc)
        start_str = start_time.strftime("%d/%m %H:%M UTC")
        role_id = ROLE_IDS.get(str(guild_id), {}).get(emoji)
        role_mention = f"<@&{role_id}>" if role_id else ""

        msg = (
            f"{role_mention}\n"
            f"📢 New contest detected!\n"
            f"{c['name']}\n"
            f"Starts: {start_str}\n"
            f"https://codeforces.com/contest/{c['id']}"
        )

        log.info("[%s] Sending contest: %s to channel: %s", guild.name, c["name"], channel.name)
        try:
            await channel.send(msg)
        except discord.HTTPException as e:
            log.warning("[%s] Failed to send contest %s: %s", guild.name, contest_id, e)
            continue

        sent_for_server.append(contest_id)
        SENT_CONTESTS[str(guild_id)] = sent_for_server
        save_sent_contests()


@tasks.loop(minutes=10)
async def check_contests():
    log.info("===== Checking contests =====")
    contests = sorted(fetch_codeforces_contests(), key=lambda x: x[0]["startTimeSeconds"])

    for guild_id, channel_id in SERVER_CHANNELS.items():
        try:
            await notify_guild(guild_id, channel_id, contests)
        except Exception:
            log.exception("Error while notifying guild %s", guild_id)

# ===============================
# Command /reactionrole
# ===============================
@tree.command(name="reactionrole", description="Sets up reaction roles and creates roles automatically")
@app_commands.default_permissions(administrator=True)
async def reactionrole(interaction: discord.Interaction):
    guild = interaction.guild
    log.info("[%s] Command /reactionrole executed (guild id %s)", guild.name, guild.id)

    await ensure_guild_roles(guild)

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
    log.info("[%s] Command /listdivs called (guild id %s)", interaction.guild.name, interaction.guild.id)
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
    log.info("[%s] Command /setchannel called (guild id %s)", interaction.guild.name, interaction.guild.id)
    log.info("[%s] Notification channel set to: %s (%s)", interaction.guild.name, channel.name, channel.id)
    await interaction.response.send_message(f"Notification channel set to {channel.mention}!", ephemeral=True)

# ===============================
# Add/remove reaction events
# ===============================
@bot.event
async def on_raw_reaction_add(payload):
    if payload.guild_id is None or payload.user_id == bot.user.id:
        return

    message_id = REACTION_MESSAGES.get(str(payload.guild_id))
    if payload.message_id != message_id:
        return

    emoji = payload.emoji.name
    role_id = ROLE_IDS.get(str(payload.guild_id), {}).get(emoji)
    if role_id is None:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    role = guild.get_role(role_id)
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.add_roles(role)
        log.info("Added role %s to %s (%s)", role.name, member.name, guild.name)

@bot.event
async def on_raw_reaction_remove(payload):
    if payload.guild_id is None:
        return

    message_id = REACTION_MESSAGES.get(str(payload.guild_id))
    if payload.message_id != message_id:
        return

    emoji = payload.emoji.name
    role_id = ROLE_IDS.get(str(payload.guild_id), {}).get(emoji)
    if role_id is None:
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    role = guild.get_role(role_id)
    member = guild.get_member(payload.user_id)
    if role and member:
        await member.remove_roles(role)
        log.info("Removed role %s from %s (%s)", role.name, member.name, guild.name)

# ===============================
# Event on_ready
# ===============================
@bot.event
async def on_ready():
    log.info("Bot connected as %s", bot.user)

    # on_ready can fire again on reconnects — only bootstrap once.
    if getattr(bot, "_bootstrap_done", False):
        return

    # Automatically creates roles if they don't exist.
    for guild in bot.guilds:
        log.info("Initializing roles on server: %s (%s)", guild.name, guild.id)
        await ensure_guild_roles(guild)

    await tree.sync()
    check_contests.start()
    log.info("Contest check loop started.")
    bot._bootstrap_done = True

if not TOKEN:
    raise SystemExit(
        "DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in, "
        "or export DISCORD_TOKEN in your shell."
    )

bot.run(TOKEN)
