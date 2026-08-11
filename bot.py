import os, json, asyncio, re, string, secrets, urllib.parse, time as time_module
import xml.etree.ElementTree as ET
import tempfile
import threading
from threading import Thread
from datetime import datetime, timedelta, timezone, time

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from flask import Flask, request, jsonify

# ══════════════════════════════════════════════════════════════════
# 0. PERSISTANCE CLÉ
# ══════════════════════════════════════════════════════════════════
KEY_STORE_FILE = "key_store.json"
_store_lock    = threading.Lock()

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
    now = datetime.now(timezone.utc)
    with _store_lock:
        expired = [uid for uid, d in key_store.items() if d["expires"] < now]
        for uid in expired:
            del key_store[uid]
        if expired:
            _save_store(key_store)

# ══════════════════════════════════════════════════════════════════
# 0b. PERSISTANCE PARTENAIRES
# ══════════════════════════════════════════════════════════════════
PARTNERS_FILE = "partners.json"
_partner_lock = threading.Lock()

def _load_partners() -> list[dict]:
    try:
        with open(PARTNERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def _save_partners(data: list[dict]) -> None:
    dir_ = os.path.dirname(os.path.abspath(PARTNERS_FILE)) or "."
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp",
                                     encoding="utf-8") as tmp:
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, PARTNERS_FILE)

partners: list[dict] = _load_partners()
_partner_rotation_index: int = 0

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
    if not key:
        return jsonify({"valid": False, "reason": "Aucune clé fournie"}), 400
    now = datetime.now(timezone.utc)
    with _store_lock:
        for user_id, data in key_store.items():
            if data["key"] == key:
                if data["expires"] > now:
                    remaining = data["expires"] - now
                    return jsonify({
                        "valid":              True,
                        "user":               data["username"],
                        "expires_in_seconds": int(remaining.total_seconds()),
                    })
                return jsonify({"valid": False, "reason": "Clé expirée"})
    return jsonify({"valid": False, "reason": "Clé invalide"})

@flask_app.route("/health")
def health():
    with _store_lock:
        keys_count = len(key_store)
    with _partner_lock:
        partner_count = len(partners)
    return jsonify({"status": "ok", "keys_active": keys_count, "partners": partner_count})

def _run_flask() -> None:
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

Thread(target=_run_flask, daemon=True).start()

# ══════════════════════════════════════════════════════════════════
# 2. CONFIG DISCORD
# ══════════════════════════════════════════════════════════════════
DISCORD_INVITE = "https://discord.gg/DbHsGBckyc"
SERVER_NAME    = "L3X"

ROBLOX_CHANNEL_ID        = int(os.getenv("ROBLOX_CHANNEL_ID",     1534679583947886594))
TWITCH_CHANNEL_ID        = int(os.getenv("TWITCH_CHANNEL_ID",     1517233263293497384))
RL_SHOP_CHANNEL_ID       = int(os.getenv("RL_SHOP_CHANNEL_ID",    1515508545418952734))
RL_UPDATES_CHANNEL_ID    = int(os.getenv("RL_UPDATES_CHANNEL_ID", 1534708870352732241))
FN_UPDATES_CHANNEL_ID    = int(os.getenv("FN_UPDATES_CHANNEL_ID", 1534724078584336384))

KEY_CHANNEL_ID           = 1534835833922785431
ROBLOX_VERIFY_CHANNEL_ID = 1518014650829242388
ROBLOX_ROLE_ID           = 1518016527499132948
ROBLOX_PROFILE_URL       = "https://www.roblox.com/users/1353605326/profile"

DISBOARD_BOT_ID    = 302050872383242240
BUMP_CHANNEL_ID    = int(os.getenv("BUMP_CHANNEL_ID",    0))
PARTNER_CHANNEL_ID = int(os.getenv("PARTNER_CHANNEL_ID", 0))
BUMP_INTERVAL_SEC  = 7200

