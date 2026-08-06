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
import cloudscraper
from bs4 import BeautifulSoup
import requests

# ==========================================
# 1. FLASK KEEP-ALIVE (RENDER)
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
# 2. BOT DISCORD
# ==========================================
intents = discord.Intents.all()
scrap = cloudscraper.create_scraper()

class L3XBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="/", intents=intents)
        self.session: aiohttp.ClientSession | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        check_roblox_update.start()
        check_rocket_league_patches.start()
        check_fortnite_updates.start()
        check_twitch_streams.start()
        daily_rl_shop.start()

    async def close(self):
        if self.session and not self.session.closed:
            await self.session.close()
        await super().close()

    async def on_ready(self):
        print(f"✅ Connecté : {self.user} (ID: {self.user.id})")
        try:
            synced = await self.tree.sync()
            print(f"🔄 Commandes synchronisées : {len(synced)}")
        except Exception as e:
            print(f"❌ Sync error : {e}")

bot = L3XBot()

# ==========================================
# 3. CHANNEL IDs & CONFIG
# ==========================================
ROBLOX_CHANNEL_ID      = int(os.getenv("ROBLOX_CHANNEL_ID",    1534679583947886594))
TWITCH_CHANNEL_ID      = int(os.getenv("TWITCH_CHANNEL_ID",    1517233263293497384))
RL_SHOP_CHANNEL_ID     = int(os.getenv("RL_SHOP_CHANNEL_ID",   1515508545418952734))
RL_UPDATES_CHANNEL_ID  = int(os.getenv("RL_UPDATES_CHANNEL_ID",1534708870352732241))
FN_UPDATES_CHANNEL_ID  = int(os.getenv("FN_UPDATES_CHANNEL_ID",1534724078584336384))

TWITCH_CLIENT_ID     = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")
twitch_access_token: str | None = None

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
    "wavepunk", "achieves",
]

last_roblox_version_hash: str | None = None
last_rl_patch_title:      str | None = None
current_rl_version                   = "v2.72"
last_fn_news_title:       str | None = None
current_fn_version                   = "v39.00"
currently_live: set[str]             = set()

