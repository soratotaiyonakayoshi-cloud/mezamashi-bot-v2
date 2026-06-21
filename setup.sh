#!/usr/bin/env bash
# 目覚ましBot セットアップスクリプト（Oracle Cloud / Ubuntu ARM 想定）
# 使い方: bash setup.sh
set -euo pipefail

echo "==> システム更新と必要パッケージのインストール"
sudo apt-get update
# python本体 / 仮想環境 / ビルド用 / 音声(opus, ffmpeg) / PyNaCl(libffi)
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg libopus0 libffi-dev git

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "==> アプリディレクトリ: $APP_DIR"

echo "==> Python仮想環境を作成"
python3 -m venv "$APP_DIR/venv"
"$APP_DIR/venv/bin/pip" install --upgrade pip
"$APP_DIR/venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo ""
echo "==> 完了！次にやること:"
echo "  1. 環境変数ファイルを作成:  cp .env.example .env && nano .env"
echo "  2. 動作確認(手動起動):       venv/bin/python main.py"
echo "  3. 常駐化(systemd):          下記 DEPLOY.md の手順を参照"
