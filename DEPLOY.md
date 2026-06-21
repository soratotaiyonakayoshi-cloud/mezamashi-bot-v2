# Oracle Cloud（無料VM）への引っ越し手順

Render から Oracle Cloud の「Always Free」VM へ目覚ましBotを移す手順です。
完全無料・スリープなしで24時間動きます。

---

## STEP 1. Oracle Cloud アカウント作成（ブラウザ作業）

1. https://www.oracle.com/jp/cloud/free/ から「無料で始める」
2. メール・国（日本）・クレジットカードを登録（**本人確認用で、無料枠では請求されません**）
3. ホームリージョンは近い場所（例: Japan East (Tokyo) / Japan Central (Osaka)）を選ぶ

## STEP 2. 無料VM（インスタンス）を作成

1. メニュー → 「コンピュート」→「インスタンス」→「インスタンスの作成」
2. 名前: `mezamashi-bot` など
3. イメージとシェイプ:
   - イメージ: **Ubuntu 22.04**（または Canonical Ubuntu）
   - シェイプ: 「シェイプの変更」→ **Ampere（ARM, VM.Standard.A1.Flex）** を選び、OCPU=1, メモリ=6GB 程度
   - ※ ARM が「容量不足(Out of capacity)」エラーなら、時間/リージョンを変えて再試行するか、x86 の `VM.Standard.E2.1.Micro`（これも無料枠）でもOK
4. 「SSHキーの追加」→ **「キーペアを生成」を選び、秘密鍵をダウンロード**（後でログインに使う。無くさない）
5. 「作成」

作成後、インスタンスの**パブリックIPアドレス**をメモ。

## STEP 3. SSHでVMに接続

ダウンロードした秘密鍵（例: `ssh-key.key`）を使う。Windows PowerShell の場合:

```powershell
# 鍵の権限を絞る（初回のみ）
icacls "ssh-key.key" /inheritance:r /grant:r "$($env:USERNAME):(R)"
# 接続（ubuntu はUbuntuイメージの既定ユーザー）
ssh -i "ssh-key.key" ubuntu@<パブリックIP>
```

## STEP 4. Botを配置してセットアップ

VMにログインした状態で:

```bash
# リポジトリを取得
git clone https://github.com/soratotaiyonakayoshi-cloud/mezamashi-bot-v2.git
cd mezamashi-bot-v2

# 依存パッケージと仮想環境をまとめて用意
bash setup.sh

# 環境変数を設定
cp .env.example .env
nano .env      # トークンとチャンネルIDを入力 → Ctrl+O で保存, Ctrl+X で終了
```

### 動作確認（手動起動）
```bash
venv/bin/python main.py
```
「ログイン成功」と出てDiscordでBotがオンラインになればOK。`Ctrl+C` で止める。

## STEP 5. 常駐化（systemdで自動起動・自動再起動）

```bash
# サービス定義をコピー（ユーザー名/パスがubuntu以外なら .service を先に編集）
sudo cp mezamashi-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mezamashi-bot

# 状態確認
systemctl status mezamashi-bot
# ログをリアルタイムで見る
journalctl -u mezamashi-bot -f
```

これでVM再起動後も自動で立ち上がり、落ちても10秒後に再起動します。

---

## 更新のやり方（コードを直したとき）
```bash
cd ~/mezamashi-bot-v2
git pull
venv/bin/pip install -r requirements.txt   # 依存が変わった時だけ
sudo systemctl restart mezamashi-bot
```

## トラブル時
- `journalctl -u mezamashi-bot -e` でエラーログ確認
- 音が出ない → `ffmpeg` と `libopus0` が入っているか（setup.shで導入済み）
- オフラインのまま → `.env` のトークンが正しいか、`DISCORD_CHANNEL_ID` がボイスチャンネルのIDか確認

> マッチングBotも同じVMに同じ手順でもう1つ systemd サービスとして同居できます。