# ==========================================
# 4. HELPERS
# ==========================================
async def send_rl_shop(channel: discord.TextChannel) -> None:
    embed = discord.Embed(
        title="🛒 BOUTIQUE ROCKET LEAGUE",
        description=(
            "La rotation quotidienne de la boutique est en ligne en jeu !\n\n"
            "*Pense à lancer Rocket League pour découvrir les nouveautés du jour.*"
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(name="🔄 Rotation", value="Actualisation quotidienne automatique", inline=False)
    embed.set_footer(text="L3X BOT - Alertes Rocket League")
    await channel.send(embed=embed)


async def get_twitch_token() -> str | None:
    global twitch_access_token
    if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
        return None
    try:
        async with bot.session.post(
            "https://id.twitch.tv/oauth2/token",
            params={
                "client_id": TWITCH_CLIENT_ID,
                "client_secret": TWITCH_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                twitch_access_token = data.get("access_token")
                return twitch_access_token
    except Exception as e:
        print(f"Erreur token Twitch : {e}")
    return None

# ==========================================
# 5. COMMANDES SLASH
# ==========================================
@bot.tree.command(name="shoprl", description="[ADMIN] Force l'affichage de la boutique Rocket League.")
@app_commands.checks.has_permissions(administrator=True)
async def slash_shoprl(interaction: discord.Interaction):
    await send_rl_shop(interaction.channel)
    await interaction.response.send_message("✅ Boutique envoyée.", ephemeral=True)


@bot.tree.command(name="versionrl", description="Affiche la version actuelle et les patch notes de Rocket League.")
async def slash_versionrl(interaction: discord.Interaction):
    patch_url = "https://www.rocketleague.com/news/tag/patch-notes"
    embed = discord.Embed(
        title="🎮 PATCH NOTES & VERSIONS ROCKET LEAGUE",
        description=(
            f"Version actuelle : **{current_rl_version}**\n\n"
            f"👉 **[Patch Notes officiels]({patch_url})**"
        ),
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} - L3X BOT")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="versionfn", description="Affiche les actualités et versions de Fortnite.")
async def slash_versionfn(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌀 ACTUALITÉS & VERSIONS FORTNITE",
        description=(
            f"Version récente : **{current_fn_version}**\n\n"
            "👉 **[Actualités officielles Fortnite](https://www.fortnite.com/news)**"
        ),
        color=discord.Color.purple(),
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} - L3X BOT")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="robloxversion", description="Donne la version officielle actuelle de Roblox.")
async def slash_robloxversion(interaction: discord.Interaction):
    url = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
    try:
        async with bot.session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                version_hash = data.get("clientVersionUpload", "Inconnue")
                embed = discord.Embed(
                    description=f"🎮 **Version actuelle de Roblox** : `{version_hash}`",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    "❌ Impossible de récupérer la version Roblox.", ephemeral=True
                )
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)


class AnimeView(discord.ui.View):
    def __init__(self, anime_name: str):
        super().__init__(timeout=180)
        query = urllib.parse.quote(anime_name)
        self.add_item(discord.ui.Button(
            label="📺 Lancer la recherche sur Anime-Sama",
            style=discord.ButtonStyle.link,
            url=f"https://anime-sama.to/catalogue/?search={query}",
        ))


@bot.tree.command(name="animesama", description="Recherche un animé sur Anime-Sama de façon privée.")
@app_commands.describe(nom="Nom de l'animé à rechercher")
async def animesama(interaction: discord.Interaction, nom: str):
    embed = discord.Embed(
        title="🌸 Recherche Anime-Sama",
        description=f"Résultat pour : **{nom}**",
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.add_field(
        name="💡 Astuce",
        value="Clique sur le bouton ci-dessous pour ouvrir la recherche en privé.",
        inline=False,
    )
    embed.set_footer(text="L3X BOT - Streaming Anime")
    await interaction.response.send_message(embed=embed, view=AnimeView(nom), ephemeral=True)


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = "❌ Tu n'as pas les permissions nécessaires." if isinstance(error, app_commands.MissingPermissions) \
          else f"❌ Erreur : {error}"
    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)

# ==========================================
# 6. TÂCHES DE FOND
# ==========================================
@tasks.loop(time=time(hour=20, minute=0, tzinfo=timezone.utc))
async def daily_rl_shop():
    channel = bot.get_channel(RL_SHOP_CHANNEL_ID)
    if channel:
        await send_rl_shop(channel)


@tasks.loop(minutes=5)
async def check_rocket_league_patches():
    global last_rl_patch_title, current_rl_version
    try:
        async with bot.session.get("https://www.rocketleague.com/news/rss/") as resp:
            if resp.status != 200:
                return
            root = ET.fromstring(await resp.text())
            for item in root.findall(".//item"):
                title = item.find("title").text or ""
                link  = item.find("link").text  or ""
                if not any(k in title.lower() for k in ("patch", "v2.", "update")):
                    continue
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
                            color=discord.Color.orange(),
                        )
                        embed.add_field(name="Lien officiel", value=link, inline=False)
                        embed.set_footer(text="Alerte automatique - L3X BOT")
                        await channel.send(content="@everyone", embed=embed)
                break
    except Exception as e:
        print(f"Erreur patch RL : {e}")


@tasks.loop(minutes=10)
async def check_fortnite_updates():
    global last_fn_news_title, current_fn_version
    try:
        async with bot.session.get("https://fortnite-api.com/v2/news/br") as resp:
            if resp.status != 200:
                return
            data = await resp.json()
            if data.get("status") != 200:
                return
            motd  = data["data"]["motds"][0]
            title = motd.get("title", "")
            body  = motd.get("body",  "")
            image = motd.get("image")
            match = re.search(r'v\d+\.\d+', f"{title} {body}", re.IGNORECASE)
            if match:
                current_fn_version = match.group(0)
            if last_fn_news_title is None:
                last_fn_news_title = title
            elif title != last_fn_news_title:
                last_fn_news_title = title
                channel = bot.get_channel(FN_UPDATES_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🌀 NOUVELLE ACTUALITÉ / MISE À JOUR FORTNITE !",
                        description=f"**{title}**\n\n{body}",
                        color=discord.Color.purple(),
                    )
                    if image:
                        embed.set_image(url=image)
                    embed.add_field(name="Version détectée", value=current_fn_version, inline=False)
                    embed.set_footer(text="Alerte Fortnite automatique - L3X BOT")
                    await channel.send(content="@everyone", embed=embed)
    except Exception as e:
        print(f"Erreur Fortnite : {e}")


@tasks.loop(minutes=5)
async def check_roblox_update():
    global last_roblox_version_hash
    try:
        async with bot.session.get(
            "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
        ) as resp:
            if resp.status != 200:
                return
            data         = await resp.json()
            version_hash = data.get("clientVersionUpload")
            if last_roblox_version_hash is None:
                last_roblox_version_hash = version_hash
            elif version_hash != last_roblox_version_hash:
                last_roblox_version_hash = version_hash
                channel = bot.get_channel(ROBLOX_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        description=f"🎮 **Nouvelle version Roblox déployée !**\n\nVersion : `{version_hash}`",
                        color=discord.Color.blue(),
                    )
                    embed.set_footer(text="Alerte Roblox automatique - L3X BOT")
                    await channel.send(content="@everyone", embed=embed)
    except Exception as e:
        print(f"Erreur Roblox : {e}")


@tasks.loop(minutes=3)
async def check_twitch_streams():
    global twitch_access_token
    if not twitch_access_token:
        await get_twitch_token()
        if not twitch_access_token:
            return

    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_access_token}",
    }
    active_this_check: set[str] = set()

    for i in range(0, len(STREAMERS), 100):
        chunk = STREAMERS[i:i + 100]
        url   = "https://api.twitch.tv/helix/streams?" + "&".join(f"user_login={s}" for s in chunk)
        try:
            async with bot.session.get(url, headers=headers) as resp:
                if resp.status == 401:
                    await get_twitch_token()
                    headers["Authorization"] = f"Bearer {twitch_access_token}"
                    continue
                if resp.status != 200:
                    continue
                for stream in (await resp.json()).get("data", []):
                    if "rocket league" not in stream.get("game_name", "").lower():
                        continue
                    login = stream["user_login"].lower()
                    active_this_check.add(login)
                    if login in currently_live:
                        continue
                    currently_live.add(login)
                    channel = bot.get_channel(TWITCH_CHANNEL_ID)
                    if not channel:
                        continue
                    stream_url = f"https://www.twitch.tv/{login}"
                    embed = discord.Embed(
                        title=f"🔴 {stream['user_name']} est en LIVE sur Rocket League !",
                        description=(
                            f"**Titre :** {stream['title']}\n"
                            f"**Spectateurs :** 👁️ {stream['viewer_count']}"
                        ),
                        url=stream_url,
                        color=discord.Color.purple(),
                    )
                    embed.set_thumbnail(
                        url=stream["thumbnail_url"].replace("{width}", "320").replace("{height}", "180")
                    )
                    embed.add_field(name="Lien du Stream", value=stream_url, inline=False)
                    await channel.send(
                        content=f"🔴 **{stream['user_name']}** est actuellement en direct !",
                        embed=embed,
                    )
        except Exception as e:
            print(f"Erreur Twitch : {e}")

    currently_live.difference_update(currently_live - active_this_check)

# ==========================================
# 7. DÉMARRAGE
# ==========================================
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ Aucun token Discord trouvé dans les variables d'environnement.")
