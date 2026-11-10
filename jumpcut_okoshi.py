#!/usr/bin/env python3
# ジャンプカット用の書き起こし（jumpcut.py と jumpcut_hakaru.py が同じ耳で使う・作業AI 2026-10-19）
#   声を 0.25秒以上の静かな所で 12〜24秒のかたまりに切り、かたまりごとに Whisper large-v3（mlx・GPU）で単語の時刻つきで起こす
#   （写し元：pipe/koe_okoshi.py。通しで起こすと声のある所が抜け・作り事が出た 10/19）
#   違う所：つなぎ言葉（えー・あのー）も字にさせる呼び水を入れる（narration/henshu.py と同じ呼び水）。消す言葉を見つけるのが目的なので
#   使い方: narration/.venv/bin/python jumpcut_okoshi.py 声.wav 出力.json
import hashlib, json, os, re, subprocess, sys
import numpy as np

WHISPER = "mlx-community/whisper-large-v3-mlx"
PROMPT = "えー、あのー、えっと、まあ、そのー、うーん。"
SR16 = 16000
HALL = re.compile(r"ご視聴ありがとうございました|チャンネル登録|おやすみなさい|字幕|by H")


def load16(path):
    r = subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR16), "-f", "f32le", "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def okosu(a, cache_dir=None, prompt=PROMPT):
    """a：16kHz の声（float32）→ [[始, 終, 言葉], ...]（秒）"""
    key = hashlib.md5(a[::5].tobytes() + (WHISPER + (prompt or "")).encode()).hexdigest()[:16]
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
        f = os.path.join(cache_dir, "okoshi-%s.json" % key)
        if os.path.exists(f):
            return json.load(open(f))
    import mlx_whisper
    import mlx.core as mx
    mx.set_cache_limit(2 * 2 ** 30)   # GPU の溜めを 2GB まで（無いと起こすたびに太る・henshu.py と同じ）
    n10 = len(a) // 160
    db = 20 * np.log10(np.sqrt((a[:n10 * 160].reshape(n10, 160) ** 2).mean(1)) + 1e-9)
    floor = np.percentile(db, 10)
    quiet = db < max(-40, floor + 6)
    cands, s = [], None
    for i, q in enumerate(quiet):
        if q and s is None:
            s = i
        if not q and s is not None:
            if i - s >= 25:
                cands.append((s + i) // 2)
            s = None
    cuts = [0]
    for c in cands + [n10]:
        while c - cuts[-1] > 2400:
            prev = [d for d in cands if cuts[-1] + 600 < d < cuts[-1] + 2400]
            cuts.append(prev[-1] if prev else cuts[-1] + 2400)
        if c - cuts[-1] >= 1200 and c < n10:
            cuts.append(c)
    cuts.append(n10)
    out = []
    for k in range(len(cuts) - 1):
        c0, c1 = cuts[k], cuts[k + 1]
        if c1 - c0 < 15 or db[c0:c1].max() < floor + 10:
            continue
        r = mlx_whisper.transcribe(a[c0 * 160:c1 * 160], path_or_hf_repo=WHISPER, language="ja", word_timestamps=True,
                                   condition_on_previous_text=False, initial_prompt=prompt or None, temperature=0.0)
        for sg in r["segments"]:
            if HALL.search(sg.get("text", "")):
                continue
            for w in sg.get("words", []):
                ww = w["word"].strip()
                if not ww:
                    continue
                s_, e_ = c0 / 100 + float(w["start"]), c0 / 100 + float(w["end"])
                i0, i1 = int(s_ * 100), max(int(s_ * 100) + 1, int(e_ * 100))
                if db[i0:i1].max() < floor + 6:     # 声の無い所に置かれた言葉は捨てる
                    continue
                out.append([round(s_, 3), round(e_, 3), ww])
        mx.clear_cache()
    out.sort(key=lambda w: w[0])
    if cache_dir:
        json.dump(out, open(f, "w"), ensure_ascii=False)
    return out


if __name__ == "__main__":
    a = load16(sys.argv[1])
    W = okosu(a, os.path.join(os.path.dirname(os.path.abspath(sys.argv[2])), "cache"))
    json.dump(W, open(sys.argv[2], "w"), ensure_ascii=False)
    print("言葉 %d ／ %.1f秒" % (len(W), len(a) / SR16))
