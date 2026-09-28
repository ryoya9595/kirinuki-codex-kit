# 切り抜きキット（Codex用）導入手順 ─ Codex向け

> このファイルは **Codex（OpenAI）が読んで実行する手順書**です。
> ユーザーはこのページのURLをCodexに貼っただけの状態です。以下を上から順に、ユーザーと会話しながら進めてください。
> 作成：RISE講師 関 諒也

## このキットでできること
あべむつき【ラッキーマイン】の公認切り抜き動画を、RISE会員サイトで配布されている素材から作ります。
Codexが「文字起こし → 切り口に合う場面を複数の動画から選ぶ → カットしてつなぐ → 字幕SRTと概要欄の下書き」までを行い、ユーザーはCapCutで仕上げて投稿します。

## 前提
- Mac（Apple Silicon / Intel どちらも可）または Windows 10/11（Windows は動作未検証。つまずいたら表示された内容をそのままユーザーに伝えてください）
- まずユーザーのパソコンが Mac か Windows かを確認してから進めてください
- RISEの会員で、会員サイトの「切り抜き講座」を見られること（素材とルールはそこにあります）

## 手順

### 1. ユーザーに一言伝える
次のように伝えてから始めてください：
「切り抜きキットを入れます。①スキルを入れる ②動画の道具（ffmpeg・文字起こし）を入れる ③チャンネル名と紹介URLを聞く、の順で進めます。途中でインストールの許可を聞くことがあります。」

### 2. スキルをダウンロードして入れる
次のコマンドを実行してください（`~/.codex/skills/my-kirinuki/` に入ります）。

**Mac**
```bash
BASE="https://ryoya9595.github.io/kirinuki-codex-kit/skill/my-kirinuki"
DEST="$HOME/.codex/skills/my-kirinuki"
mkdir -p "$DEST/scripts"
curl -fsSL "$BASE/SKILL.md" -o "$DEST/SKILL.md"
for f in setup.sh setup.ps1 transcribe.py cut.py; do curl -fsSL "$BASE/scripts/$f" -o "$DEST/scripts/$f"; done
chmod +x "$DEST/scripts/setup.sh"
ls -la "$DEST" "$DEST/scripts"
```

**Windows（PowerShell）**
```powershell
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$BASE = "https://ryoya9595.github.io/kirinuki-codex-kit/skill/my-kirinuki"
$DEST = Join-Path $HOME ".codex\skills\my-kirinuki"
New-Item -ItemType Directory -Force (Join-Path $DEST "scripts") | Out-Null
Invoke-WebRequest -UseBasicParsing "$BASE/SKILL.md" -OutFile (Join-Path $DEST "SKILL.md")
foreach ($f in "setup.sh","setup.ps1","transcribe.py","cut.py") { Invoke-WebRequest -UseBasicParsing "$BASE/scripts/$f" -OutFile (Join-Path $DEST "scripts\$f") }
Get-ChildItem -Recurse $DEST
```

5ファイル（SKILL.md・setup.sh・setup.ps1・transcribe.py・cut.py）がそろっていることを確認してください。
ネットワークが使えずに失敗した場合は、ユーザーにネットワークの許可を求めてから再実行してください。

### 3. 道具を入れる（初回セットアップ）
**Mac**
```bash
bash "$HOME/.codex/skills/my-kirinuki/scripts/setup.sh"
```
**Windows（PowerShell）**
```powershell
powershell -ExecutionPolicy Bypass -File "$HOME\.codex\skills\my-kirinuki\scripts\setup.ps1"
```
- 作業フォルダ `~/kirinuki/`（素材／文字起こし／出力）ができます
- ffmpeg が無ければ入れます（Mac＝Homebrew／Windows＝winget）。Homebrew や winget が無い場合、または「開き直してから、もう一度」と出た場合は、表示された案内をそのままユーザーに伝えてください
- 文字起こし用の Python 環境（faster-whisper）を `~/kirinuki/.venv` に作ります（数分かかります）。Windows で Python が無い場合は winget で入れます
- 最後に「セットアップ完了」と出れば成功です

### 4. ユーザーに2つ聞いて config.json に書く
`~/kirinuki/config.json` の次の2つを、ユーザーに聞いて書き込んでください（Windows では BOM なしの UTF-8 で書く）。
- `channel_name`：切り抜きチャンネルの名前（未定なら空のまま）
- `affiliate_url`：アフィリエイター登録で取った**自分専用の紹介URL**（まだなら空のまま。あとで入れられます）

まだの場合は、会員サイト「切り抜き講座」の**登録フォーム（契約内容の確認と署名）**と**アフィリエイター登録**を先に済ませるよう伝えてください。署名が無いと報酬が払われません。

### 5. 完了を伝える
次のように伝えて終わってください：

「導入できました！次からは **$my-kirinuki** と呼ぶか、『切り抜き作って』と言えば始められます。
1. 会員サイトの『切り抜き素材ダウンロード』から動画を落として、`~/kirinuki/素材` に入れてください（切り口に合いそうな動画を何本か）
2. どんな切り抜きにするか（例：あべむつきがAIを使いこなす場面まとめ）を教えてください」

※ Codexを一度閉じて開き直すと、スキルが確実に読み込まれます。
