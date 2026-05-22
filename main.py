import discord
from discord.ext import tasks
from discord import app_commands  # ★スラッシュコマンド用のパーツを追加
from datetime import datetime, timezone, timedelta
import asyncio
import os
from flask import Flask
import threading
import imageio_ffmpeg

# --- Webサーバー設定 ---
app = Flask('')
@app.route('/')
def home():
    return "Botは正常に稼働しています！"

def run_server():
    app.run(host='0.0.0.0', port=8080, debug=False, use_reloader=False)

# --- 環境変数と初期設定 ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID", "0"))
CONFIG_CHANNEL_ID = int(os.getenv("CONFIG_CHANNEL_ID", "0"))
AUDIO_FILE = "morning.mp3"
JST = timezone(timedelta(hours=9))

alarm_hour = 6
alarm_minute = 30
already_played = False

async def play_voice():
    print(f"[{datetime.now(JST)}] 音声再生タスクを開始します。", flush=True)
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        return
    try:
        vc = await channel.connect()
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        source = discord.FFmpegPCMAudio(AUDIO_FILE, executable=ffmpeg_path)
        vc.play(source)
        while vc.is_playing():
            await asyncio.sleep(1)
        await vc.disconnect()
        print("再生終了、退室しました。", flush=True)
    except Exception as e:
        print(f"再生エラー: {e}", flush=True)
        if 'vc' in locals() and vc.is_connected():
            await vc.disconnect()

@tasks.loop(seconds=60)
async def check_time_loop():
    global already_played
    now = datetime.now(JST)
    if now.hour == alarm_hour and now.minute == alarm_minute:
        if not already_played:
            await play_voice()
            already_played = True
    else:
        already_played = False

# --- スラッシュコマンドに対応した特別なBotの土台を作る ---
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(intents=intents)
        # コマンドを管理する「ツリー」を用意する
        self.tree = app_commands.CommandTree(self)

    # 起動した時に自動で実行される処理（初期化用）
    async def setup_hook(self):
        # 作成したスラッシュコマンドをDiscord公式に登録（同期）する
        await self.tree.sync()
        print("スラッシュコマンドの同期が完了しました！", flush=True)

bot = MyBot()

@bot.event
async def on_ready():
    global alarm_hour, alarm_minute
    print(f"====================================", flush=True)
    print(f"ログイン成功: {bot.user.name} が起動しました！", flush=True)
    
    # データベース（Discordチャンネル）から過去の設定を読み込む
    config_channel = bot.get_channel(CONFIG_CHANNEL_ID)
    if config_channel:
        async for message in config_channel.history(limit=1):
            try:
                h_str, m_str = message.content.split(':')
                alarm_hour = int(h_str)
                alarm_minute = int(m_str)
                print(f"★過去の設定を復元: {alarm_hour:02d}:{alarm_minute:02d}", flush=True)
            except Exception:
                print("有効な過去設定がありませんでした。", flush=True)
    
    print(f"現在のアラーム設定: {alarm_hour:02d}:{alarm_minute:02d}", flush=True)
    print(f"====================================", flush=True)
    
    # ループ処理がまだ動いていなければ開始する
    if not check_time_loop.is_running():
        check_time_loop.start()

# 💡【ここから新しいスラッシュコマンドの定義】
# チャット欄に「/settime」と打つと、時(hour)と分(minute)を数字で数字で入力させる画面が出ます
@bot.tree.command(name="settime", description="目覚ましのアラーム時間を設定します")
@app_commands.describe(hour="時 (0-23)", minute="分 (0-59)")
async def set_time_command(interaction: discord.Interaction, hour: int, minute: int):
    global alarm_hour, alarm_minute
    
    # 入力された数字が正しいかチェック
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        alarm_hour = hour
        alarm_minute = minute
        
        # ユーザーへの返答（スラッシュコマンドは interaction.response.send_message を使います）
        await interaction.response.send_message(f"⏰ 目覚まし時間を **{alarm_hour:02d}:{alarm_minute:02d}** に変更しました！")
        
        # Discordチャンネルに設定を保存
        config_channel = bot.get_channel(CONFIG_CHANNEL_ID)
        if config_channel:
            await config_channel.send(f"{alarm_hour:02d}:{alarm_minute:02d}")
            print("新しい設定をDiscordに保存しました。", flush=True)
    else:
        await interaction.response.send_message("❌ 時間は0〜23時、分は0〜59分の間で指定してください。", ephemeral=True)

# バックグラウンドでWebサーバー起動
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

if TOKEN:
    bot.run(TOKEN)
