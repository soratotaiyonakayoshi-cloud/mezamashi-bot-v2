import discord
from discord.ext import tasks
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
AUDIO_FILE = "morning.mp3"
JST = timezone(timedelta(hours=9))

# ★ここが重要：デフォルトの目覚まし時間（再起動したらここに戻ります）
alarm_hour = 6
alarm_minute = 30
already_played = False  # 同じ分の中で何度も鳴らないようにするガード

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

# ★ 1分ごとに現在の時刻をパトロールするループに変更
@tasks.loop(seconds=60)
async def check_time_loop():
    global already_played
    now = datetime.now(JST)
    
    # 設定された「時」と「分」が一致したら再生
    if now.hour == alarm_hour and now.minute == alarm_minute:
        if not already_played:
            await play_voice()
            already_played = True
    else:
        # 設定時間以外の時は、ガードを解除しておく
        already_played = False

intents = discord.Intents.default()
intents.message_content = True  # チャットの文字を読み取るために必須
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"====================================", flush=True)
    print(f"ログイン成功: {bot.user.name} が起動しました！", flush=True)
    print(f"現在のアラーム設定: {alarm_hour:02d}:{alarm_minute:02d}", flush=True)
    print(f"====================================", flush=True)
    check_time_loop.start()

# ★ チャットでコマンドを受け付けるイベントを追加
@bot.event
async def on_message(message):
    global alarm_hour, alarm_minute
    
    # Bot自身の発言には反応しない
    if message.author == bot.user:
        return

    # 「!settime 」から始まるメッセージが来たら処理する
    if message.content.startswith('!settime '):
        # 「!settime 07:30」から時間の文字だけを抜き出す
        time_text = message.content.replace('!settime ', '').strip()
        
        try:
            # 「:」で区切って数字に変換する
            h_str, m_str = time_text.split(':')
            h = int(h_str)
            m = int(m_str)
            
            # 正しい時間の範囲（0〜23時、0〜59分）かチェック
            if 0 <= h <= 23 and 0 <= m <= 59:
                alarm_hour = h
                alarm_minute = m
                await message.channel.send(f"⏰ 目覚まし時間を **{alarm_hour:02d}:{alarm_minute:02d}** に変更しました！")
                print(f"アラーム時間が {alarm_hour:02d}:{alarm_minute:02d} に変更されました。", flush=True)
            else:
                await message.channel.send("❌ 時間は00:00〜23:59の間で指定してください。")
        except Exception:
            await message.channel.send("❌ 入力形式が違います。例：`!settime 07:30` と入力してください。")

# バックグラウンドでWebサーバー起動
server_thread = threading.Thread(target=run_server)
server_thread.daemon = True
server_thread.start()

if TOKEN:
    bot.run(TOKEN)
