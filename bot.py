import os
import discord
from discord.ext import commands, tasks
import aiohttp
from flask import Flask
from threading import Thread
from datetime import time, timezone
import xml.etree.ElementTree as ET
import re

# ==========================================
# 1. SERVEUR FLASK POUR RENDER (KEEP ALIVE)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Le bot Roblox, Twitch & Rocket League est en ligne !"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# ==========================================
# 2. CONFIGURATION DU BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# IDs des salons Discord
ROBLOX_UNIVERSE_ID = 6880080644
ROBLOX_CHANNEL_ID = 1344403756811423854
TWITCH_CHANNEL_ID = 1517233263293497384
RL_SHOP_CHANNEL_ID = 1515508545418952734     # Salon pour la Boutique RL (!shop)
RL_UPDATES_CHANNEL_ID = 1534708870352732241 # Salon pour les Versions / Patch Notes Rocket League

# Clés Twitch API
TWITCH_CLIENT_ID = os.environ.get("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.environ.get("TWITCH_CLIENT_SECRET")
twitch_access_token = None

# LISTE STREAMERS TWITCH
STREAMERS = [
    "mawkzy_", "rocketbaguette", "fuury_off", "atowwwww", "kaydop", "vatira", 
    "zenrll", "alpha54", "chausette45", "fairy_peak", "extra", "saizen", "radosin", 
    "juicy", "seikoo", "monkeymoon", "itachi", "aztral", "ferra", "eversax", 
    "exotiik", "dralii", "lecheps", "payriixx", "poachimpa", "kaokor", "rasmelthor", 
    "shogunfr", "yukeofr", "rocketleague", "squishymuffinz", "lethamyr", "apparentlyjack", 
    "retals", "arsenal", "garrettg", "ayyjayy", "jstn", "daniel", "beastmode", "comm", 
    "firstkiller", "chronic", "lj", "mist", "cheese", "hockser", "percy", "chicago", 
    "rizzo", "athena", "jonsandman", "sunlesskhan", "musty", "cbell", "thanovic", 
    "wayton", "chiefbeef_rl", "evample", "frontalpanda", "pulsemk", "pulsetemple", 
    "hivise", "cbellrl", "woody", "spookluke", "virge", "gibbs", "johnnyboi_i", 
    "dazerin", "corelli", "turtle", "stumpy", "cole", "jannlpzz", "rosdri_twitch", 
    "stake", "crr", "atomik", "dorito", "marc_by_8", "rezears", "kairiu", "tox", 
    "trk511__", "rw9", "kiileerrz", "nwpo", "ahmad", "okhali_d", "venom", "smw", 
    "m7sn", "t7lm", "catalysm", "nass", "oaly", "oski", "joreuz", "rise", "archie", 
    "scrubkilla", "yukeo", "yanxnz", "lostt", "kv1", "motta", "aztromick", "caard", 
    "math", "droppz", "muiricle", "henkovic", "jzr", "ganer", "kuxir97", "maktuf", 
    "wavepunk", "achieves"
]

last_roblox_timestamp = None
last_rl_patch_title = None
current_rl_version = "v2.72"  # Version par défaut initiale
currently_live = set()

# Fonction d'envoi de la boutique RL
async def send_rl_shop(target_channel):
    embed = discord.Embed(
        title="🛒 BOUTIQUE ROCKET LEAGUE",
        description="La rotation quotidienne de la boutique est en ligne en jeu !\n\n*Pense à lancer Rocket League pour découvrir les nouveaux objets et packs disponibles aujourd'hui.*",
        color=discord.Color.blue()
    )
    embed.add_field(name="🔄 Rotation", value="Actualisation quotidienne automatique", inline=False)
    embed.set_footer(text="L3X BOT - Alertes Rocket League")
    
    await target_channel.send(embed=embed)

# ------------------------------------------
# EVENEMENTS ET COMMANDES
# ------------------------------------------
@bot.event
async def on_ready():
    print(f"✅ Bot connecté avec succès en tant que : {bot.user}")
    check_roblox_update.start()
    check_rocket_league_patches.start()
    check_twitch_streams.start()
    daily_rl_shop.start()

# Commande manuelle !shop
@bot.command(name="shop")
async def manual_shop(ctx):
    await send_rl_shop(ctx.channel)

# Commande manuelle !versionrl affichant la version dynamique
@bot.command(name="versionrl", aliases=["versionrocketleague"])
async def version_rl(ctx):
    patch_url = "https://www.rocketleague.com/news/tag/patch-notes"
    embed = discord.Embed(
        title="🎮 PATCH NOTES & VERSIONS ROCKET LEAGUE",
        description=f"Version actuelle du jeu : **{current_rl_version}**\n\nConsulte les dernières notes de mise à jour officielles :\n\n👉 **[Clique ici pour voir les Patch Notes]({patch_url})**",
        color=discord.Color.orange()
    )
    embed.add_field(name="📌 Suivi des versions", value="Lien direct vers les patchs officiels", inline=False)
    embed.set_footer(text=f"Demandé par {ctx.author.name} - L3X BOT")
    await ctx.send(embed=embed)

# Tâche quotidienne automatique de la boutique (20h00 UTC)
@tasks.loop(time=time(hour=20, minute=0, tzinfo=timezone.utc))
async def daily_rl_shop():
    channel = bot.get_channel(RL_SHOP_CHANNEL_ID)
    if channel:
        await send_rl_shop(channel)

# ------------------------------------------
# TÂCHES DE SURVEILLANCE (PATCHES, ROBLOX, TWITCH)
# ------------------------------------------
@tasks.loop(minutes=5)
async def check_rocket_league_patches():
    global last_rl_patch_title, current_rl_version
    rss_url = "https://www.rocketleague.com/news/rss/"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(rss_url) as response:
                if response.status == 200:
                    xml_content = await response.text()
                    root = ET.fromstring(xml_content)
                    
                    for item in root.findall(".//item"):
                        title = item.find("title").text
                        link = item.find("link").text
                        
                        if "patch" in title.lower() or "v2." in title.lower() or "update" in title.lower():
                            # Extraire automatiquement le numéro de version (ex: v2.73) s'il est présent dans le titre
                            match = re.search(r'v2\.\d+', title, re.IGNORECASE)
                            if match:
                                current_rl_version = match.group(0)

                            if last_rl_patch_title is None:
                                last_rl_patch_title = title
                            elif title != last_rl_patch_title:
                                last_rl_patch_title = title
                                channel = bot.get_channel(RL_UPDATES_CHANNEL_ID)
                                if channel:
                                    embed = discord.Embed(
                                        title=f"🚀 NOUVELLE VERSION ({current_rl_version}) ROCKET LEAGUE !",
                                        description=f"**{title}**",
                                        url=link,
                                        color=discord.Color.orange()
                                    )
                                    embed.add_field(name="Lien officiel", value=link, inline=False)
                                    embed.set_footer(text="Alerte de version automatique - L3X BOT")
                                    await channel.send(content="@everyone", embed=embed)
                            break
        except Exception as e:
            print(f"Erreur vérification patch Rocket League : {e}")

@tasks.loop(minutes=2)
async def check_roblox_update():
    global last_roblox_timestamp
    url = f"https://games.roblox.com/v1/games?universeIds={ROBLOX_UNIVERSE_ID}"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        game_info = data["data"][0]
                        updated_at = game_info.get("updated")
                        name = game_info.get("name")

                        if last_roblox_timestamp is None:
                            last_roblox_timestamp = updated_at
                        elif updated_at != last_roblox_timestamp:
                            last_roblox_timestamp = updated_at
                            channel = bot.get_channel(ROBLOX_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="🚀 NOUVELLE MISE À JOUR ROBLOX !",
                                    description=f"Le jeu **{name}** vient de recevoir une mise à jour !",
                                    color=discord.Color.green()
                                )
                                embed.add_field(name="Horodatage", value=updated_at, inline=False)
                                await channel.send(content="@everyone", embed=embed)
        except Exception as e:
            print(f"Erreur Roblox : {e}")

async def get_twitch_token():
    global twitch_access_token
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    url = "https://id.twitch.tv/oauth2/token"
    params = {
        "client_id": TWITCH_CLIENT_ID,
        "client_secret": TWITCH_CLIENT_SECRET,
        "grant_type": "client_credentials"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                twitch_access_token = data.get("access_token")
                return twitch_access_token
            return None

@tasks.loop(minutes=3)
async def check_twitch_streams():
    global twitch_access_token
    if not twitch_access_token:
        await get_twitch_token()
        if not twitch_access_token:
            return

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_access_token}"
    }

    chunk_size = 100
    streamer_chunks = [STREAMERS[i:i + chunk_size] for i in range(0, len(STREAMERS), chunk_size)]
    active_live_this_check = set()

    async with aiohttp.ClientSession() as session:
        for chunk in streamer_chunks:
            url = "https://api.twitch.tv/helix/streams?" + "&".join([f"user_login={s}" for s in chunk])
            try:
                async with session.get(url, headers=headers) as resp:
                    if resp.status == 401:
                        await get_twitch_token()
                        headers["Authorization"] = f"Bearer {twitch_access_token}"
                        continue
                    
                    if resp.status == 200:
                        data = await resp.json()
                        streams = data.get("data", [])

                        for stream in streams:
                            user_login = stream["user_login"].lower()
                            game_name = stream.get("game_name", "")
                            
                            if "rocket league" in game_name.lower():
                                active_live_this_check.add(user_login)

                                if user_login not in currently_live:
                                    currently_live.add(user_login)
                                    channel = bot.get_channel(TWITCH_CHANNEL_ID)
                                    if channel:
                                        stream_url = f"https://www.twitch.tv/{user_login}"
                                        embed = discord.Embed(
                                            title=f"🔴 {stream['user_name']} est en LIVE sur Rocket League !",
                                            description=f"**Titre :** {stream['title']}\n**Spectateurs :** 👁️ {stream['viewer_count']}",
                                            url=stream_url,
                                    color=discord.Color.purple()
                                        )
                                        embed.set_thumbnail(url=stream['thumbnail_url'].replace("{width}", "320").replace("{height}", "180"))
                                        embed.add_field(name="Lien du Stream", value=stream_url, inline=False)
                                        await channel.send(content=f"🔴 **{stream['user_name']}** est actuellement en direct !", embed=embed)
            except Exception as e:
                print(f"Erreur Twitch : {e}")

    for streamer in list(currently_live):
        if streamer not in active_live_this_check:
            currently_live.remove(streamer)

# ==========================================
# 3. DÉMARRAGE DU BOT
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
