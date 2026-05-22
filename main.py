import discord
from discord.ext import tasks
from datetime import datetime, time, timezone, timedelta
import asyncio
import os
from flask import Flask
import threading

# --- Webサーバー設定 (Renderの居眠り防止用) ---
app = Flask('')
@app.route('/')
def home():
    return "Botは正常に稼働しています！"

def run_server():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# --- 環境変数の読み込み (Renderの設定画面から安全に取得します) ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
AUDIO_FILE = "morning.mp3"

JST = timezone(timedelta(hours=9))

async def play_voice():
    print(f"[{datetime.now(JST)}] 音声再生タスクを開始します。")
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"エラー: チャンネルID {CHANNEL_ID} が見つかりません。")
        return

    try:
        vc = await channel.connect()
        print(f"{channel.name} に参加しました。")
        source = discord.FFmpegPCMAudio(AUDIO_FILE)
        vc.play(source)
        while vc.is_playing():
            await asyncio.sleep(1)
        await vc.disconnect()
        print("再生終了、退室しました。")
    except Exception as e:
        print(f"再生エラー: {e}")
        if 'vc' in locals() and vc.is_connected():
            await vc.disconnect()

@tasks.loop(time=time(6, 30, 0, tzinfo=JST))
async def morning_task():
    await play_voice()

intents = discord.Intents.default()
# 念のためすべての権限を明示的にONにする
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"====================================")
    print(f"ログイン成功: {bot.user.name} がオンラインになりました！")
    print(f"====================================")
    morning_task.start()
    print("【起動テスト】今から一度再生を行います...")
    await play_voice()

# バックグラウンドでWebサーバーを起動
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

# Botの起動
if TOKEN:
    bot.run(TOKEN)
else:
    print("エラー: DISCORD_BOT_TOKEN が設定されていません。")
