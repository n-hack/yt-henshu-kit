# 試しの答え合わせ：make_test.py の正解（truth.json）と henshu.py の結果（kiroku.json）を比べる
#   取りこぼし＝消すべき声が残った ／ 消しすぎ＝残すべき声が削れた
# 使い方: .venv/bin/python hyouka.py test/tts1/raw_a.truth.json test/out_a/kiroku.json
import json, sys
from pathlib import Path
import numpy as np
from common import SR, HOP, load, frame_db, voice_mask

truth = json.load(open(sys.argv[1]))
rep = json.load(open(sys.argv[2]))
# 声のある刻みだけで数える（文の中の間を詰めた分は「削った」に入れない）
raw = Path(sys.argv[1].replace(".truth.json", ".wav"))
vm, _ = voice_mask(frame_db(load(raw), SR))
km = np.zeros(len(vm), bool)
for a, b, _ in rep["kept_ranges"]:
    km[int(a / HOP):int(b / HOP) + 1] = True


def kept_len(s, e):
    a, b = int(s / HOP), int(e / HOP)
    return km[a:b][vm[a:b]].sum() * HOP / max(vm[a:b].mean(), 1e-6)


miss, over, ok_del, ok_keep = [], [], 0, 0
for t in truth["truth"]:
    d = t["e"] - t["s"]
    k = kept_len(t["s"], t["e"]) / max(d, 1e-6)
    if t["kind"] == "del":
        if k > 0.25:
            miss.append((t, k))
        else:
            ok_del += 1
    else:
        if k < 0.85:
            over.append((t, k))
        else:
            ok_keep += 1

n_del = sum(t["kind"] == "del" for t in truth["truth"])
n_keep = len(truth["truth"]) - n_del
print(f"消すべき {n_del} → 消せた {ok_del} ／ 取りこぼし {len(miss)}")
for t, k in miss:
    print(f"  取りこぼし {t['s']:.2f}〜{t['e']:.2f} {t['reason']}「{t['text']}」 残った割合 {k:.0%}")
print(f"残すべき {n_keep} → 残せた {ok_keep} ／ 消しすぎ {len(over)}")
for t, k in over:
    print(f"  消しすぎ {t['s']:.2f}〜{t['e']:.2f} 文{t['sent'] + 1}「{t['text']}」 残った割合 {k:.0%}")
tm = rep.get("timing")
if tm:
    bad = [s for s in tm["sentences"] if not s["found"] or s["hits"] != 1]
    print(f"編集後の文字起こし：台本の文がちょうど1回 {len(tm['sentences']) - len(bad)}/{len(tm['sentences'])}"
          f" ／ 台本に無い言葉 {' '.join(e['t'] for e in tm['not_in_script']) or 'なし'}")
    for s in bad:
        print(f"  文{s['i']} 見つかった={s['found']} 回数={s['hits']} {s['text']}")
print(f"長さ {rep['dur_in']}秒 → {rep['dur_out']}秒 ／ 一覧に出した削除 {len(rep['deleted'])}件")
