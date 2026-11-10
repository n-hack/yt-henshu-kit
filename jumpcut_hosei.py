#!/usr/bin/env python3
# 書き起こしの抜けを埋める（作業AI 2026-10-19）
#   Whisper を かたまりで起こすと、声があるのに字が出ない区間がある（面談前VSL 345〜377秒の 30秒が丸ごと抜け・判断カットの前に見つけた）
#   言葉と言葉の間が 1秒以上あり、その間に声の大きさ（部屋の音より上）が 0.25秒以上ある所を、前後 0.3秒を足してもう一度起こし、言葉を差し込む
#   使い方: narration/.venv/bin/python jumpcut_hosei.py 声.wav 書き起こし.json 出力.json
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "narration"))
import jumpcut as J                      # noqa: E402
import jumpcut_okoshi as OK              # noqa: E402
from common import load                  # noqa: E402


def main():
    wav, src, dst = sys.argv[1:4]
    W = json.load(open(src))
    x = load(wav)
    db = J.env_db(x)
    thr = max(np.percentile(db, 95) - 30, np.percentile(db, 10) + 8)
    a16 = OK.load16(wav)
    import mlx_whisper
    add, log = [], []
    for i in range(len(W) - 1):
        e, s = W[i][1], W[i + 1][0]
        if s - e < 1.0:
            continue
        a, b = int((e + 0.1) / J.HOP), int((s - 0.1) / J.HOP)
        loud = float((db[a:b] > thr + 6).sum() * J.HOP)
        if loud < 0.25:
            continue
        t0, t1 = max(0, e - 0.3), s + 0.3
        r = mlx_whisper.transcribe(a16[int(t0 * 16000):int(t1 * 16000)], path_or_hf_repo=OK.WHISPER, language="ja",
                                   word_timestamps=True, initial_prompt=OK.PROMPT)
        got = []
        for sg in r["segments"]:
            for w in sg.get("words", []):
                ws, we = w["start"] + t0, w["end"] + t0
                if ws >= e - 0.02 and we <= s + 0.02 and w["word"].strip():
                    got.append([round(ws, 2), round(we, 2), w["word"].strip()])
        log.append({"aida": [round(e, 2), round(s, 2)], "koe_byou": round(loud, 2), "tashita": "".join(g[2] for g in got)})
        add += got
    W2 = sorted(W + add, key=lambda w: w[0])
    json.dump(W2, open(dst, "w"), ensure_ascii=False)
    json.dump(log, open(dst.replace(".json", "_log.json"), "w"), ensure_ascii=False, indent=1)
    print("言葉 %d → %d ／ 起こし直した間 %d" % (len(W), len(W2), len(log)))
    for l in log:
        print(l)


if __name__ == "__main__":
    main()
