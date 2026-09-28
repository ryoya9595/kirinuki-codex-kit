"""切り抜き計画（plan.json）どおりに切ってつなぎ、字幕SRTと概要欄の下書きを作る。

使い方:
  python3 cut.py ~/kirinuki/出力/<タイトル>/plan.json

plan.json の形:
{
  "title": "あべむつきがAIを使いこなす場面まとめ",
  "format": "yoko",            # yoko=横 1920x1080 / tate=縦 1080x1920（ショート）
  "source_urls": ["元動画のYouTube URL（わかれば）"],
  "clips": [
    {"src": "素材/動画A.mp4", "start": "00:01:23.4", "end": "00:02:10.0", "memo": "アバンで使われている見せ場"},
    {"src": "素材/動画B.mp4", "start": "00:10:05", "end": "00:11:30", "memo": ""}
  ]
}
src は ~/kirinuki からの相対パスか絶対パス。start/end は "時:分:秒" か秒数。

出力（plan.json と同じフォルダ）:
  本編.mp4 … つないだ動画（CapCutでテロップ・サムネを仕上げる前提）
  字幕.srt … CapCutの「字幕をインポート」で読み込める
  概要欄.txt … 【PR】表記・クレジット・紹介URL入りの下書き
  使った場所.txt … どの動画の何秒から何秒か（確認・振り返り用）
"""
import json
import subprocess
import sys
from pathlib import Path

WORK = Path.home() / "kirinuki"


def sec(v):
    if isinstance(v, (int, float)):
        return float(v)
    parts = [float(p) for p in str(v).split(":")]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def srt_ts(t):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def hms(t):
    h, rem = divmod(t, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:04.1f}"


def resolve(src):
    p = Path(src).expanduser()
    return p if p.is_absolute() else WORK / p


def video_filter(fmt):
    if fmt == "tate":
        # 縦：ぼかした背景の上に元映像を中央配置（黒帯にしない）
        return ("[0:v]split[a][b];"
                "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=30[bg];"
                "[b]scale=1080:-2[fg];"
                "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30[v]")
    return ("[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v]")


def main():
    plan_path = Path(sys.argv[1]).expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    out_dir = plan_path.parent
    tmp = out_dir / "_parts"
    tmp.mkdir(exist_ok=True)
    fmt = plan.get("format", "yoko")

    parts, srt, used = [], [], []
    offset = 0.0
    for i, c in enumerate(plan["clips"], 1):
        src = resolve(c["src"])
        if not src.exists():
            sys.exit(f"素材が見つかりません: {src}")
        s, e = sec(c["start"]), sec(c["end"])
        if e <= s:
            sys.exit(f"{i}本目：終わり({c['end']})が始まり({c['start']})より前です")
        part = tmp / f"{i:02d}.mp4"
        print(f"[{i}/{len(plan['clips'])}] {src.name} {hms(s)}〜{hms(e)}")
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", f"{s:.2f}", "-t", f"{e - s:.2f}", "-i", str(src),
            "-filter_complex", video_filter(fmt), "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(part)], check=True)
        parts.append(part)

        # 字幕：文字起こしがあれば、この区間のセリフをずらして並べる
        tj = WORK / "文字起こし" / f"{src.stem}.json"
        if tj.exists():
            for seg in json.loads(tj.read_text(encoding="utf-8"))["segments"]:
                a, b = max(seg["start"], s), min(seg["end"], e)
                if b - a > 0.3:
                    srt.append((offset + a - s, offset + b - s, seg["text"]))
        used.append(f"{i}. {src.name}  {hms(s)}〜{hms(e)}（{e - s:.0f}秒）  {c.get('memo', '')}")
        offset += e - s

    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts), encoding="utf-8")
    final = out_dir / "本編.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)

    (out_dir / "字幕.srt").write_text(
        "\n".join(f"{n}\n{srt_ts(a)} --> {srt_ts(b)}\n{t}\n" for n, (a, b, t) in enumerate(srt, 1)),
        encoding="utf-8")
    (out_dir / "使った場所.txt").write_text(
        f"{plan['title']}（合計 {hms(offset)}）\n" + "\n".join(used), encoding="utf-8")

    cfg_path = WORK / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8")) if cfg_path.exists() else {}
    url = cfg.get("affiliate_url") or "（ここに自分専用の紹介URL）"
    credit = cfg.get("credit") or "あべむつき【ラッキーマイン】"
    srcs = "\n".join(u for u in plan.get("source_urls", []) if u) or "（元動画のURL）"
    (out_dir / "概要欄.txt").write_text(f"""【PR】この動画はアフィリエイト広告（プロモーション）を含みます。

{plan['title']}

▼（ここに誘導の一言）
{url}

――――――――――
元動画：{credit}
{srcs}
※このチャンネルは{credit}の公認切り抜きチャンネルです。
""", encoding="utf-8")

    for p in parts:
        p.unlink()
    lst.unlink()
    tmp.rmdir()
    print(f"\n完成：{final}（{hms(offset)}）")
    print(f"字幕：{out_dir / '字幕.srt'}（{len(srt)}行）")
    print(f"概要欄：{out_dir / '概要欄.txt'}")


if __name__ == "__main__":
    main()
