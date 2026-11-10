#!/usr/bin/env python3
# 判断カット用の書き起こし：声のかたまり（島）ごとに起こす（作業AI 2026-10-19）
#   jumpcut_okoshi.py（12〜24秒のかたまり）では、Whisper が言い直しの くり返しを1回にまとめて書き、時刻もずれた
#   （面談前VSL：「あと、今回面談を、あと、今回面談を…」「優秀な相談相手が、優秀な…」が1回に・345〜377秒の30秒が丸ごと抜け）
#   ここでは 0.35秒以上の静かな所で声を島に切り、島ごとに起こす（言い直しの回ごとに字と時刻が出る）。島の外の言葉は出ない
#   使い方: narration/.venv/bin/python jumpcut_shima.py 声.wav 出力.json
import hashlib, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, "narration"))
import jumpcut as J                      # noqa: E402
import jumpcut_okoshi as OK              # noqa: E402
from common import load                  # noqa: E402

GAP = 0.35      # これより短い静けさは同じ島
PAD = 0.12      # 島の前後に足す（頭の子音・語尾の息を Whisper に聞かせる）


def shima(wav):
    x = load(wav)
    db = J.env_db(x)
    thr = max(np.percentile(db, 95) - 30, np.percentile(db, 10) + 8)
    loud = db > thr
    runs = J.quiet_runs(loud, 0, len(loud), 4)          # 20ms 以上の声
    out = []
    for a, b in runs:
        a, b = a * J.HOP, b * J.HOP
        if out and a - out[-1][1] < GAP:
            out[-1][1] = b
        else:
            out.append([a, b])
    return [s for s in out if s[1] - s[0] >= 0.08], len(x) / J.SR


def main():
    wav, dst = sys.argv[1:3]
    S, dur = shima(wav)
    a16 = OK.load16(wav)
    import mlx_whisper
    import mlx.core as mx
    mx.set_cache_limit(2 * 2 ** 30)
    W, log = [], []
    for a, b in S:
        t0, t1 = max(0, a - PAD), min(dur, b + PAD)
        r = mlx_whisper.transcribe(a16[int(t0 * 16000):int(t1 * 16000)], path_or_hf_repo=OK.WHISPER, language="ja",
                                   word_timestamps=True, initial_prompt=OK.PROMPT, condition_on_previous_text=False)
        ws = [[round(float(w["start"]) + t0, 3), round(float(w["end"]) + t0, 3), w["word"].strip()]
              for s in r["segments"] for w in s.get("words", []) if w["word"].strip()]
        ws = [w for w in ws if not OK.HALL.search(w[2])]
        # 島の外にはみ出した時刻は島の中に収める（ずれた時刻で隣の島の声を切らないため）
        for w in ws:
            w[0] = min(max(w[0], t0), t1); w[1] = min(max(w[1], w[0]), t1)
        W += ws
        log.append({"shima": [round(a, 2), round(b, 2)], "text": "".join(w[2] for w in ws)})
    json.dump(W, open(dst, "w"), ensure_ascii=False)
    json.dump(log, open(dst.replace(".json", "_shima.json"), "w"), ensure_ascii=False, indent=0)
    print("島 %d ／ 言葉 %d ／ 字の無い島 %d" % (len(S), len(W), sum(1 for l in log if not l["text"])))


if __name__ == "__main__":
    main()
