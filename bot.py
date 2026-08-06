import os
import asyncio
from flask import Flask
from threading import Thread
import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
from datetime import time, timezone
import xml.etree.ElementTree as ET
import re
import urllib.parse

# ==========================================
# 1. SERVEUR FLASK POUR RENDER (KEEP ALIVE)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "🚀 L3X BOT est en ligne et opérationnel !"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run, daemon=True)
    t.start()

keep_alive()

# ==========================================
# 2. CONFIGURATION DU BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

class L3XBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        
        check_roblox_update.start()
        check_rocket_league_patches.start()
        check_fortnite_updates.start()
        check_twitch_streams.start()
        daily_rl_shop.start()

    async def close(self):
        if self.session:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        print(f"✅ Connecté avec succès en tant que : {self.user} (ID: {self.user.id})")
        try:
            synced = await self.tree.sync()
            print(f"🔄 Commandes Slash synchronisées avec succès : {len(synced)}")
        except Exception as e:
            print(f"❌ Erreur lors de la synchronisation des commandes : {e}")

bot = L3XBot()

# IDs des salons Discord
ROBLOX_CHANNEL_ID = int(os.getenv("ROBLOX_CHANNEL_ID", 1534679583947886594))
TWITCH_CHANNEL_ID = int(os.getenv("TWITCH_CHANNEL_ID", 1517233263293497384))
RL_SHOP_CHANNEL_ID = int(os.getenv("RL_SHOP_CHANNEL_ID", 1515508545418952734))
RL_UPDATES_CHANNEL_ID = int(os.getenv("RL_UPDATES_CHANNEL_ID", 1534708870352732241))
FN_UPDATES_CHANNEL_ID = int(os.getenv("FN_UPDATES_CHANNEL_ID", 1534724078584336384))

TWITCH_CLIENT_ID = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
twitch_access_token = None

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

last_roblox_version_hash = None
last_rl_patch_title = None
current_rl_version = "v2.72"
last_fn_news_title = None
current_fn_version = "v39.00"
currently_live = set()

# ==========================================
# 3. FONCTIONS UTILITAIRES & COMMANDES SLASH
# ==========================================

async def send_rl_shop(target_channel):
    if not target_channel:
        return
    embed = discord.Embed(
        title="🛒 BOUTIQUE ROCKET LEAGUE",
        description="La rotation quotidienne de la boutique est en ligne en jeu !\n\n*Pense à lancer Rocket League pour découvrir les nouveautés du jour.*",
        color=discord.Color.blue()
    )
    embed.add_field(name="🔄 Rotation", value="Actualisation quotidienne automatique", inline=False)
    embed.set_footer(text="L3X BOT - Alertes Rocket League")
    await target_channel.send(embed=embed)

@bot.tree.command(name="shoprl", description="[ADMIN] Force l'affichage de la boutique Rocket League.")
@app_commands.checks.has_permissions(administrator=True)
async def slash_shoprl(interaction: discord.Interaction):
    await send_rl_shop(interaction.channel)
    await interaction.response.send_message("✅ Message de la boutique envoyé avec succès !", ephemeral=True)