ADMIN_ROLE_IDS: set[int] = {
    int(os.getenv("ROLE_FONDATEUR",      0)),
    int(os.getenv("ROLE_FONDATEUR_PLUS", 0)),
    int(os.getenv("ROLE_COOWNER",        0)),
    int(os.getenv("ROLE_ADMIN",          0)),
}

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
# 3. ÉTAT VÉRIFICATION ROBLOX
# ══════════════════════════════════════════════════════════════════
pending_verifications: dict[str, dict] = {}
_verif_lock = threading.Lock()

def generate_verif_code() -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    return f"L3X-{suffix}"

# ══════════════════════════════════════════════════════════════════
# 4. HELPER ADMIN
# ══════════════════════════════════════════════════════════════════
def _is_admin(interaction: discord.Interaction) -> bool:
    if not interaction.guild or not interaction.user:
        return False
    if interaction.user.guild_permissions.administrator:
        return True
    user_role_ids = {role.id for role in interaction.user.roles}
    return bool(user_role_ids & ADMIN_ROLE_IDS)

# ══════════════════════════════════════════════════════════════════
# 5. BOT
# ══════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True

class L3XBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.session: aiohttp.ClientSession | None = None
        self._twitch_token: str | None = None
        self._twitch_token_expiry: float = 0.0
        self._token_lock = asyncio.Lock()
        self.last_bump_success: datetime | None = None
        self.next_bump_at: datetime | None = None

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()
        self.add_view(RobloxVerifyConfirmView())
        check_roblox_update.start()
        check_rocket_league_patches.start()
        check_fortnite_updates.start()
        check_twitch_streams.start()
        daily_rl_shop.start()
        auto_bump.start()
        rotate_partner_embeds.start()

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
# 6. ÉTAT GLOBAL
# ══════════════════════════════════════════════════════════════════
last_roblox_version_hash: str | None = None
last_rl_patch_title:      str | None = None
current_rl_version:        str        = "v2.72"
last_fn_news_title:        str | None = None
current_fn_version:        str        = "v39.00"
currently_live:            set[str]   = set()

# ══════════════════════════════════════════════════════════════════
# 7. HELPERS
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
                    bot._twitch_token        = data["access_token"]
                    bot._twitch_token_expiry = (
                        time_module.monotonic() + data.get("expires_in", 3600)
                    )
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

