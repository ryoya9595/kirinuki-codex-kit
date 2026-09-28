#!/bin/bash
# 切り抜きキットの初回セットアップ（Mac）
# - 作業フォルダ ~/kirinuki を作る
# - ffmpeg が無ければ Homebrew で入れる
# - 文字起こし用の Python 環境（faster-whisper）を ~/kirinuki/.venv に作る
set -e

WORK="$HOME/kirinuki"
mkdir -p "$WORK/素材" "$WORK/文字起こし" "$WORK/出力"

echo "== ffmpeg =="
if command -v ffmpeg >/dev/null 2>&1; then
  echo "OK: $(ffmpeg -version | head -1)"
else
  if command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "NG: ffmpeg も Homebrew も見つかりません。https://brew.sh の手順で Homebrew を入れてから、もう一度このスクリプトを実行してください。"
    exit 1
  fi
fi

echo "== Python =="
PY=$(command -v python3 || true)
if [ -z "$PY" ]; then
  echo "NG: python3 が見つかりません。ターミナルで xcode-select --install を実行してから、もう一度このスクリプトを実行してください。"
  exit 1
fi
echo "OK: $($PY --version)"

echo "== 文字起こし環境（faster-whisper）=="
if [ ! -x "$WORK/.venv/bin/python" ]; then
  "$PY" -m venv "$WORK/.venv"
fi
"$WORK/.venv/bin/python" -m pip install --quiet --upgrade pip
"$WORK/.venv/bin/python" -m pip install --quiet faster-whisper
"$WORK/.venv/bin/python" -c "import faster_whisper; print('OK: faster-whisper', faster_whisper.__version__)"

if [ ! -f "$WORK/config.json" ]; then
  cat > "$WORK/config.json" <<'EOF'
{
  "channel_name": "",
  "affiliate_url": "",
  "credit": "あべむつき【ラッキーマイン】"
}
EOF
  echo "config.json を作りました（チャンネル名と紹介URLは、Codexが最初に聞いて書き込みます）"
fi

echo ""
echo "セットアップ完了：$WORK"