@bot.tree.command(name="versionrl", description="Affiche la version actuelle et les patch notes de Rocket League.")
async def slash_versionrl(interaction: discord.Interaction):
    patch_url = "https://www.rocketleague.com/news/tag/patch-notes"
    embed = discord.Embed(
        title="🎮 PATCH NOTES & VERSIONS ROCKET LEAGUE",
        description=f"Version actuelle du jeu : **{current_rl_version}**\n\nConsulte les dernières notes de mise à jour officielles :\n\n👉 **[Clique ici pour voir les Patch Notes]({patch_url})**",
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} - L3X BOT")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="versionfn", description="Affiche les actualités et versions du jeu Fortnite.")
async def slash_versionfn(interaction: discord.Interaction):
    fn_url = "https://www.fortnite.com/news"
    embed = discord.Embed(
        title="🌀 ACTUALITÉS & VERSIONS FORTNITE",
        description=f"Version / mise à jour récente du jeu : **{current_fn_version}**\n\nConsulte les dernières annonces officielles :\n\n👉 **[Clique ici pour voir les actualités Fortnite]({fn_url})**",
        color=discord.Color.purple()
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} - L3X BOT")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="robloxversion", description="Donne la version officielle actuelle de Roblox.")
async def slash_robloxversion(interaction: discord.Interaction):
    url = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
    try:
        async with bot.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                version_hash = data.get("clientVersionUpload")
                embed = discord.Embed(
                    description=f"🎮 **Version actuelle de Roblox**\n\nLa version officielle actuelle est : `{version_hash}`",
                    color=discord.Color.blue()
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message("❌ Impossible de récupérer la version actuelle de Roblox.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur technique : {e}", ephemeral=True)

# ==========================================
# 4. MODULE ANIME-SAMA (/animesama)
# ==========================================
class AnimeView(discord.ui.View):
    def __init__(self, anime_name: str):
        super().__init__(timeout=180)
        query = urllib.parse.quote(anime_name)
        url = f"https://anime-sama.to/catalogue/?search={query}"
        
        self.add_item(discord.ui.Button(
            label="📺 Lancer la recherche sur Anime-Sama",
            style=discord.ButtonStyle.link,
            url=url
        ))

@bot.tree.command(name="animesama", description="Recherche un animé sur Anime-Sama de façon privée.")
@app_commands.describe(nom="Nom de l'animé à rechercher (tolère les petites fautes)")
async def animesama(interaction: discord.Interaction, nom: str):
    embed = discord.Embed(
        title="🌸 Recherche Anime-Sama",
        description=f"Résultat de la recherche pour : **{nom}**",
        color=discord.Color.from_rgb(255, 105, 180)
    )
    embed.add_field(
        name="💡 Astuce", 
        value="Clique sur le bouton ci-dessous pour ouvrir la recherche directement sur le site en privé.", 
        inline=False
    )
    embed.set_footer(text="L3X BOT - Streaming Anime")
    
    await interaction.response.send_message(embed=embed, view=AnimeView(nom), ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Tu n'as pas les permissions nécessaires pour exécuter cette commande.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Tu n'as pas les permissions nécessaires pour exécuter cette commande.", ephemeral=True)
    else:
        print(f"Erreur de commande slash : {error}")

# ==========================================
# 5. TÂCHES AUTOMATIQUES DE FOND (LOOPS)
# ==========================================

@tasks.loop(time=time(hour=20, minute=0, tzinfo=timezone.utc))
async def daily_rl_shop():
    channel = bot.get_channel(RL_SHOP_CHANNEL_ID)
    if channel:
        await send_rl_shop(channel)

@tasks.loop(minutes=5)
async def check_rocket_league_patches():
    global last_rl_patch_title, current_rl_version
    rss_url = "https://www.rocketleague.com/news/rss/"

    try:
        async with bot.session.get(rss_url) as response:
            if response.status == 200:
                xml_content = await response.text()
                root = ET.fromstring(xml_content)
                
                for item in root.findall(".//item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    
                    if title_el is None or link_el is None:
                        continue
                        
                    title = title_el.text or ""
                    link = link_el.text or ""
                    
                    if "patch" in title.lower() or "v2." in title.lower() or "update" in title.lower():
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
                                embed.set_footer(text="Alerte automatique - L3X BOT")
                                await channel.send(content="@everyone", embed=embed)
                        break
    except Exception as e:
        print(f"Erreur vérification patch Rocket League : {e}")

@tasks.loop(minutes=10)
async def check_fortnite_updates():
    global last_fn_news_title, current_fn_version
    fn_api_url = "https://fortnite-api.com/v2/news/br"

    try:
        async with bot.session.get(fn_api_url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("status") == 200:
                    motd = data["data"]["motds"][0]
                    title = motd.get("title")
                    body = motd.get("body", "")
                    image = motd.get("image")

                    match = re.search(r'v\d+\.\d+', title + " " + body, re.IGNORECASE)
                    if match:
                        current_fn_version = match.group(0)

                    if last_fn_news_title is None:
                        last_fn_news_title = title
                    elif title != last_fn_news_title:
                        last_fn_news_title = title
                        channel = bot.get_channel(FN_UPDATES_CHANNEL_ID)
                        if channel:
                            embed = discord.Embed(
                                title=f"🌀 NOUVELLE ACTUALITÉ / MISE À JOUR FORTNITE !",
                                description=f"**{title}**\n\n{body}",
                                color=discord.Color.purple()
                            )
                            if image:
                                embed.set_image(url=image)
                            embed.add_field(name="Version détectée", value=current_fn_version, inline=False)
                            embed.set_footer(text="Alerte Fortnite automatique - L3X BOT")
                            await channel.send(content="@everyone", embed=embed)
    except Exception as e:
        print(f"Erreur vérification actualités Fortnite : {e}")

@tasks.loop(minutes=5)
async def check_roblox_update():
    global last_roblox_version_hash
    url = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"

    try:
        async with bot.session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                version_hash = data.get("clientVersionUpload")
                normalized_hash = version_hash.lower() if version_hash else ""

                if last_roblox_version_hash is None:
                    last_roblox_version_hash = normalized_hash
                elif normalized_hash != last_roblox_version_hash:
                    last_roblox_version_hash = normalized_hash
                    channel = bot.get_channel(ROBLOX_CHANNEL_ID)
                    if channel:
                        embed = discord.Embed(
                            description=f"🎮 **Nouvelle version de Roblox déployée !**\n\nLa nouvelle version officielle est : `{version_hash}`",
                            color=discord.Color.blue()
                        )
                        embed.set_footer(text="Alerte Roblox automatique - L3X BOT")
                        await channel.send(content="@everyone", embed=embed)
    except Exception as e:
        print(f"Erreur vérification Roblox : {e}")

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
    try:
        async with bot.session.post(url, params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                twitch_access_token = data.get("access_token")
                return twitch_access_token
    except Exception as e:
        print(f"Erreur génération token Twitch : {e}")
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

    for chunk in streamer_chunks:
        url = "https://api.twitch.tv/helix/streams?" + "&".join([f"user_login={s}" for s in chunk])
        try:
            async with bot.session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    await get_twitch_token()
                    if not twitch_access_token:
                        break
                    headers["Authorization"] = f"Bearer {twitch_access_token}"
                    async with bot.session.get(url, headers=headers) as retry_resp:
                        if retry_resp.status == 200:
                            data = await retry_resp.json()
                            streams = data.get("data", [])
                        else:
                            continue
                elif resp.status == 200:
                    data = await resp.json()
                    streams = data.get("data", [])
                else:
                    continue

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
            print(f"Erreur vérification Twitch : {e}")

    currently_live.difference_update(currently_live - active_live_this_check)

# ==========================================
# 6. DÉMARRAGE DU BOT
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Erreur critique : Aucun token Discord trouvé dans les variables d'environnement (DISCORD_TOKEN).")
