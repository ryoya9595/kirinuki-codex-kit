"""切り抜き計画（plan.json）どおりに切ってつなぎ、字幕SRTと概要欄の下書きを作る。

使い方:
  <venvのpython> cut.py ~/kirinuki/出力/<タイトル>/plan.json
  （Mac: ~/kirinuki/.venv/bin/python ／ Windows: %USERPROFILE%\kirinuki\.venv\Scripts\python.exe）

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
つなぎ目の調整（省略時は両方オン）:
  "snap": true        … 切る位置を前後の「声が途切れた瞬間」に自動でずらす（言葉の途中で切れにくくする）
                        場面ごとに "snap": false と書けば、その場面だけ位置を動かさない
  "crossfade": 0.2    … つなぎ目で音と映像を0.2秒重ねる（0 で重ねない）
場面ごとに "crossfade" を書くと、その場面の直前のつなぎ目だけ重ねる秒数を変えられる
（アバンは 0.1 でテンポよく、アバン→本編は 0.3 でゆっくり、など）

出力（plan.json と同じフォルダ）:
  本編.mp4 … つないだ動画（CapCutでテロップ・サムネを仕上げる前提）
  字幕.srt … CapCutの「字幕をインポート」で読み込める
  概要欄.txt … 【PR】表記・クレジット・紹介URL入りの下書き
  使った場所.txt … どの動画の何秒から何秒か（確認・振り返り用）
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows でも日本語や絵文字の表示で止まらないようにする
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORK = Path.home() / "kirinuki"


def find_ffmpeg():
    """PATH に無くても、Windows の winget で入れた場所を探す"""
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    if os.name == "nt":
        cand = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links" / "ffmpeg.exe"
        if cand.exists():
            return str(cand)
    sys.exit("ffmpeg が見つかりません。セットアップをもう一度実行してください。")


FFMPEG = find_ffmpeg()
_probe = Path(FFMPEG).with_name("ffprobe.exe" if FFMPEG.lower().endswith(".exe") else "ffprobe")
FFPROBE = str(_probe) if _probe.exists() else (shutil.which("ffprobe") or "ffprobe")


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


# ---------- つなぎ目の調整 ----------
SR = 16000        # 解析用の音声サンプリング周波数
FRAME = 160       # 10ms ごとに音の大きさを測る


def load_audio(src, t0, dur):
    """素材の t0 秒から dur 秒ぶんの音声を、16kHzモノラルの数値列で読む"""
    import numpy as np
    t0 = max(0.0, t0)
    raw = subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
                          "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return t0, np.frombuffer(raw, dtype=np.int16).astype(np.float32)


def frame_db(x):
    """10ms ごとの音の大きさ（dB）。少しならして細かいノイズを消す"""
    import numpy as np
    n = len(x) // FRAME
    fr = x[:n * FRAME].reshape(n, FRAME)
    db = 20 * np.log10(np.sqrt((fr ** 2).mean(axis=1)) + 1e-6)
    return np.convolve(db, np.ones(3) / 3, mode="same")


def snap_point(src, t, kind):
    """切る位置 t を、近くでいちばん静かな瞬間（声の切れ目）にずらす。
    kind='start' は前に、'end' は後ろに広げる方を優先（頭や語尾の言葉を削らない）。
    元の位置で十分静かなら動かさない。"""
    import numpy as np
    try:
        # 探す幅：話し始めは前0.6秒・後0.3秒、話し終わりは前0.3秒・後0.8秒
        lo, hi = (0.6, 0.3) if kind == "start" else (0.3, 0.8)
        t0, x = load_audio(src, t - lo, lo + hi)
        db = frame_db(x)
        if len(db) < 20:
            return t
        times = t0 + (np.arange(len(db)) + 0.5) * FRAME / SR
        shift = times - t
        # 1秒ずらすごとに15dBぶんの罰点（遠くへ動かしすぎない）。言葉を削る方向は3倍
        wrong = (shift > 0.15) if kind == "start" else (shift < -0.15)
        score = db + 15 * np.abs(shift) * np.where(wrong, 3, 1)
        k = int(np.argmin(score))
        here = db[int(np.argmin(np.abs(shift)))]
        if here <= db[k] + 3:   # 元の位置とほとんど変わらないなら動かさない
            return t
        return float(times[k])
    except Exception:
        return t


def duration(path):
    out = subprocess.run([FFPROBE,
                          "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def has_audio(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return bool(out.strip())


def main():
    plan_path = Path(sys.argv[1]).expanduser().resolve()
    plan = json.loads(plan_path.read_text(encoding="utf-8-sig"))
    out_dir = plan_path.parent
    tmp = out_dir / "_parts"
    tmp.mkdir(exist_ok=True)
    fmt = plan.get("format", "yoko")
    snap = plan.get("snap", True)
    xf = float(plan.get("crossfade", 0.2))

    parts, clips, used = [], [], []
    for i, c in enumerate(plan["clips"], 1):
        src = resolve(c["src"])
        if not src.exists():
            sys.exit(f"素材が見つかりません: {src}")
        s, e = sec(c["start"]), sec(c["end"])
        if e <= s:
            sys.exit(f"{i}本目：終わり({c['end']})が始まり({c['start']})より前です")
        if c.get("snap", snap):
            s2, e2 = snap_point(src, s, "start"), snap_point(src, e, "end")
            if e2 - s2 > 1.0:
                if abs(s2 - s) > 0.02 or abs(e2 - e) > 0.02:
                    print(f"   声の切れ目に合わせて調整：{hms(s)}〜{hms(e)} → {hms(s2)}〜{hms(e2)}")
                s, e = s2, e2
        part = tmp / f"{i:02d}.mp4"
        print(f"[{i}/{len(plan['clips'])}] {src.name} {hms(s)}〜{hms(e)}")
        subprocess.run([
            FFMPEG, "-y", "-loglevel", "error", "-ss", f"{s:.2f}", "-t", f"{e - s:.2f}", "-i", str(src),
            "-filter_complex", video_filter(fmt), "-map", "[v]", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(part)], check=True)
        parts.append(part)
        clips.append((src, s, e, float(c.get("crossfade", xf))))
        used.append(f"{i}. {src.name}  {hms(s)}〜{hms(e)}（{e - s:.0f}秒）  {c.get('memo', '')}")

    # つなぐ：音と映像を xf 秒ずつ重ねる（重ねない設定・1本だけ・音が無い素材は、そのままつなぐ）
    durs = [duration(p) for p in parts]
    final = out_dir / "本編.mp4"
    xfs = [0.0] + [cl[3] for cl in clips[1:]]
    use_xf = (len(parts) > 1 and any(d > 0 for d in xfs)
              and all(durs[k] > max(xfs[k], xfs[k + 1] if k + 1 < len(xfs) else 0) * 2 + 0.2 for k in range(len(parts)))
              and all(has_audio(p) for p in parts))
    if use_xf:
        starts, t = [0.0], durs[0]
        vf, af, vlast, alast = [], [], "[0:v]", "[0:a]"
        for k in range(1, len(parts)):
            d = max(xfs[k], 0.04)  # 0 のときも、ほぼ切り替えるだけの短い重ねにする
            off = t - d
            starts.append(off)
            vf.append(f"{vlast}[{k}:v]xfade=transition=fade:duration={d}:offset={off:.3f}[v{k}]")
            af.append(f"{alast}[{k}:a]acrossfade=d={d}[a{k}]")
            vlast, alast = f"[v{k}]", f"[a{k}]"
            t = off + durs[k]
        cmd = [FFMPEG, "-y", "-loglevel", "error"]
        for p in parts:
            cmd += ["-i", str(p)]
        cmd += ["-filter_complex", ";".join(vf + af), "-map", vlast, "-map", alast,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)]
        subprocess.run(cmd, check=True)
        total = t
    else:
        starts, t = [], 0.0
        for d in durs:
            starts.append(t)
            t += d
        total = t
        lst = tmp / "list.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                        "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(final)], check=True)
        lst.unlink()

    # 字幕：文字起こしがあれば、各場面のセリフを本編の時間に合わせて並べる
    srt = []
    for (src, s, e, _), st in zip(clips, starts):
        tj = WORK / "文字起こし" / f"{src.stem}.json"
        if tj.exists():
            for seg in json.loads(tj.read_text(encoding="utf-8-sig"))["segments"]:
                a, b = max(seg["start"], s), min(seg["end"], e)
                if b - a > 0.3:
                    srt.append((st + a - s, st + b - s, seg["text"]))
    offset = total

    (out_dir / "字幕.srt").write_text(
        "\n".join(f"{n}\n{srt_ts(a)} --> {srt_ts(b)}\n{t}\n" for n, (a, b, t) in enumerate(srt, 1)),
        encoding="utf-8")
    (out_dir / "使った場所.txt").write_text(
        f"{plan['title']}（合計 {hms(offset)}）\n" + "\n".join(used), encoding="utf-8")

    cfg_path = WORK / "config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig")) if cfg_path.exists() else {}
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
    tmp.rmdir()
    print(f"\n完成：{final}（{hms(offset)}）")
    print(f"字幕：{out_dir / '字幕.srt'}（{len(srt)}行）")
    print(f"概要欄：{out_dir / '概要欄.txt'}")


if __name__ == "__main__":
    main()
