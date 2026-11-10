# 粗い声の試し材料を作る（依頼主の録ったままの声が届くまでの代わり）
#   見本の動画の声（demucs で抜いた vocals.wav＝人の声）を切り出し、録ったままの声に近づける：
#   言いかけ→言い直し・同じ文を2回・つなぎ言葉（えーと・あのー）・噛み・間の長さのばらつき・文ごとの速さ違い・全体の速さ（ゆっくり話す人）
#   台本は「きれいな声」を whisper large-v3 で起こした文（依頼主の台本の代わり。区間・訴求・【間】は書かない＝依頼主の台本と同じ形）
#   正解（どこに何を足したか）を truth.json に書く
# 使い方: .venv/bin/python make_rough.py 声.wav 出力フォルダ --start 0 --len 150 [--slow 0.8] [--seed 1]
#   出力: narration.wav（粗い声）・daihon.txt（台本）・truth.json・clean.wav（切り出しただけの声）
import argparse, json, random, re, subprocess, tempfile
from pathlib import Path
import numpy as np
from common import SR, load, save, FILLER_STRONG
import henshu as H

ap = argparse.ArgumentParser()
ap.add_argument("audio"); ap.add_argument("out")
ap.add_argument("--start", type=float, default=0.0); ap.add_argument("--len", type=float, default=150.0)
ap.add_argument("--slow", type=float, default=1.0, help="全体の速さ（0.8＝ゆっくり話す人。編集で全体の倍率を1つ決められるかを見る）")
ap.add_argument("--seed", type=int, default=1)
A = ap.parse_args()
out = Path(A.out); out.mkdir(parents=True, exist_ok=True); cache = out / "cache"; cache.mkdir(exist_ok=True)
rnd = random.Random(A.seed)

full = load(A.audio)
# ---- 切り出し：始めと終わりを無音に合わせる（文の途中で切らない）
from common import frame_db, voice_mask, runs
fdb = frame_db(full, SR); vm, _ = voice_mask(fdb)
def snap_silence(t):
    i = int(t / 0.01)
    for d in range(0, 400):
        for j in (i + d, i - d):
            if 0 <= j < len(vm) and not vm[j:j + 15].any(): return j * 0.01
    return t
a = snap_silence(A.start); b = snap_silence(A.start + A.len)
x = full[int(a * SR):int(b * SR)].copy()
save(out / "clean.wav", x)

# ---- きれいな声を whisper large-v3 で起こす → 文に分ける（台本の代わり）
words = H.transcribe(x, cache, prompt="")
sents = H.split_words(words)          # 文の切り方は台本の代わり（words_to_script）と同じ
S = [{"s": ws[0][0], "e": ws[-1][1], "text": "".join(w[2] for w in ws).strip(), "words": ws} for ws in sents]
for s in S:
    if not s["text"].endswith(("。", "？", "！", "?", "!")): s["text"] += "。"
(out / "daihon.txt").write_text("\n".join(s["text"] for s in S) + "\n")

# ---- つなぎ言葉の音：同じ人の声から探す（全編を呼び水つきで起こす）。無ければ macOS の声で作る
fwords = H.transcribe(full, cache)
fill = []
for s_, e_, t in fwords:
    k = re.sub(r"[、。\s]", "", t)
    if k in FILLER_STRONG and 0.18 <= e_ - s_ <= 0.9 and k not in ("あ", "え", "ん"):
        fill.append(full[int(max(0, s_ - 0.02) * SR):int((e_ + 0.04) * SR)].copy())
fill_src = "同じ人の声（全編の %d か所）" % len(fill)
if len(fill) < 3:
    tmp = Path(tempfile.mkdtemp())
    for i, f in enumerate(["えーと", "あのー", "えー"]):
        subprocess.run(["say", "-v", "Kyoko", "-r", "150", "-o", str(tmp / f"f{i}.aiff"), f], check=True)
        y = load(tmp / f"f{i}.aiff"); fill.append(y * (np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(y ** 2)) + 1e-9)) * 0.8)
    fill_src += "＋macOS の声（Kyoko）3つ"

