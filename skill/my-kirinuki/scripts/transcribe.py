"""素材フォルダの動画を文字起こしする（秒数つき）。

使い方:
  ~/kirinuki/.venv/bin/python transcribe.py            # ~/kirinuki/素材 の動画を全部
  ~/kirinuki/.venv/bin/python transcribe.py 動画.mp4    # 指定したファイルだけ
  オプション: --model small|medium|large-v3 （既定 small。精度を上げたいときは medium）

出力（~/kirinuki/文字起こし/）:
  <動画名>.txt   … [00:01:23.4] セリフ  の形。Codexが読んで切る場所を選ぶ用
  <動画名>.json  … 秒数つきの区切り。cut.py が字幕(SRT)を作るときに使う
すでに文字起こし済みの動画は飛ばす。
"""
import json
import sys
from pathlib import Path

WORK = Path.home() / "kirinuki"
SRC = WORK / "素材"
OUT = WORK / "文字起こし"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".webm"}


def ts(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


def main():
    args = sys.argv[1:]
    model_name = "small"
    if "--model" in args:
        i = args.index("--model")
        model_name = args[i + 1]
        del args[i:i + 2]

    files = [Path(a).expanduser() for a in args] if args else sorted(
        p for p in SRC.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not files:
        print(f"動画が見つかりません。{SRC} に素材を入れてください。")
        sys.exit(1)

    OUT.mkdir(parents=True, exist_ok=True)
    todo = [f for f in files if not (OUT / f"{f.stem}.json").exists()]
    for f in files:
        if f not in todo:
            print(f"済み: {f.name}")
    if not todo:
        return

    from faster_whisper import WhisperModel
    print(f"モデル読み込み中（{model_name}・初回はダウンロードに数分かかります）…")
    model = WhisperModel(model_name, device="cpu", compute_type="int8")

    for f in todo:
        print(f"文字起こし中: {f.name}")
        segments, info = model.transcribe(str(f), language="ja", vad_filter=True)
        segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
                for s in segments if s.text.strip()]
        (OUT / f"{f.stem}.json").write_text(
            json.dumps({"source": str(f), "duration": info.duration, "segments": segs},
                       ensure_ascii=False, indent=1), encoding="utf-8")
        (OUT / f"{f.stem}.txt").write_text(
            f"# {f.name}（{ts(info.duration)}）\n" +
            "\n".join(f"[{ts(s['start'])}] {s['text']}" for s in segs), encoding="utf-8")
        print(f"  → {len(segs)}行 / {ts(info.duration)}")


if __name__ == "__main__":
    main()
