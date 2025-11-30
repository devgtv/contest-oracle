import discord
from discord.ext import tasks
from discord import app_commands
import requests
import datetime
import json
import os

# ===============================
# Dados do bot
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
# Dados persistentes
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

def salvar_server_channels():
    with open(SERVER_CHANNELS_FILE, "w") as f:
        json.dump(SERVER_CHANNELS, f, indent=4)

def salvar_sent_contests():
    with open(SENT_CONTESTS_FILE, "w") as f:
        json.dump(SENT_CONTESTS, f, indent=4)

def salvar_reaction_messages():
    with open(REACTION_MESSAGES_FILE, "w") as f:
        json.dump(REACTION_MESSAGES, f, indent=4)

# ===============================
#  global de roles por emoji
# ===============================
ROLE_IDS = {}

# ===============================
# search contests Codeforces
# ===============================
def buscar_contests_codeforces():
    url = "https://codeforces.com/api/contest.list?gym=false"
    try:
        res = requests.get(url).json()
    except Exception as e:
        print(f"[DEBUG] Erro ao buscar contests: {e}")
        return []

    if res["status"] != "OK":
        print("[DEBUG] Código de status não OK ao buscar contests")
        return []

    contests = res["result"]
    proximos = []

    for c in contests:
        if c["phase"] == "BEFORE":
            name = c["name"]
            if ("Div. 1" in name or "Div. 2" in name or "Div. 1 + Div. 2" in name):
                proximos.append((c, "🔵"))
            elif "Div. 3" in name:
                proximos.append((c, "🟢"))
            elif "Div. 4" in name:
                proximos.append((c, "🟡"))

    print(f"[DEBUG] Contests futuros encontrados: {len(proximos)}")
    return proximos

# ===============================
# Loop automático para enviar contests
# ===============================
@tasks.loop(minutes=10)
async def verificar_contests():
    print("[DEBUG] ===== Verificando contests =====")
    for guild_id, channel_id in SERVER_CHANNELS.items():
        guild = bot.get_guild(int(guild_id))
        if not guild:
            print(f"[DEBUG] Guild {guild_id} não encontrada")
            continue
        channel = guild.get_channel(channel_id)
        if not channel:
            print(f"[DEBUG] Canal {channel_id} não encontrado em {guild.name}")
            continue

        contests = buscar_contests_codeforces()
        contests = sorted(contests, key=lambda x: x[0]["startTimeSeconds"])

        enviados_servidor = SENT_CONTESTS.get(str(guild_id), [])

        for c, emoji in contests:
            contest_id = c["id"]
            if contest_id in enviados_servidor:
                continue

            inicio = datetime.datetime.fromtimestamp(c["startTimeSeconds"], datetime.timezone.utc)
            inicio_str = inicio.strftime("%d/%m %H:%M UTC")
            role_id = ROLE_IDS.get(emoji)
            role_mention = f"<@&{role_id}>" if role_id else ""

            msg = (
                f"{role_mention}\n"
                f"📢 Novo contest detectado!\n"
                f"{c['name']}\n"
                f"Começa: {inicio_str}\n"
                f"https://codeforces.com/contest/{c['id']}"
            )

            print(f"[DEBUG][{guild.name}] Enviando contest: {c['name']} para canal: {channel.name}")
            await channel.send(msg)
            enviados_servidor.append(contest_id)
            SENT_CONTESTS[str(guild_id)] = enviados_servidor
            salvar_sent_contests()

