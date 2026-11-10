# 代わりの台本を作る（依頼主の台本が無い声で、粗い声を整える道具が動くかを試すため。作業AI・2026-10-15）
#   依頼主の Loom（YouTube と関係ない話）など：声を Whisper large-v3 で起こし、つなぎ言葉と、すぐ後で言い直した言いかけを除いて
#   「話したかった文」に近づけたものを台本の代わりにする。中身は使わない（声の道具の試しだけ）
# 使い方: .venv/bin/python daihon_kawari.py 声.wav 出力.txt
import re, sys
from pathlib import Path
from common import load, FILLERS, FILLER_STRONG
import henshu as H

x = load(sys.argv[1]); out = Path(sys.argv[2]); cache = out.parent / "cache"; cache.mkdir(parents=True, exist_ok=True)
words = H.transcribe(x, cache)                                  # 呼び水あり＝つなぎ言葉も書かせて、ここで落とす
FZ = {f.replace("ー", "") for f in FILLERS} | {f.replace("ー", "") for f in FILLER_STRONG} | {"まあ", "その", "なんか"}
k = lambda t: re.sub(r"[、。？！?!\sー]", "", t)
ws = [w for w in words if k(w[2]) and k(w[2]) not in FZ]
n_fill = len(words) - len(ws)
# すぐ後で同じ言葉から言い直した言いかけ（2〜8語の並びが続けて2回）→ 1回目を落とす
out_w, i, n_re = [], 0, 0
while i < len(ws):
    hit = 0
    for L in range(8, 1, -1):
        a = "".join(k(w[2]) for w in ws[i:i + L]); b = "".join(k(w[2]) for w in ws[i + L:i + 2 * L])
        if len(a) >= 3 and a == b: hit = L; break
    if hit: i += hit; n_re += 1; continue
    out_w.append(ws[i]); i += 1
out.write_text(H.words_to_script(out_w))
print(f"→ {out}（語 {len(words)}・つなぎ言葉を落とした {n_fill}・言い直しの1回目を落とした {n_re}）", file=sys.stderr)
