import discord
from discord.ext import commands, tasks
import aiohttp

# --- CONFIGURATION ---
TOKEN = "MTUxNzIyNjk3ODk0MjUyMTQ3NQ.GoHajx.RvljJIXFEYUGXRQvg10zGTQC3dZcGRXEA3kz-Y"  # Remplace par le token de ton bot
CHANNEL_ID = 1534679583947886594  # Remplace par l'ID du salon Discord où envoyer l'alerte

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Variable pour stocker la dernière version connue
last_known_version = None

# API officielle de Roblox pour récupérer la version actuelle de WindowsPlayer
ROBLOX_API_URL = "https://clientsettings.roblox.com/v2/client-version/WindowsPlayer"


async def fetch_roblox_version():
    """Récupère la version actuelle de Roblox depuis l'API officielle."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(ROBLOX_API_URL) as response:
                if response.status == 200:
                    data = await response.json()
                    # Exemple de format retourné : "version-ff6341faef444107" ou numéro de version "0.732.0.7321040"
                    version_num = data.get("version", "Inconnue")
                    client_version = data.get("clientVersionUpload", version_num)
                    return client_version
    except Exception as e:
        print(f"Erreur lors de la vérification de la version Roblox : {e}")
    return None


@bot.event
async def on_ready():
    print(f"✅ Bot connecté en tant que {bot.user}")
    # Démarre la boucle de vérification automatique toutes les 15 minutes
    if not check_roblox_update.is_running():
        check_roblox_update.start()


@tasks.loop(minutes=15)
async def check_roblox_update():
    global last_known_version

    current_version = await fetch_roblox_version()
    if not current_version:
        return

    # Première exécution : enregistre la version de départ sans spammer
    if last_known_version is None:
        last_known_version = current_version
        print(f"📌 Version Roblox actuelle enregistrée : {last_known_version}")
        return

    # Si la version a changé -> Nouvelle mise à jour détectée !
    if current_version != last_known_version:
        last_known_version = current_version
        channel = bot.get_channel(CHANNEL_ID)

        if channel:
            embed = discord.Embed(
                title="🚨 Nouvelle mise à jour Roblox !",
                description="Roblox vient de déployer une nouvelle version du client.",
                color=discord.Color.red(),
            )
            embed.add_field(
                name="📦 Version", value=f"`{current_version}`", inline=False
            )
            embed.set_thumbnail(
                url="https://upload.wikimedia.org/wikipedia/commons/3/3a/Roblox_player_2022_icon.svg"
            )
            embed.set_footer(text="Système de notification automatique Roblox")

            await channel.send(embed=embed)
            print(f"📢 Notification d'update envoyée : {current_version}")


@bot.command()
async def robloxversion(ctx):
    """Commande manuelle pour afficher la version actuelle."""
    version = await fetch_roblox_version()
    if version:
        embed = discord.Embed(
            title="🎮 Version actuelle de Roblox",
            description=f"La version officielle actuelle est : `{version}`",
            color=discord.Color.blue(),
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ Impossible de récupérer la version de Roblox pour le moment.")


bot.run(TOKEN)