async def roblox_get_user_by_username(username: str) -> dict | None:
    url     = "https://users.roblox.com/v1/usernames/users"
    payload = {"usernames": [username], "excludeBannedUsers": True}
    try:
        async with bot.session.post(
            url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            if resp.status != 200:
                return None
            data  = await resp.json()
            users = data.get("data", [])
            return users[0] if users else None
    except Exception as e:
        print(f"Roblox username lookup erreur : {e}")
        return None

async def roblox_get_user_description(roblox_id: int) -> str | None:
    url = f"https://users.roblox.com/v1/users/{roblox_id}"
    try:
        async with bot.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                return None
            data = await resp.json()
            return data.get("description", "")
    except Exception as e:
        print(f"Roblox bio fetch erreur : {e}")
        return None

async def _post_partner_embed(channel: discord.TextChannel, partner: dict) -> None:
    embed = discord.Embed(
        title=f"🤝 Partenaire — {partner['name']}",
        description=partner["description"],
        url=partner["invite"],
        color=discord.Color.gold(),
    )
    embed.add_field(name="🔗 Rejoindre", value=partner["invite"], inline=False)
    if partner.get("banner"):
        embed.set_image(url=partner["banner"])
    embed.set_footer(text=f"Ajouté par {partner['added_by']} — L3X BOT")
    await channel.send(embed=embed)

# ══════════════════════════════════════════════════════════════════
# 8. LINKROBLOX — MODAL + VUE DE CONFIRMATION
# ══════════════════════════════════════════════════════════════════
class RobloxUsernameModal(discord.ui.Modal, title="Vérification Roblox"):
    username = discord.ui.TextInput(
        label="Ton username Roblox",
        placeholder="ex: Builderman",
        min_length=3,
        max_length=20,
        required=True,
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        roblox_user = await roblox_get_user_by_username(self.username.value.strip())
        if not roblox_user:
            await interaction.followup.send(
                "❌ Username Roblox introuvable. Vérifie l'orthographe et réessaie.",
                ephemeral=True,
            )
            return

        roblox_id       = roblox_user["id"]
        roblox_username = roblox_user["name"]
        discord_uid     = str(interaction.user.id)
        code            = generate_verif_code()
        expires         = datetime.now(timezone.utc) + timedelta(minutes=15)

        with _verif_lock:
            pending_verifications[discord_uid] = {
                "roblox_id":       roblox_id,
                "roblox_username": roblox_username,
                "code":            code,
                "expires":         expires,
            }

        embed = discord.Embed(
            title="🔐 Étape 2 — Place le code dans ta bio Roblox",
            description=(
                f"Compte détecté : **{roblox_username}** (`{roblox_id}`)\n\n"
                f"**1.** Va sur ton profil Roblox → **[Modifier ma bio]({ROBLOX_PROFILE_URL})**\n"
                f"**2.** Colle ce code **exactement** dans ta bio :\n\n"
                f"```\n{code}\n```\n"
                f"**3.** Sauvegarde, puis clique sur **✅ Vérifier** ci-dessous.\n\n"
                f"⏱️ Ce code expire dans **15 minutes**."
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="L3X BOT — Vérification Roblox")
        await interaction.followup.send(
            embed=embed, view=RobloxVerifyConfirmView(), ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        print(f"RobloxUsernameModal erreur : {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ Erreur inattendue.", ephemeral=True)
        else:
            await interaction.followup.send("❌ Erreur inattendue.", ephemeral=True)


class RobloxVerifyConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="✅ Vérifier",
        style=discord.ButtonStyle.green,
        custom_id="roblox_verify_confirm_v2",
    )
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)

        discord_uid = str(interaction.user.id)
        now         = datetime.now(timezone.utc)

        with _verif_lock:
            pending = pending_verifications.get(discord_uid)

        if not pending:
            await interaction.followup.send(
                "❌ Aucune vérification en attente. Relance `/linkroblox`.", ephemeral=True
            )
            return

        if pending["expires"] < now:
            with _verif_lock:
                pending_verifications.pop(discord_uid, None)
            await interaction.followup.send(
                "❌ Code expiré. Relance `/linkroblox` pour un nouveau code.", ephemeral=True
            )
            return

        bio = await roblox_get_user_description(pending["roblox_id"])
        if bio is None:
            await interaction.followup.send(
                "❌ Impossible de lire ta bio Roblox. Réessaie dans quelques secondes.",
                ephemeral=True,
            )
            return

        if pending["code"] not in bio:
            await interaction.followup.send(
                f"❌ Code **{pending['code']}** introuvable dans ta bio Roblox.\n\n"
                "Assure-toi de l'avoir copié exactement et sauvegardé, puis réessaie.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Erreur serveur.", ephemeral=True)
            return

        role = guild.get_role(ROBLOX_ROLE_ID)
        if not role:
            await interaction.followup.send("❌ Rôle introuvable sur le serveur.", ephemeral=True)
            return

        try:
            await interaction.user.add_roles(role, reason="Vérification Roblox bio réussie")
        except discord.Forbidden:
            await interaction.followup.send(
                "❌ Le bot n'a pas les permissions pour attribuer ce rôle.", ephemeral=True
            )
            return

        with _verif_lock:
            pending_verifications.pop(discord_uid, None)

        embed = discord.Embed(
            title="✅ Vérification réussie !",
            description=(
                f"Compte Roblox **{pending['roblox_username']}** vérifié.\n"
                f"Le rôle **{role.name}** t'a été attribué.\n\n"
                "Tu peux retirer le code de ta bio si tu veux."
            ),
            color=discord.Color.green(),
        )
        embed.set_footer(text="L3X BOT — Vérification Roblox")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="🔄 Changer de compte",
        style=discord.ButtonStyle.grey,
        custom_id="roblox_verify_restart_v2",
    )
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        discord_uid = str(interaction.user.id)
        with _verif_lock:
            pending_verifications.pop(discord_uid, None)
        await interaction.response.send_modal(RobloxUsernameModal())

# ══════════════════════════════════════════════════════════════════
# 9. ON_MEMBER_JOIN — DM de bienvenue
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_member_join(member: discord.Member):
    try:
        embed = discord.Embed(
            title=f"👋 Bienvenue sur le serveur {SERVER_NAME} !",
            description=(
                "Merci d'avoir rejoint la communauté.\n\n"
                "🔧 **Outils disponibles :** OSINT, CSINT et bien plus.\n"
                "🎮 **Rocket League FR** — alertes live, boutique, mises à jour.\n"
                f"📨 **Partage le serveur à tes amis :** {DISCORD_INVITE}"
            ),
            color=discord.Color.blurple(),
        )
        embed.set_footer(text="L3X BOT — Bienvenue")
        await member.send(embed=embed)
    except discord.Forbidden:
        pass

# ══════════════════════════════════════════════════════════════════
# 10. ON_MESSAGE — Détection réponse Disboard
# ══════════════════════════════════════════════════════════════════
@bot.event
async def on_message(message: discord.Message):
    if message.author.id == DISBOARD_BOT_ID and message.embeds:
        for embed in message.embeds:
            desc = (embed.description or "").lower()
            if "bump done" in desc or "bumped" in desc:
                confirm = discord.Embed(
                    title="✅ Serveur bumped sur Disboard !",
                    description=(
                        f"**{SERVER_NAME}** est maintenant mis en avant.\n\n"
                        f"📨 Partage le lien : {DISCORD_INVITE}\n"
                        "⏱️ Prochain bump automatique dans **2 heures**."
                    ),
                    color=discord.Color.green(),
                )
                confirm.set_footer(text="L3X BOT — Bump Disboard")
                await message.channel.send(embed=confirm)
                bot.last_bump_success = datetime.now(timezone.utc)
                bot.next_bump_at      = bot.last_bump_success + timedelta(seconds=BUMP_INTERVAL_SEC)
                return

    await bot.process_commands(message)

# ══════════════════════════════════════════════════════════════════
# 11. COMMANDES SLASH
# ══════════════════════════════════════════════════════════════════

# ── /key ──────────────────────────────────────────────────────────
@bot.tree.command(name="key", description="Génère une clé d'accès unique valable 24h.")
async def slash_key(interaction: discord.Interaction):
    if interaction.channel_id != KEY_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Cette commande est réservée au salon <#{KEY_CHANNEL_ID}> !",
            ephemeral=True,
        )
        return

    cleanup_expired_keys()
    user_id = str(interaction.user.id)
    now     = datetime.now(timezone.utc)

    with _store_lock:
        existing = key_store.get(user_id)
        if existing and existing["expires"] > now:
            remaining = existing["expires"] - now
            hours     = int(remaining.total_seconds() // 3600)
            minutes   = int((remaining.total_seconds() % 3600) // 60)
            embed = discord.Embed(
                title="🔑 Clé déjà active",
                description=f"Tu as déjà une clé valide.\n\n**Ta clé :**\n```\n{existing['key']}\n```",
                color=discord.Color.orange(),
            )
            embed.add_field(
                name="⏱️ Expiration",
                value=f"Expire dans **{hours}h {minutes}min**",
                inline=False,
            )
            embed.set_footer(text="L3X BOT — Système de clés")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        new_key = generate_key(20)
        expires = now + timedelta(hours=24)
        key_store[user_id] = {
            "key":      new_key,
            "expires":  expires,
            "username": str(interaction.user),
        }
        _save_store(key_store)

    print(f"🔑 [NOUVELLE CLÉ] {interaction.user} (ID: {user_id}) | Clé : {new_key}")

    embed = discord.Embed(
        title="✅ Nouvelle clé générée !",
        description=(
            f"**Ta clé :**\n```\n{new_key}\n```\n"
            "Copie-la et colle-la dans le script Roblox."
        ),
        color=discord.Color.green(),
    )
    embed.add_field(name="⏱️ Durée",     value="**24 heures**",                   inline=False)
    embed.add_field(name="⚠️ Important", value="Clé personnelle — ne pas partager.", inline=False)
    embed.set_footer(text="L3X BOT — Système de clés")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /linkroblox ───────────────────────────────────────────────────
@bot.tree.command(name="linkroblox", description="Vérifie ton compte Roblox pour récupérer ton rôle.")
async def slash_linkroblox(interaction: discord.Interaction):
    if interaction.channel_id != ROBLOX_VERIFY_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ Cette commande est réservée au salon <#{ROBLOX_VERIFY_CHANNEL_ID}> !",
            ephemeral=True,
        )
        return
    role = interaction.guild.get_role(ROBLOX_ROLE_ID) if interaction.guild else None
    if role and role in interaction.user.roles:
        await interaction.response.send_message(
            "✅ Tu as déjà le rôle Roblox vérifié !", ephemeral=True
        )
        return
    await interaction.response.send_modal(RobloxUsernameModal())


# ── /invite ───────────────────────────────────────────────────────
@bot.tree.command(name="invite", description="Obtiens le lien d'invitation du serveur.")
async def slash_invite(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📨 Invite tes amis !",
        description=(
            f"**Rejoins le serveur {SERVER_NAME} :**\n{DISCORD_INVITE}\n\n"
            "🔧 Outils OSINT / CSINT · 🎮 Rocket League FR · 🔑 Système de clés."
        ),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="L3X BOT")
    await interaction.response.send_message(embed=embed)


# ── /versionrl ────────────────────────────────────────────────────
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


# ── /versionfn ────────────────────────────────────────────────────
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


# ── /robloxversion ────────────────────────────────────────────────
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
                await interaction.response.send_message(f"❌ HTTP {resp.status}", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Erreur : {e}", ephemeral=True)


# ── /animesama ────────────────────────────────────────────────────
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


# ── /bumpstatus ───────────────────────────────────────────────────
@bot.tree.command(name="bumpstatus", description="Affiche le statut du bump Disboard automatique.")
async def slash_bumpstatus(interaction: discord.Interaction):
    now      = datetime.now(timezone.utc)
    last_str = (
        bot.last_bump_success.strftime("%H:%M:%S UTC")
        if bot.last_bump_success else "Pas encore effectué"
    )
    if bot.next_bump_at:
        delta    = bot.next_bump_at - now
        next_str = (
            f"Dans **{max(0, int(delta.total_seconds() // 60))} minutes**"
            if delta.total_seconds() > 0 else "Imminent"
        )
    else:
        next_str = "Inconnu"

    embed = discord.Embed(title="🔄 Statut Bump Disboard", color=discord.Color.blurple())
    embed.add_field(name="Dernier bump",  value=last_str,               inline=False)
    embed.add_field(name="Prochain bump", value=next_str,               inline=False)
    embed.add_field(name="Intervalle",    value="Toutes les **2 heures**", inline=False)
    embed.set_footer(text="L3X BOT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /listpartners ─────────────────────────────────────────────────
@bot.tree.command(name="listpartners", description="Liste tous les partenaires actifs.")
async def slash_listpartners(interaction: discord.Interaction):
    with _partner_lock:
        snapshot = list(partners)

    if not snapshot:
        await interaction.response.send_message("Aucun partenaire enregistré.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"🤝 {len(snapshot)} partenaire(s) actif(s)",
        color=discord.Color.gold(),
    )
    for p in snapshot:
        embed.add_field(
            name=p["name"],
            value=f"[Rejoindre]({p['invite']}) — {p['description'][:80]}",
            inline=False,
        )
    embed.set_footer(text="L3X BOT")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ══════════════════════════════════════════════════════════════════
# COMMANDES ADMIN (Incluant /spam)
# ══════════════════════════════════════════════════════════════════

# ── /spam ─────────────────────────────────────────────────────────
@bot.tree.command(name="spam", description="[ADMIN] Envoie des DMs répétés à un utilisateur.")
@app_commands.describe(
    uid="ID de l'utilisateur Discord cible",
    message="Message à envoyer",
    count="Nombre de messages (max 20)",
    random_string="Ajouter une chaîne aléatoire (True/False)",
    random_emojis="Ajouter des emojis aléatoires (True/False)"
)
async def slash_spam(
    interaction: discord.Interaction,
    uid: str,
    message: str,
    count: int = 5,
    random_string: bool = False,
    random_emojis: bool = False
):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    try:
        target_user = await bot.fetch_user(int(uid))
    except Exception:
        await interaction.followup.send("❌ Utilisateur introuvable. Vérifie l'ID.", ephemeral=True)
        return

    emojis = ["🔥", "💀", "🚀", "👑", "⚡"]
    success_count = 0

    for _ in range(min(count, 20)):
        msg = message
        if random_string:
            msg += " -> " + ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(25))
        if random_emojis:
            msg += " -> " + ' '.join(secrets.choice(emojis) for _ in range(5))

        try:
            await target_user.send(msg)
            success_count += 1
            await asyncio.sleep(0.6)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Impossible d'envoyer le message : les DMs de {target_user.name} sont fermés.", ephemeral=True)
            return
        except Exception:
            break

    await interaction.followup.send(f"✅ Spam terminé : {success_count}/{count} messages envoyés à **{target_user.name}**.", ephemeral=True)


# ── /shoprl ───────────────────────────────────────────────────────
@bot.tree.command(name="shoprl", description="[ADMIN] Force l'affichage de la boutique Rocket League.")
async def slash_shoprl(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return
    await send_rl_shop(interaction.channel)
    await interaction.response.send_message("✅ Boutique envoyée.", ephemeral=True)


# ── /keys ─────────────────────────────────────────────────────────
@bot.tree.command(name="keys", description="[ADMIN] Liste toutes les clés actives.")
async def slash_keys(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    cleanup_expired_keys()
    now = datetime.now(timezone.utc)
    with _store_lock:
        snapshot = dict(key_store)

    if not snapshot:
        await interaction.response.send_message("Aucune clé active.", ephemeral=True)
        return

    lines = []
    for uid, data in snapshot.items():
        remaining = data["expires"] - now
        h = int(remaining.total_seconds() // 3600)
        m = int((remaining.total_seconds() % 3600) // 60)
        lines.append(f"`{data['key']}` — {data['username']} — expire dans {h}h{m}m")

    embed = discord.Embed(
        title=f"🔑 {len(snapshot)} clé(s) active(s)",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    embed.set_footer(text="L3X BOT — Admin")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /revokekey ────────────────────────────────────────────────────
@bot.tree.command(name="revokekey", description="[ADMIN] Révoque la clé d'un utilisateur.")
@app_commands.describe(user="L'utilisateur dont révoquer la clé")
async def slash_revokekey(interaction: discord.Interaction, user: discord.Member):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    uid = str(user.id)
    with _store_lock:
        if uid in key_store:
            del key_store[uid]
            _save_store(key_store)
            removed = True
        else:
            removed = False

    msg = f"✅ Clé de {user} révoquée." if removed else f"❌ {user} n'a pas de clé active."
    await interaction.response.send_message(msg, ephemeral=True)


# ── /manualbump ───────────────────────────────────────────────────
@bot.tree.command(name="manualbump", description="[ADMIN] Force un bump Disboard immédiat.")
async def slash_manualbump(interaction: discord.Interaction):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    channel = bot.get_channel(BUMP_CHANNEL_ID)
    if not channel:
        await interaction.response.send_message(
            f"❌ Salon bump introuvable (ID: {BUMP_CHANNEL_ID}).", ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)
    try:
        await channel.send("!d bump")
        await interaction.followup.send("✅ Bump forcé envoyé.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)


# ── /addpartner ───────────────────────────────────────────────────
@bot.tree.command(name="addpartner", description="[ADMIN] Ajoute un serveur partenaire.")
@app_commands.describe(
    name="Nom du serveur partenaire",
    invite="Lien d'invitation (https://discord.gg/xxx)",
    description="Description courte du serveur",
    banner="URL d'une image bannière (optionnel)",
)
async def slash_addpartner(
    interaction: discord.Interaction,
    name: str,
    invite: str,
    description: str,
    banner: str = "",
):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    if not invite.startswith("https://discord.gg/"):
        await interaction.response.send_message(
            "❌ Le lien doit commencer par `https://discord.gg/`.", ephemeral=True
        )
        return

    new_partner = {
        "name":        name.strip(),
        "invite":      invite.strip(),
        "description": description.strip(),
        "banner":      banner.strip(),
        "added_by":    str(interaction.user),
        "added_at":    datetime.now(timezone.utc).isoformat(),
    }

    with _partner_lock:
        if any(p["invite"] == new_partner["invite"] for p in partners):
            await interaction.response.send_message("❌ Ce partenaire existe déjà.", ephemeral=True)
            return
        partners.append(new_partner)
        _save_partners(partners)

    channel = bot.get_channel(PARTNER_CHANNEL_ID)
    if channel:
        await _post_partner_embed(channel, new_partner)

    await interaction.response.send_message(
        f"✅ Partenaire **{name}** ajouté et posté dans <#{PARTNER_CHANNEL_ID}>.", ephemeral=True
    )


# ── /removepartner ────────────────────────────────────────────────
@bot.tree.command(name="removepartner", description="[ADMIN] Supprime un partenaire.")
@app_commands.describe(name="Nom exact du serveur à supprimer")
async def slash_removepartner(interaction: discord.Interaction, name: str):
    if not _is_admin(interaction):
        await interaction.response.send_message("❌ Permissions insuffisantes.", ephemeral=True)
        return

    with _partner_lock:
        before = len(partners)
        partners[:] = [p for p in partners if p["name"].lower() != name.strip().lower()]
        removed = len(partners) < before
        if removed:
            _save_partners(partners)

    msg = f"✅ Partenaire **{name}** supprimé." if removed else f"❌ Partenaire **{name}** introuvable."
    await interaction.response.send_message(msg, ephemeral=True)


# ── Gestion erreurs slash ──────────────────────────────────────────
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
# 12. LOOPS AUTOMATIQUES
# ══════════════════════════════════════════════════════════════════

@tasks.loop(time=time(hour=20, minute=0, tzinfo=timezone.utc))
async def daily_rl_shop():
    channel = bot.get_channel(RL_SHOP_CHANNEL_ID)
    if channel:
        await send_rl_shop(channel)


@tasks.loop(seconds=BUMP_INTERVAL_SEC)
async def auto_bump():
    channel = bot.get_channel(BUMP_CHANNEL_ID)
    if not channel:
        print(f"❌ Salon bump introuvable (ID: {BUMP_CHANNEL_ID})")
        return
    try:
        await channel.send("!d bump")
        bot.last_bump_success = datetime.now(timezone.utc)
        bot.next_bump_at      = bot.last_bump_success + timedelta(seconds=BUMP_INTERVAL_SEC)
        print(f"✅ Bump Disboard envoyé à {bot.last_bump_success.strftime('%H:%M:%S UTC')}")
    except discord.Forbidden:
        print("❌ Permissions manquantes — salon bump.")
    except Exception as e:
        print(f"❌ Erreur bump : {e}")

@auto_bump.before_loop
async def before_bump():
    await bot.wait_until_ready()
    await asyncio.sleep(10)


@tasks.loop(hours=6)
async def rotate_partner_embeds():
    global _partner_rotation_index
    channel = bot.get_channel(PARTNER_CHANNEL_ID)
    if not channel:
        return
    with _partner_lock:
        if not partners:
            return
        partner = partners[_partner_rotation_index % len(partners)]
        _partner_rotation_index = (_partner_rotation_index + 1) % len(partners)
    await _post_partner_embed(channel, partner)

@rotate_partner_embeds.before_loop
async def before_rotate():
    await bot.wait_until_ready()


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

    headers           = {"Client-ID": TWITCH_CLIENT_ID, "Authorization": f"Bearer {token}"}
    active_this_check: set[str] = set()
    all_ok            = True

    for i in range(0, len(STREAMERS), 100):
        chunk   = STREAMERS[i:i + 100]
        params  = [("user_login", s) for s in chunk]
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
# 13. DÉMARRAGE
# ══════════════════════════════════════════════════════════════════
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("❌ DISCORD_TOKEN manquant dans les variables d'environnement.")

bot.run(TOKEN)