def seg(s, e): return x[int(max(0, s) * SR):int(e * SR)].copy()
def stretch(y, f):
    """f>1 で速く（長さ 1/f）"""
    if abs(f - 1) < 1e-3: return y
    t = Path(tempfile.mkdtemp())
    save(t / "i.wav", y)
    subprocess.run(["rubberband", "-q", "-T", str(f), "--fine", str(t / "i.wav"), str(t / "o.wav")], check=True, capture_output=True)
    return load(t / "o.wav")
_sil = np.repeat(~vm[int(a / 0.01):int(b / 0.01)], int(SR * 0.01))[:len(x)]   # 無音の所の部屋の音（声の長さと10ms枠の端数を合わせる）
_sil = np.pad(_sil, (0, len(x) - len(_sil)))
noise_lvl = np.sqrt(np.mean(x[_sil] ** 2)) if _sil.any() else 1e-4
def room(d): return (np.random.default_rng(int(d * 1000)).standard_normal(int(d * SR)) * max(noise_lvl, 2e-4)).astype(np.float32)

# ---- 組み立て（文ごとに 何を足すかを決める。どれも決まった割合で必ず入るように並べる）
kinds = ["iikake", "nidoiu", "filler", "speed_slow", "speed_fast", "kami", "nagai_ma"]
plan = []
for i in range(len(S)):
    plan.append(kinds[(i // 2) % len(kinds)] if i % 2 == 1 or i == 0 else "")
res, truth, T = [], [], 0.0
def put(y, what=None, text=""):
    global T
    if what: truth.append({"what": what, "s": round(T, 2), "e": round(T + len(y) / SR, 2), "text": text})
    res.append(y.astype(np.float32)); T += len(y) / SR
put(room(0.6))
for i, s in enumerate(S):
    y = seg(s["s"] - 0.03, s["e"] + 0.08); k = plan[i]
    if k == "iikake":
        cut = s["words"][max(1, int(len(s["words"]) * rnd.uniform(0.35, 0.6))) - 1][1]
        put(seg(s["s"] - 0.03, cut + 0.02), "言いかけ（消すべき）", "".join(w[2] for w in s["words"] if w[1] <= cut + 0.01))
        put(room(rnd.uniform(0.3, 0.7)))
    elif k == "nidoiu":
        put(stretch(y, 1.08), "同じ文の1回目（消すべき・2回目を残す）", s["text"]); put(room(rnd.uniform(0.6, 1.2)))
    elif k == "filler":
        f = fill[rnd.randrange(len(fill))]; put(f, "つなぎ言葉（消すべき）"); put(room(rnd.uniform(0.15, 0.4)))
    elif k == "kami":
        w0 = s["words"][0]; put(seg(w0[0] - 0.02, w0[1] + 0.01), "噛み（言葉の頭を言い直し・消すべき）", w0[2]); put(room(0.12))
    if k == "speed_slow": y = stretch(y, 0.82); truth.append({"what": "この文だけ遅い（0.82倍）", "s": round(T, 2), "text": s["text"]})
    if k == "speed_fast": y = stretch(y, 1.2); truth.append({"what": "この文だけ速い（1.2倍）", "s": round(T, 2), "text": s["text"]})
    put(y, None)
    gap = rnd.choice([0.12, 0.2, 0.3, 0.5, 0.8, 1.2]) if k != "nagai_ma" else rnd.uniform(2.0, 3.5)
    if k == "nagai_ma": truth.append({"what": "長すぎる間（詰めるべき）", "s": round(T, 2), "e": round(T + gap, 2)})
    put(room(gap))
y = np.concatenate(res)
if abs(A.slow - 1) > 1e-3:
    y = stretch(y, A.slow)
    for t in truth:
        for kk in ("s", "e"):
            if kk in t: t[kk] = round(t[kk] / A.slow, 2)
save(out / "narration.wav", y)
json.dump({"source": A.audio, "cut": [round(a, 2), round(b, 2)], "slow": A.slow, "fillers_from": fill_src, "sentences": len(S),
           "dur_clean": round(len(x) / SR, 2), "dur_rough": round(len(y) / SR, 2), "events": truth},
          open(out / "truth.json", "w"), ensure_ascii=False, indent=1)
print(f"→ {out}/narration.wav {len(y) / SR:.1f}秒（きれいな声 {len(x) / SR:.1f}秒）・台本 {len(S)}文・足したもの {len(truth)}・つなぎ言葉 {fill_src}")
