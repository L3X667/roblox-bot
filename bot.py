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
    return "Le bot Roblox est en ligne et fonctionnel !"

def run():
    # Render attribue un port dynamique via os.environ.get("PORT")
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# Lancement du serveur Web en arrière-plan
keep_alive()

# ==========================================
# 2. CONFIGURATION DU BOT DISCORD
# ==========================================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ID de l'expérience Roblox et ID du salon Discord
ROBLOX_UNIVERSE_ID = 6880080644  # Modifie si besoin avec ton Universe ID
DISCORD_CHANNEL_ID = 1344403756811423854  # Modifie si besoin avec l'ID de ton salon

last_updated_timestamp = None

@bot.event
async def on_ready():
    print(f"✅ Bot connecté avec succès en tant que : {bot.user}")
    check_roblox_update.start()

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
                            print(f"Initialisation : Dernière MàJ enregistrée = {updated_at}")
                        elif updated_at != last_updated_timestamp:
                            last_updated_timestamp = updated_at
                            
                            channel = bot.get_channel(DISCORD_CHANNEL_ID)
                            if channel:
                                embed = discord.Embed(
                                    title="🚀 NOUVELLE MISE À JOUR ROBLOX !",
                                    description=f"Le jeu **{name}** vient de recevoir une mise à jour !",
                                    color=discord.Color.green()
                                )
                                embed.add_field(name="Horodatage", value=updated_at, inline=False)
                                embed.set_footer(text="Détecteur de mise à jour Roblox")
                                
                                await channel.send(content="@everyone", embed=embed)
                                print("Notification envoyée sur Discord !")
        except Exception as e:
            print(f"Erreur lors de la vérification Roblox : {e}")

# ==========================================
# 3. DEMARRAGE SECURISE DU BOT
# ==========================================
# Récupère le token depuis la variable d'environnement configurée sur Render
TOKEN = os.environ.get("DISCORD_TOKEN")

if TOKEN:
    bot.run(TOKEN)
else:
    print("❌ ERREUR : La variable d'environnement 'DISCORD_TOKEN' n'est pas définie sur Render !")
