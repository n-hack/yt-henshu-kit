# make_rough.py で作った粗い声の答え合わせ：truth.json（どこに何を足したか）と henshu.py の結果（kiroku.json の kept_ranges）を比べる
#   消すべき（言いかけ・同じ文の1回目・つなぎ言葉・噛み）… 声のある所が25%を超えて残ったら「取りこぼし」
#   詰めるべき（長すぎる間）……………………………… 1.0秒を超えて残ったら「取りこぼし」
#   残すべき（それ以外の声）………………………………… 声のある所の残った割合。90%を切ったら「消しすぎ」
# 使い方: .venv/bin/python hyouka_rough.py <粗い声のフォルダ（narration.wav・truth.json）> <henshu の出力フォルダ（kiroku.json）>
import json, sys
from pathlib import Path
import numpy as np
from common import SR, HOP, load, frame_db, voice_mask

src, outd = Path(sys.argv[1]), Path(sys.argv[2])
truth = json.load(open(src / "truth.json")); rep = json.load(open(outd / "kiroku.json"))
x = load(src / "narration.wav"); vm, _ = voice_mask(frame_db(x, SR)); n = len(vm)
km = np.zeros(n, bool)
for r in rep.get("kept_ranges", []):
    a, b = r[0], r[1]; km[int(a / HOP):int(b / HOP) + 1] = True
def fr(s, e): return int(s / HOP), min(n, int(e / HOP) + 1)
dele = np.zeros(n, bool); res = []
for ev in truth["events"]:
    if "e" not in ev: continue
    a, b = fr(ev["s"], ev["e"])
    if "消すべき" in ev["what"]:
        dele[a:b] = True
        v = vm[a:b]; k = (km[a:b] & v).sum() / max(1, v.sum()) if v.any() else km[a:b].mean()
        res.append(("消す", ev["what"].split("（")[0], ev["s"], round(float(k), 2), k <= 0.25))
    elif "詰めるべき" in ev["what"]:
        dele[a:b] = True
        kept_s = km[a:b].sum() * HOP
        res.append(("詰める", "長すぎる間", ev["s"], round(float(kept_s), 2), kept_s <= 1.0))
# 声の橋渡し（lib/narr_bridge.py fix_leftovers）が編集後に切った残り（言いかけの取りこぼし）を当てる
nk = json.load(open(outd / "nokori.json")) if (outd / "nokori.json").exists() else []
for i, r in enumerate(res):
    if r[4] or r[0] != "消す": continue
    ev = [e for e in truth["events"] if e.get("s") == r[2]][0]
    if any(c.get("applied") and c.get("text") and c["text"][:6] in (ev.get("text") or "") for c in nk):
        res[i] = (r[0], r[1] + "（編集後に切った）", r[2], r[3], True)
keep = vm & ~dele
kr = (km & keep).sum() / max(1, keep.sum())
ok = sum(1 for r in res if r[4])
print("消す・詰める %d / %d できた" % (ok, len(res)))
for r in res:
    print(("  ✅ " if r[4] else "  🔴 ") + "%s %s %.1f秒 残り %s" % r[:4])
print("残すべき声の残り %.1f%%（90%%以上で合格）" % (100 * kr))
print("全体の速さ %s 倍（粗い声は全体 %s 倍に遅くしてある）" % ((rep.get("speed") or {}).get("factor"), truth.get("slow")))
json.dump({"done": ok, "total": len(res), "keep_ratio": round(float(kr), 3), "items": res, "speed": rep.get("speed"), "slow": truth.get("slow")},
          open(outd / "hyouka_rough.json", "w"), ensure_ascii=False, indent=1, default=str)
sys.exit(0 if ok == len(res) and kr >= 0.9 else 1)
