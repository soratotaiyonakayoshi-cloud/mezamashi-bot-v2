import discord
from discord.ext import tasks
from discord import app_commands
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

# メモリ上の初期値
alarm_hour = 6
alarm_minute = 30
max_play_count = 3       # ★追加：スヌーズ最大回数
snooze_interval = 5      # ★追加：スヌーズ間隔（分）
already_played = False

async def play_voice():
    global max_play_count, snooze_interval
    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        return

    print(f"[{datetime.now(JST)}] 目覚ましタスクを開始します（最大{max_play_count}回）", flush=True)

    for i in range(max_play_count):
        human_members = [m for m in channel.members if not m.bot]
        
        if len(human_members) == 0:
            print("チャンネルに人がいないため、スヌーズを終了して完全停止します！", flush=True)
            break

        print(f"--- ⏰ {i+1}回目の再生を開始します ---", flush=True)
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

        if i < max_play_count - 1:
            print(f"まだ人がいるかもしれないので、{snooze_interval}分後にスヌーズします...", flush=True)
            await asyncio.sleep(snooze_interval * 60) # 分を秒に変換して待機

@tasks.loop(seconds=60)
async def check_time_loop():
    global already_played
    now = datetime.now(JST)
    if now.hour == alarm_hour and now.minute == alarm_minute:
        if not already_played:
            asyncio.create_task(play_voice())
            already_played = True
    else:
        already_played = False

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("スラッシュコマンドの同期が完了しました！", flush=True)

bot = MyBot()

@bot.event
async def on_ready():
    global alarm_hour, alarm_minute, max_play_count, snooze_interval
    print(f"====================================", flush=True)
    print(f"ログイン成功: {bot.user.name} が起動しました！", flush=True)
    
    # データベースから設定を読み込む
    config_channel = bot.get_channel(CONFIG_CHANNEL_ID)
    if config_channel:
        async for message in config_channel.history(limit=1):
            try:
                # 「06:30,3,5」のようにカンマで区切られているかチェック
                parts = message.content.split(',')
                
                # 時間の読み込み
                h_str, m_str = parts[0].split(':')
                alarm_hour = int(h_str)
                alarm_minute = int(m_str)
                
                # スヌーズ設定の読み込み（古い設定でカンマが無い場合は初期値のまま）
                if len(parts) == 3:
                    max_play_count = int(parts[1])
                    snooze_interval = int(parts[2])
                    
                print(f"★過去の設定を復元: {alarm_hour:02d}:{alarm_minute:02d} / スヌーズ最大{max_play_count}回 / {snooze_interval}分間隔", flush=True)
            except Exception:
                print("有効な過去設定がありませんでした。", flush=True)
    
    print(f"現在のアラーム設定: {alarm_hour:02d}:{alarm_minute:02d}", flush=True)
    print(f"====================================", flush=True)
    
    if not check_time_loop.is_running():
        check_time_loop.start()

# 【コマンド1】時間設定コマンド
@bot.tree.command(name="settime", description="目覚ましのアラーム時間を設定します")
@app_commands.describe(hour="時 (0-23)", minute="分 (0-59)")
async def set_time_command(interaction: discord.Interaction, hour: int, minute: int):
    global alarm_hour, alarm_minute, max_play_count, snooze_interval
    
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        alarm_hour = hour
        alarm_minute = minute
        await interaction.response.send_message(f"⏰ 目覚まし時間を **{alarm_hour:02d}:{alarm_minute:02d}** に変更しました！")
        
        config_channel = bot.get_channel(CONFIG_CHANNEL_ID)
        if config_channel:
            # データベース保存形式: 06:30,3,5
            await config_channel.send(f"{alarm_hour:02d}:{alarm_minute:02d},{max_play_count},{snooze_interval}")
            print("新しい時間設定をDiscordに保存しました。", flush=True)
    else:
        await interaction.response.send_message("❌ 時間は0〜23時、分は0〜59分の間で指定してください。", ephemeral=True)

# ★【コマンド2】スヌーズ設定コマンド（新規追加）
@bot.tree.command(name="setsnooze", description="スヌーズの最大回数と間隔を設定します")
@app_commands.describe(count="最大再生回数 (1〜10回)", interval="間隔の分数 (1〜60分)")
async def set_snooze_command(interaction: discord.Interaction, count: int, interval: int):
    global alarm_hour, alarm_minute, max_play_count, snooze_interval
    
    # 異常な数字（100回連続再生など）を防ぐガード
    if 1 <= count <= 10 and 1 <= interval <= 60:
        max_play_count = count
        snooze_interval = interval
        await interaction.response.send_message(f"🔄 スヌーズ設定を **最大 {max_play_count} 回 / {snooze_interval} 分間隔** に変更しました！")
        
        config_channel = bot.get_channel(CONFIG_CHANNEL_ID)
        if config_channel:
            # データベース保存形式: 06:30,3,5
            await config_channel.send(f"{alarm_hour:02d}:{alarm_minute:02d},{max_play_count},{snooze_interval}")
            print("新しいスヌーズ設定をDiscordに保存しました。", flush=True)
    else:
        await interaction.response.send_message("❌ 回数は1〜10回、間隔は1〜60分の間で指定してください。", ephemeral=True)


# バックグラウンドでWebサーバー起動
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

if TOKEN:
    bot.run(TOKEN)
