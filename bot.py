import os
import discord
from discord.ext import commands, tasks
import aiohttp
from flask import Flask
from threading import Thread

# ==========================================
# 1. SERVEUR FLASK POUR RENDER (KEEP ALIVE)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Le bot Roblox & Twitch est en ligne et fonctionnel !"

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
intents.presences = True  # Indispensable pour détecter le statut de jeu/stream
intents.members = True    # Nécessaire pour lire le statut des membres

bot = commands.Bot(command_prefix="!", intents=intents)

# IDs de configuration
ROBLOX_UNIVERSE_ID = 6880080644
ROBLOX_CHANNEL_ID = 1344403756811423854
TWITCH_CHANNEL_ID = 1517233263293497384  # Ton salon d'annonces Twitch

last_updated_timestamp = None
# Pour éviter de spammer l'annonce si la personne reste en live longtemps
live_announced = set()

@bot.event
async def on_ready():
    print(f"✅ Bot connecté avec succès en tant que : {bot.user}")
    check_roblox_update.start()

# ------------------------------------------
# DETECTION DES LIVES TWITCH SUR ROCKET LEAGUE
# ------------------------------------------
@bot.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    # Vérifier si l'utilisateur a des activités en cours
    for activity in after.activities:
        # Vérifie si l'activité est un Stream (Streaming)
        if isinstance(activity, discord.Streaming):
            # Mots-clés recherchés pour Rocket League (en minuscule pour éviter les fautes)
            game_name = (activity.game or "").lower()
            stream_name = (activity.name or "").lower()
            
            is_rocket_league = "rocket league" in game_name or "rocket" in game_name or "rocket league" in stream_name
            
            if is_rocket_league:
                # Si le live n'a pas encore été annoncé pendant cette session
                if after.id not in live_announced:
                    live_announced.add(after.id)
                    
                    channel = bot.get_channel(TWITCH_CHANNEL_ID)
                    if channel:
                        twitch_url = activity.url
                        twitch_pseudo = activity.twitch_name or after.display_name
                        
                        embed = discord.Embed(
                            title=f"🔴 {after.display_name} est en LIVE sur Rocket League !",
                            description=f"Venez soutenir **{twitch_pseudo}** en direct !",
                            url=twitch_url,
                            color=discord.Color.purple()
                        )
                        embed.add_field(name="Titre du live", value=activity.details or "Pas de titre", inline=False)
                        embed.add_field(name="Lien Twitch", value=twitch_url, inline=False)
                        embed.set_thumbnail(url=after.display_avatar.url)
                        embed.set_footer(text="Détecteur de Stream Twitch")
                        
                        await channel.send(content=f"🔴 **{after.display_name}** est en live sur **Rocket League** !\n{twitch_url}", embed=embed)
                        print(f"Annonce Twitch envoyée pour {after.name} ({twitch_url})")
            return

    # Si l'utilisateur arrête de streamer, on le retire de la liste pour la prochaine fois
    if after.id in live_announced:
        live_announced.remove(after.id)

# ------------------------------------------
# DETECTION DES MAJ ROBLOX
# ------------------------------------------
@tasks.loop(minutes=2)
async def check_roblox_update():
    global last_updated_timestamp
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

                        if last_updated_timestamp is None:
                            last_updated_timestamp = updated_at
                            print(f"Initialisation Roblox : {updated_at}")
                        elif updated_at != last_updated_timestamp:
                            last_updated_timestamp = updated_at
                            
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

# ==========================================
# 3. DEMARRAGE
# ==========================================
TOKEN = os.environ.get("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERREUR : La variable d'environnement 'DISCORD_TOKEN' n'est pas définie sur Render !")