# ===============================
# comand /reactionrole
# ===============================
@tree.command(name="reactionrole", description="Configura reaction roles e cria cargos automaticamente")
@app_commands.default_permissions(administrator=True)
async def reactionrole(interaction: discord.Interaction):
    global ROLE_IDS
    guild = interaction.guild
    print(f"[DEBUG] Comando /reactionrole executado no servidor: {guild.name} ({guild.id})")
    ROLE_IDS = {}

    for emoji, nome in ROLE_NAMES.items():
        role = discord.utils.get(guild.roles, name=nome)
        if not role:
            role = await guild.create_role(name=nome)
            print(f"[DEBUG] Cargo criado: {role.name} ({role.id})")
        else:
            print(f"[DEBUG] Cargo existente: {role.name} ({role.id})")
        ROLE_IDS[emoji] = role.id

    desc = (
        "Reaja com os contests que quer receber alerta:\n\n"
        "🔵 Div 1/2\n"
        "🟢 Div 3\n"
        "🟡 Div 4"
    )
    embed = discord.Embed(title="Reaction Roles — Codeforces", description=desc, color=discord.Color.blue())
    msg = await interaction.channel.send(embed=embed)
    for emoji in REACTION_EMOJIS:
        await msg.add_reaction(emoji)

    REACTION_MESSAGES[str(guild.id)] = msg.id
    salvar_reaction_messages()

    await interaction.response.send_message("Reaction roles configuradas e cargos criados automaticamente!", ephemeral=True)

# ===============================
# Comando /mostrardivs
# ===============================
@tree.command(name="mostrardivs", description="Mostra os próximos contests por divisão")
async def mostrardivs(interaction: discord.Interaction):
    print(f"[DEBUG] Comando /mostrardivs chamado no servidor: {interaction.guild.name} ({interaction.guild.id})")
    await interaction.response.defer(ephemeral=False)

    contests = buscar_contests_codeforces()
    contests = sorted(contests, key=lambda x: x[0]["startTimeSeconds"])

    if not contests:
        await interaction.followup.send("Nenhum contest futuro encontrado.", ephemeral=True)
        return

    msg = ""
    for c, emoji in contests[:10]:
        inicio = datetime.datetime.fromtimestamp(c["startTimeSeconds"], datetime.timezone.utc)
        inicio_str = inicio.strftime("%d/%m %H:%M UTC")
        div = ROLE_NAMES.get(emoji, "")
        msg += f"**{c['name']}** ({div}) — Começa: {inicio_str}\n🔗 https://codeforces.com/contest/{c['id']}\n\n"

    await interaction.followup.send(msg, ephemeral=False)

# ===============================
# setchanel
# ===============================
@tree.command(name="setcanal", description="Define o canal de avisos do Codeforces")
@app_commands.default_permissions(administrator=True)
async def setcanal(interaction: discord.Interaction, canal: discord.TextChannel):
    SERVER_CHANNELS[str(interaction.guild.id)] = canal.id
    salvar_server_channels()
    print(f"[DEBUG] Comando /setcanal chamado no servidor: {interaction.guild.name} ({interaction.guild.id})")
    print(f"[DEBUG] Canal de avisos definido: {canal.name} ({canal.id})")
    await interaction.response.send_message(f"Canal de avisos definido para {canal.mention}!", ephemeral=True)

# ===============================
# Eventos de adicionar/remover reaction
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
        print(f"[DEBUG] Adicionado cargo {role.name} a {member.name} ({guild.name})")

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
        print(f"[DEBUG] Removido cargo {role.name} de {member.name} ({guild.name})")

# ===============================
# Evento on_ready
# ===============================
@bot.event
async def on_ready():
    global ROLE_IDS
    print(f"[DEBUG] Bot conectado como {bot.user}")

    # Cria cargos automaticamente se não existirem
    for guild in bot.guilds:
        print(f"[DEBUG] Inicializando roles no servidor: {guild.name} ({guild.id})")
        for emoji, nome in ROLE_NAMES.items():
            role = discord.utils.get(guild.roles, name=nome)
            if not role:
                role = await guild.create_role(name=nome)
                print(f"[DEBUG] Cargo criado: {role.name} ({role.id})")
            ROLE_IDS[emoji] = role.id

    await tree.sync()
    verificar_contests.start()
    print("[DEBUG] Loop de contests iniciado.")

bot.run(TOKEN)
