import os, json, asyncio, re, string, secrets, urllib.parse, tempfile, threading, time as time_module
import xml.etree.ElementTree as ET
from threading import Thread
from datetime import datetime, timedelta, timezone, time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask, request, jsonify

# ══════════════════════════════════════════════════════════════════
# 0. PERSISTANCE CLÉ & VERROUILLAGE THREAD-SAFE
# ══════════════════════════════════════════════════════════════════
KEY_STORE_FILE = "key_store.json"
_store_lock = threading.Lock()

def _load_store() -> dict:
    try:
        with open(KEY_STORE_FILE, "r") as f:
            raw = json.load(f)
        for uid, data in raw.items():
            data["expires"] = datetime.fromisoformat(data["expires"])
        return raw
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return {}

def _save_store(store: dict) -> None:
    serializable = {
        uid: {
            "key":      d["key"],
            "expires":  d["expires"].isoformat(),
            "username": d["username"],
        }
        for uid, d in store.items()
    }
    dir_ = os.path.dirname(os.path.abspath(KEY_STORE_FILE)) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp") as tmp:
        json.dump(serializable, tmp, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, KEY_STORE_FILE)

key_store: dict[str, dict] = _load_store()

def generate_key(length: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def cleanup_expired_keys() -> None:
    with _store_lock:
        now = datetime.now(timezone.utc)
        expired = [uid for uid, d in key_store.items() if d["expires"] < now]
        for uid in expired:
            del key_store[uid]
        if expired:
            _save_store(key_store)

# ══════════════════════════════════════════════════════════════════
# 1. FLASK — KEEP-ALIVE + VALIDATION
# ══════════════════════════════════════════════════════════════════
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "🚀 L3X BOT opérationnel."

@flask_app.route("/validate_key", methods=["GET"])
def validate_key():
    key = request.args.get("key", "").strip()
    print(f"[DEBUG FLASK] Requête de validation reçue pour la clé : '{key}'")
    
    if not key:
        return jsonify({"valid": False, "reason": "Aucune clé fournie"}), 400

    now = datetime.now(timezone.utc)
    with _store_lock:
        for user_id, data in key_store.items():
            if data["key"] == key:
                if data["expires"] > now:
                    remaining = data["expires"] - now
                    print(f"[DEBUG FLASK] Succès ! Clé valide pour l'utilisateur {data['username']}")
                    return jsonify({
                        "valid":             True,
                        "user":              data["username"],
                        "expires_in_seconds": int(remaining.total_seconds()),
                    })
                print(f"[DEBUG FLASK] Échec : Clé expirée pour {data['username']}")
                return jsonify({"valid": False, "reason": "Clé expirée"})

    print(f"[DEBUG FLASK] Échec : Clé introuvable dans le key_store")
    return jsonify({"valid": False, "reason": "Clé invalide"})

@flask_app.route("/health")
def health():
    with _store_lock:
        keys_count = len(key_store)
    return jsonify({"status": "ok", "keys_active": keys_count})

def _run_flask() -> None:
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

Thread(target=_run_flask, daemon=True).start()

# ══════════════════════════════════════════════════════════════════
# 2. CONFIG DISCORD
# ══════════════════════════════════════════════════════════════════
DISCORD_INVITE = "https://discord.gg/764AW7aSKS"

ROBLOX_CHANNEL_ID      = int(os.getenv("ROBLOX_CHANNEL_ID",      1534679583947886594))
TWITCH_CHANNEL_ID      = int(os.getenv("TWITCH_CHANNEL_ID",      1517233263293497384))
RL_SHOP_CHANNEL_ID    = int(os.getenv("RL_SHOP_CHANNEL_ID",    1515508545418952734))
RL_UPDATES_CHANNEL_ID = int(os.getenv("RL_UPDATES_CHANNEL_ID", 1534708870352732241))
FN_UPDATES_CHANNEL_ID = int(os.getenv("FN_UPDATES_CHANNEL_ID", 1534724078584336384))

KEY_CHANNEL_ID        = 1534835833922785431
ROBLOX_VERIFY_CHANNEL_ID = 1518014650829242388
ROBLOX_ROLE_ID        = 1518016527499132948
ROBLOX_PROFILE_URL    = "https://www.roblox.com/users/1353605326/profile"

TWITCH_CLIENT_ID     = os.getenv("TWITCH_CLIENT_ID")
TWITCH_CLIENT_SECRET = os.getenv("TWITCH_CLIENT_SECRET")

STREAMERS = [
    "mawkzy_","rocketbaguette","fuury_off","atowwwww","kaydop","vatira",
    "zenrll","alpha54","chausette45","fairy_peak","extra","saizen","radosin",
    "juicy","seikoo","monkeymoon","itachi","aztral","ferra","eversax",
    "exotiik","dralii","lecheps","payriixx","poachimpa","kaokor","rasmelthor",
    "shogunfr","yukeofr","rocketleague","squishymuffinz","lethamyr","apparentlyjack",
    "retals","arsenal","garrettg","ayyjayy","jstn","daniel","beastmode","comm",
    "firstkiller","chronic","lj","mist","cheese","hockser","percy","chicago",
    "rizzo","athena","jonsandman","sunlesskhan","musty","cbell","thanovic",
    "wayton","chiefbeef_rl","evample","frontalpanda","pulsemk","pulsetemple",
    "hivise","cbellrl","woody","spookluke","virge","gibbs","johnnyboi_i",
    "dazerin","corelli","turtle","stumpy","cole","jannlpzz","rosdri_twitch",
    "stake","crr","atomik","dorito","marc_by_8","rezears","kairiu","tox",
    "trk511__","rw9","kiileerrz","nwpo","ahmad","okhali_d","venom","smw",
    "m7sn","t7lm","catalysm","nass","oaly","oski","joreuz","rise","archie",
    "scrubkilla","yukeo","yanxnz","lostt","kv1","motta","aztromick","caard",
    "math","droppz","muiricle","henkovic","jzr","ganer","kuxir97","maktuf",
    "wavepunk","achieves",
]

# ══════════════════════════════════════════════════════════════════
# 3. BOT
# ══════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True

class RobloxVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        self.add_item(discord.ui.Button(
            label="🔗 S'abonner à mon profil Roblox",
            style=discord.ButtonStyle.link,
            url=ROBLOX_PROFILE_URL,
            row=0
        ))
        
        self.show_role_btn = discord.ui.Button(
            label="🔄 J'ai visité le profil",
            style=discord.ButtonStyle.blurple,
            custom_id="show_role_btn_persistent",
            row=0
        )
        self.show_role_btn.callback = self.show_role_callback
        self.add_item(self.show_role_btn)

        self.verify_btn = discord.ui.Button(
            label="✅ Je me suis abonné, je veux mon rôle",
            style=discord.ButtonStyle.green,
            custom_id="verify_roblox_btn_persistent",
            row=1
        )
        self.verify_btn.callback = self.verify_callback

    async def show_role_callback(self, interaction: discord.Interaction):
        self.remove_item(self.show_role_btn)
        self.add_item(self.verify_btn)
        await interaction.response.edit_message(view=self)

    async def verify_callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return

        role = guild.get_role(ROBLOX_ROLE_ID)
        if not role:
            await interaction.response.send_message("❌ Erreur : Rôle introuvable sur le serveur.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.response.send_message("⚠️ Tu possèdes déjà ce rôle !", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"✅ Merci pour l'abonnement ! Le rôle **{role.name}** t'a été attribué avec succès.",
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Une erreur est survenue : {e}", ephemeral=True)


class L3XBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None
        self._twitch_token: str | None = None
        self._twitch_token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.add_view(RobloxVerifyView())
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
        print(f"✅ {self.user} connecté (ID: {self.user.id})")
        try:
            synced = await self.tree.sync()
            print(f"🔄 {len(synced)} commandes slash synchronisées")
        except Exception as e:
            print(f"❌ Sync slash : {e}")

bot = L3XBot()

# ══════════════════════════════════════════════════════════════════
# 4. ÉTAT GLOBAL
# ══════════════════════════════════════════════════════════════════
last_roblox_version_hash: str | None = None
last_rl_patch_title:      str | None = None
current_rl_version:        str        = "v2.72"
last_fn_news_title:        str | None = None
current_fn_version:        str        = "v39.00"
currently_live:            set[str]   = set()

# ══════════════════════════════════════════════════════════════════
# 5. HELPERS
# ══════════════════════════════════════════════════════════════════
async def get_twitch_token() -> str | None:
    async with bot._token_lock:
        if bot._twitch_token and time_module.monotonic() < bot._twitch_token_expiry - 60:
            return bot._twitch_token
        if not TWITCH_CLIENT_ID or not TWITCH_CLIENT_SECRET:
            return None
        try:
            async with bot.session.post(
                "https://id.twitch.tv/oauth2/token",
                params={
                    "client_id":     TWITCH_CLIENT_ID,
                    "client_secret": TWITCH_CLIENT_SECRET,
                    "grant_type":    "client_credentials",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bot._twitch_token         = data["access_token"]
                    bot._twitch_token_expiry  = time_module.monotonic() + data.get("expires_in", 3600)
                    return bot._twitch_token
                print(f"Token Twitch HTTP {resp.status}")
        except Exception as e:
            print(f"Token Twitch erreur : {e}")
    return None

async def send_rl_shop(channel: discord.TextChannel) -> None:
    embed = discord.Embed(
        title="🛒 BOUTIQUE ROCKET LEAGUE",
        description=(
            "La rotation quotidienne est en ligne en jeu !\n\n"
            "*Lance Rocket League pour découvrir les nouveautés.*"
        ),
        color=discord.Color.blue(),
    )
    embed.add_field(name="🔄 Rotation", value="Actualisation quotidienne automatique", inline=False)
    embed.set_footer(text="L3X BOT — Alertes Rocket League")
    await channel.send(embed=embed)

# ══════════════════════════════════════════════════════════════════
# 6. COMMANDES SLASH
# ══════════════════════════════════════════════════════════════════

@bot.tree.command(name="key", description="Génère une clé d'accès unique valable 24h.")
async def slash_key(interaction: discord.Interaction):
    if interaction.channel_id != KEY_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Tu ne peux utiliser cette commande que dans le salon <#{KEY_CHANNEL_ID}> !",
            ephemeral=True
        )
        return

    cleanup_expired_keys()
    user_id = str(interaction.user.id)
    now     = datetime.now(timezone.utc)

    with _store_lock:
        if user_id in key_store and key_store[user_id]["expires"] > now:
            existing  = key_store[user_id]
            remaining = existing["expires"] - now
            hours     = int(remaining.total_seconds() // 3600)
            minutes   = int((remaining.total_seconds() % 3600) // 60)
            embed = discord.Embed(
                title="🔑 Clé déjà active",
                description=f"Tu as déjà une clé valide.\n\n**Ta clé :**\n```\n{existing['key']}\n```",
                color=discord.Color.orange(),
            )
            embed.add_field(name="⏱️ Expiration", value=f"Expire dans **{hours}h {minutes}min**", inline=False)
            embed.set_footer(text="L3X BOT — Système de clés")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        new_key = generate_key(20)
        expires = now + timedelta(hours=24)
        key_store[user_id] = {"key": new_key, "expires": expires, "username": str(interaction.user)}
        _save_store(key_store)

    print(f"🔑 [NOUVELLE CLÉ] Utilisateur : {interaction.user} (ID: {user_id}) | Clé : {new_key}")

    embed = discord.Embed(
        title="✅ Nouvelle clé générée !",
        description=(
            f"**Ta clé :**\n```\n{new_key}\n```\n"
            "Copie-la et colle-la dans le script Roblox."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(name="⏱️ Durée", value="**24 heures**", inline=False)
    embed.add_field(name="⚠️ Important", value="Clé personnelle — ne pas partager.", inline=False)
    embed.set_footer(text="L3X BOT — Système de clés")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="linkroblox", description="Abonne-toi à mon profil Roblox pour récupérer ton rôle.")
async def slash_linkroblox(interaction: discord.Interaction):
    if interaction.channel_id != ROBLOX_VERIFY_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Tu ne peux utiliser cette commande que dans le salon <#{ROBLOX_VERIFY_CHANNEL_ID}> !",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🤖 Vérification Roblox & Abonnement",
        description=(
            "Pour obtenir ton rôle exclusif sur le serveur :\n\n"
            "1. Clique sur le bouton ci-dessous pour t'abonner à mon profil Roblox.\n"
            "2. Une fois fait, clique sur **🔄 J'ai visité le profil** pour afficher le bouton de réclamation !"
        ),
        color=discord.Color.blue(),
    )
    embed.set_footer(text="L3X BOT — Vérification")
    
    await interaction.response.send_message(
        embed=embed, 
        view=RobloxVerifyView()
    )

@bot.tree.command(name="shoprl", description="[ADMIN] Force l'affichage de la boutique Rocket League.")
@app_commands.checks.has_permissions(administrator=True)
async def slash_shoprl(interaction: discord.Interaction):
    await send_rl_shop(interaction.channel)
    await interaction.response.send_message("✅ Boutique envoyée.", ephemeral=True)

@bot.tree.command(name="versionrl", description="Affiche la version actuelle et les patch notes de Rocket League.")
async def slash_versionrl(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 PATCH NOTES & VERSIONS ROCKET LEAGUE",
        description=(
            f"Version actuelle : **{current_rl_version}**\n\n"
            "👉 **[Patch Notes officiels](https://www.rocketleague.com/news/tag/patch-notes)**"
        ),
        color=discord.Color.orange(),
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} — L3X BOT")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="versionfn", description="Affiche les actualités et version de Fortnite.")
async def slash_versionfn(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🌀 ACTUALITÉS & VERSIONS FORTNITE",
        description=(
            f"Version récente : **{current_fn_version}**\n\n"
            "👉 **[Actualités officielles Fortnite](https://www.fortnite.com/news)**"
        ),
        color=discord.Color.purple(),
    )
    embed.set_footer(text=f"Demandé par {interaction.user.name} — L3X BOT")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="robloxversion", description="Donne la version officielle actuelle de Roblox.")
async def slash_robloxversion(interaction: discord.Interaction):
    url = "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer"
    try:
        async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                data    = await resp.json()
                version = data.get("clientVersionUpload", "Inconnue")
                embed   = discord.Embed(
                    description=f"🎮 **Version actuelle de Roblox**\n\n`{version}`",
                    color=discord.Color.blue(),
                )
                await interaction.response.send_message(embed=embed)
            else:
                await interaction.response.send_message(
                    f"❌ HTTP {resp.status}", ephemeral=True
                )
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)

class AnimeView(discord.ui.View):
    def __init__(self, anime_name: str):
        super().__init__(timeout=180)
        query = urllib.parse.quote(anime_name, safe="")
        self.add_item(discord.ui.Button(
            label="📺 Rechercher sur Anime-Sama",
            style=discord.ButtonStyle.link,
            url=f"https://anime-sama.to/catalogue/?search={query}",
        ))

@bot.tree.command(name="animesama", description="Recherche un animé sur Anime-Sama.")
@app_commands.describe(nom="Nom de l'animé")
async def slash_animesama(interaction: discord.Interaction, nom: str):
    embed = discord.Embed(
        title="🌸 Recherche Anime-Sama",
        description=f"Résultat pour : **{nom}**",
        color=discord.Color.from_rgb(255, 105, 180),
    )
    embed.add_field(name="💡 Astuce", value="Clique pour ouvrir la recherche en privé.", inline=False)
    embed.set_footer(text="L3X BOT — Streaming Anime")
    await interaction.response.send_message(embed=embed, view=AnimeView(nom), ephemeral=True)

@bot.tree.command(name="keys", description="[ADMIN] Liste toutes les clés actives.")
@app_commands.checks.has_permissions(administrator=True)
async def slash_keys(interaction: discord.Interaction):
    cleanup_expired_keys()
    now = datetime.now(timezone.utc)
    with _store_lock:
        if not key_store:
            await interaction.response.send_message("Aucune clé active.", ephemeral=True)
            return

        lines = []
        for uid, data in key_store.items():
            remaining = data["expires"] - now
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            lines.append(f"`{data['key']}` — {data['username']} — expire dans {h}h{m}m")
        count = len(key_store)

    embed = discord.Embed(
        title=f"🔑 {count} clé(s) active(s)",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="L3X BOT — Admin")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="revokekey", description="[ADMIN] Révoque la clé d'un utilisateur.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(user="L'utilisateur dont révoquer la clé")
async def slash_revokekey(interaction: discord.Interaction, user: discord.Member):
    uid = str(user.id)
    with _store_lock:
        if uid in key_store:
            del key_store[uid]
            _save_store(key_store)
            revoked = True
        else:
            revoked = False

    if revoked:
        await interaction.response.send_message(f"✅ Clé de {user} révoquée.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ {user} n'a pas de clé active.", ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    msg = (
        "❌ Permissions insuffisantes."
        if isinstance(error, app_commands.MissingPermissions)
        else f"❌ Erreur : {error}"
    )
    if not interaction.response.is_done():
        await interaction.response.send_message(msg, ephemeral=True)
    else:
        await interaction.followup.send(msg, ephemeral=True)

# ══════════════════════════════════════════════════════════════════
# 7. LOOPS AUTOMATIQUES
# ══════════════════════════════════════════════════════════════════

@tasks.loop(time=time(hour=20, minute=0, tzinfo=timezone.utc))
async def daily_rl_shop():
    channel = bot.get_channel(RL_SHOP_CHANNEL_ID)
    if channel:
        await send_rl_shop(channel)

@tasks.loop(minutes=5)
async def check_rocket_league_patches():
    global last_rl_patch_title, current_rl_version
    try:
        async with bot.session.get(
            "https://www.rocketleague.com/news/rss/",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return
            root = ET.fromstring(await resp.text())

        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el  = item.find("link")
            if title_el is None or link_el is None:
                continue
            title = (title_el.text or "").strip()
            link  = (link_el.text  or "").strip()
            if not any(k in title.lower() for k in ("patch", "v2.", "update")):
                continue

            match = re.search(r"v2\.\d+", title, re.IGNORECASE)
            if match:
                current_rl_version = match.group(0)

            if last_rl_patch_title is None:
                last_rl_patch_title = title
                return
            if title == last_rl_patch_title:
                return

            last_rl_patch_title = title
            channel = bot.get_channel(RL_UPDATES_CHANNEL_ID)
            if not channel:
                return

            embed = discord.Embed(
                title=f"🚀 NOUVELLE VERSION ({current_rl_version}) ROCKET LEAGUE !",
                description=f"**{title}**",
                url=link,
                color=discord.Color.orange(),
            )
            embed.add_field(name="Lien officiel", value=link, inline=False)
            embed.set_footer(text="Alerte automatique — L3X BOT")
            await channel.send(content="@everyone", embed=embed)
            return

    except asyncio.TimeoutError:
        print("Timeout patch RL")
    except ET.ParseError as e:
        print(f"XML malformé RL RSS : {e}")
    except Exception as e:
        print(f"Erreur patch RL : {e}")

@tasks.loop(minutes=10)
async def check_fortnite_updates():
    global last_fn_news_title, current_fn_version
    try:
        async with bot.session.get(
            "https://fortnite-api.com/v2/news/br",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return
            data = await resp.json()

        if data.get("status") != 200:
            return
        motds = data.get("data", {}).get("motds", [])
        if not motds:
            return

        motd  = motds[0]
        title = (motd.get("title") or "").strip()
        body  = (motd.get("body")  or "").strip()
        image = motd.get("image")

        match = re.search(r"v\d+\.\d+", f"{title} {body} {motd.get('tabTitle','')}", re.IGNORECASE)
        if match:
            current_fn_version = match.group(0)

        if last_fn_news_title is None:
            last_fn_news_title = title
            return
        if title == last_fn_news_title:
            return

        last_fn_news_title = title
        channel = bot.get_channel(FN_UPDATES_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            title="🌀 NOUVELLE ACTUALITÉ / MISE À JOUR FORTNITE !",
            description=f"**{title}**\n\n{body}",
            color=discord.Color.purple(),
        )
        if image:
            embed.set_image(url=image)
        embed.add_field(name="Version détectée", value=current_fn_version, inline=False)
        embed.set_footer(text="Alerte Fortnite — L3X BOT")
        await channel.send(content="@everyone", embed=embed)

    except asyncio.TimeoutError:
        print("Timeout Fortnite")
    except Exception as e:
        print(f"Erreur Fortnite : {e}")

@tasks.loop(minutes=5)
async def check_roblox_update():
    global last_roblox_version_hash
    try:
        async with bot.session.get(
            "https://clientsettingscdn.roblox.com/v2/client-version/WindowsPlayer",
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                return
            data = await resp.json()

        version_hash = data.get("clientVersionUpload", "").lower()
        if not version_hash:
            return
        if last_roblox_version_hash is None:
            last_roblox_version_hash = version_hash
            return
        if version_hash == last_roblox_version_hash:
            return

        last_roblox_version_hash = version_hash
        channel = bot.get_channel(ROBLOX_CHANNEL_ID)
        if not channel:
            return

        embed = discord.Embed(
            description=f"🎮 **Nouvelle version Roblox déployée !**\n\n`{version_hash}`",
            color=discord.Color.blue(),
        )
        embed.set_footer(text="Alerte Roblox — L3X BOT")
        await channel.send(content="@everyone", embed=embed)

    except asyncio.TimeoutError:
        print("Timeout Roblox")
    except Exception as e:
        print(f"Erreur Roblox : {e}")

@tasks.loop(minutes=3)
async def check_twitch_streams():
    token = await get_twitch_token()
    if not token:
        return

    headers = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
    active_this_check: set[str] = set()
    all_ok = True

    for i in range(0, len(STREAMERS), 100):
        chunk  = STREAMERS[i:i + 100]
        params = [("user_login", s) for s in chunk]
        streams: list = []

        for attempt in range(2):
            try:
                async with bot.session.get(
                    "https://api.twitch.tv/helix/streams",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 401 and attempt == 0:
                        token = await get_twitch_token()
                        if not token:
                            all_ok = False
                            break
                        headers["Authorization"] = f"Bearer {token}"
                        continue
                    if resp.status != 200:
                        print(f"Twitch HTTP {resp.status}")
                        all_ok = False
                        break
                    streams = (await resp.json()).get("data", [])
                    break
            except asyncio.TimeoutError:
                print("Timeout Twitch chunk")
                all_ok = False
                break
            except Exception as e:
                print(f"Erreur Twitch chunk : {e}")
                all_ok = False
                break

        for stream in streams:
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

            thumb = (
                stream["thumbnail_url"]
                .replace("{width}", "320")
                .replace("{height}", "180")
            )
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
            embed.set_thumbnail(url=thumb)
            embed.add_field(name="Lien", value=stream_url, inline=False)
            await channel.send(
                content=f"🔴 **{stream['user_name']}** est en direct !",
                embed=embed,
            )

    if all_ok:
        currently_live.intersection_update(active_this_check)

# ══════════════════════════════════════════════════════════════════
# 8. DÉMARRAGE
# ══════════════════════════════════════════════════════════════════
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN manquant dans les variables d'environnement.")

bot.run(TOKEN)
