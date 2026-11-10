#!/usr/bin/env python3
# ジャンプカットの出来を数で測る（作業AI 2026-10-19・依頼主「俺の声だとジャンプカットが壊滅的」）
#   使い方: narration/.venv/bin/python jumpcut_hakaru.py 切った声.wav 台本.txt --raw 元の声.wav [--okoshi 切った声の書き起こし.json] [--raw-okoshi 元の書き起こし.json] [--cut cut.json] -o 結果.json
#   測るもの（元の声と同じ耳＝jumpcut_okoshi.py で起こして比べる）
#     ① 言葉の欠け：台本の文ごとに「元の声のいちばん近い回」と「切った声」の食い違い（かなの字数）を比べ、切った声で増えた分＝切って消えた字
#     ② 残ったつなぎ言葉（えー・あのー・えっと…）：台本に当たらない所に残った数
#     ③ 残った言い直し：台本に無い同じ並びのくり返し（4〜12字が続けて2回）の数
#     ④ 切れ目のプツ音：標本の2階差が周り（±5ms）の20倍を超える所（声の立ち上がりでは出ない大きさ）
#     ⑤ 無音0（デジタルの無音）の区間：部屋の音まで消えた所＝ブツ切れに聞こえる。20ms以上の本数と合計秒
#     ⑥ 声の途中で切れた所：5ms ごとの大きさが1つ隣で 30dB 以上落ちる／上がる所（自然な声ではほぼ出ない）
#     ⑦ 間の長さの分布（common.silences・0.06秒以上・文間／文中）と 0.3秒以上/分・0.5秒以上/分（手本の作者さん15本と同じ式）
#     ⑧ アドリブ（台本に無いが中身のある話・8字以上）が切った後に残っているか
import argparse, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "narration"))
import henshu as H                                    # noqa: E402  台本と書き起こしの並べ方（fit・candidates・choose・align_ops）を借りる（henshu.py は変えない）
from common import load, silences, kana, split_sentences, FILLER_STRONG, frame_db   # noqa: E402
import jumpcut_okoshi as OK                           # noqa: E402

SR = 48000


def words_of(path_wav, okoshi, cache):
    if okoshi and os.path.exists(okoshi):
        return json.load(open(okoshi))
    W = OK.okosu(OK.load16(path_wav), cache)
    if okoshi:
        json.dump(W, open(okoshi, "w"), ensure_ascii=False)
    return W


def chars(W):
    T, c2w = [], []
    for i, w in enumerate(W):
        k = kana(w[2])
        T += list(k)
        c2w += [i] * len(k)
    return np.array(T if T else ["_"]), np.array(c2w + [max(0, len(W) - 1)])


def sent_fit(sents, T):
    """文ごとに、書き起こしのどこかに当てたときの いちばん少ない食い違い（かなの字数）"""
    out = []
    for s in sents:
        D, _ = H.fit(np.array(list(s["k"])), T)
        out.append(int(D.min()))
    return out


def takes(sents, T):
    cands = [H.candidates(s["k"], T) for s in sents]
    pick = H.choose(cands, len(T))
    return [cands[i][p] if p is not None else None for i, p in enumerate(pick)]


def kurikaeshi(T, script_k):
    """台本に無い くり返し（同じ並び4〜12字を、0〜2字あけて続けて2回）"""
    n, i, hits = len(T), 0, []
    s = "".join(T)
    while i < n - 8:
        hit = None
        for L in range(12, 3, -1):
            a = s[i:i + L]
            if len(a) < L or "ー" * 2 in a:
                continue
            for g in range(0, 3):
                b = s[i + L + g:i + 2 * L + g]
                if a == b and (a + s[i + L:i + L + g] + a) not in script_k:
                    hit = (i, L, g, a)
                    break
            if hit:
                break
        if hit:
            hits.append(hit)
            i += 2 * hit[1] + hit[2]
        else:
            i += 1
    return hits


def fillers_left(W, T, c2w, sents, tk):
    """台本の文に当たっていない（または文の中で台本に無い）つなぎ言葉"""
    inside = np.zeros(len(W), int) - 1
    ins_flag = np.zeros(len(W), bool)
    for i, t in enumerate(tk):
        if t is None:
            continue
        _, a, b = t
        ws = sorted({int(c2w[c]) for c in range(a, b)})
        seg = "".join(kana(W[j][2]) for j in ws)
        ops, _ = H.align_ops(sents[i]["k"], seg)
        pos = 0
        for j in ws:
            L = len(kana(W[j][2]))
            o = ops[pos:pos + L]
            pos += L
            inside[j] = i
            ins_flag[j] = L > 0 and o.count("I") >= 0.8 * L
    out = []
    for j, w in enumerate(W):
        k = kana(w[2])
        if k in FILLER_STRONG and (inside[j] < 0 or ins_flag[j]):
            out.append([round(w[0], 2), w[2]])
    return out


def clicks(y):
    d2 = np.abs(np.diff(y, 2))
    w = int(0.005 * SR)
    ref = np.convolve(d2, np.ones(2 * w) / (2 * w), "same") + 1e-6
    c = np.flatnonzero((d2 > 0.02) & (d2 > 20 * ref))
    ts = sorted({round(i / SR, 2) for i in c})
    return [t for k, t in enumerate(ts) if k == 0 or t - ts[k - 1] > 0.02]


def zero_runs(y, min_len=0.02):
    z = np.abs(y) < 1e-4
    out, i, n = [], 0, len(z)
    idx = np.flatnonzero(np.diff(np.r_[0, z.astype(int), 0]))
    for a, b in zip(idx[::2], idx[1::2]):
        if (b - a) / SR >= min_len:
            out.append((a / SR, b / SR))
    return out


def hard_edges(y):
    h = int(0.005 * SR)
    n = len(y) // h
    e = 10 * np.log10(np.mean(y[:n * h].reshape(n, h) ** 2, 1) + 1e-12)
    top = np.percentile(e, 95)
    d = np.diff(e)
    loud = top - 25
    down = np.flatnonzero((d < -30) & (e[:-1] > loud))
    up = np.flatnonzero((d > 30) & (e[1:] > loud))
    return [round((i + 1) * 0.005, 3) for i in down], [round((i + 1) * 0.005, 3) for i in up]


def ma(path, W, c2w, tk, mins):
    x16 = load(path, 16000)
    sil = silences(x16, 16000, min_len=0.06)[0]
    ends, starts = [], []
    for t in tk:
        if t is not None:
            ends.append(W[int(c2w[max(t[2] - 1, 0)])][1])
            starts.append(W[int(c2w[t[1]])][0])
    ends, starts = np.array(sorted(ends)), np.array(sorted(starts))
    out = {"文中": [], "文間": []}
    for a, b in sil:
        hit = (len(ends) and np.any((ends >= a - 0.25) & (ends <= b + 0.1))) or (len(starts) and np.any((starts >= a - 0.1) & (starts <= b + 0.25)))
        k = "文間" if hit else "文中"
        out[k].append(b - a)
    allv = np.array(out["文中"] + out["文間"]) if out["文中"] or out["文間"] else np.zeros(1)
    res = {}
    for k, v in out.items():
        v = np.array(v) if v else np.zeros(1)
        res[k] = {"n": len(out[k]), **{"p%d" % p: round(float(np.percentile(v, p)), 3) for p in (25, 50, 75, 90, 95)}}
    res["全体"] = {"n": len(allv), "0.3秒以上/分": round(float((allv >= 0.3).sum() / mins), 2), "0.5秒以上/分": round(float((allv >= 0.5).sum() / mins), 2),
                 "1秒以上": int((allv >= 1.0).sum()), "最長": round(float(allv.max()), 2), "間の数/分": round(len(allv) / mins, 1)}
    return res


def adlib(raw_W, raw_T, raw_c2w, raw_tk, out_T, sents):
    """元の声で台本に当たらない かたまり（8字以上・つなぎ言葉だけでない・前後の文の言い直しでない）＝アドリブ。それが切った声に残っているか"""
    used = np.zeros(len(raw_T), bool)
    for t in raw_tk:
        if t is not None:
            used[t[1]:t[2]] = True
    runs, i, n = [], 0, len(raw_T)
    while i < n:
        if used[i]:
            i += 1
            continue
        j = i
        while j < n and not used[j]:
            j += 1
        runs.append((i, j))
        i = j
    first = min(t[1] for t in raw_tk if t is not None)
    last = max(t[2] for t in raw_tk if t is not None)
    res = []
    for a, b in runs:
        if a < first or b > last:
            continue                                     # 撮る前の声・撮った後の声
        k = "".join(raw_T[a:b])
        if len(k) < 8:
            continue
        near = [s["k"] for s in sents]
        if any(H.fit(np.array(list(k)), np.array(list(S)))[0].min() <= 0.35 * len(k) for S in near):
            continue                                     # 台本のどこかの言い直し
        D, _ = H.fit(np.array(list(k)), out_T)
        res.append({"t": round(raw_W[int(raw_c2w[a])][0], 1), "kana": k[:40], "len": len(k), "nokotta": bool(D.min() <= 0.25 * len(k))})
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("script")
    ap.add_argument("--raw", required=True)
    ap.add_argument("--okoshi")
    ap.add_argument("--raw-okoshi")
    ap.add_argument("--cut")
    ap.add_argument("-o", required=True)
    A = ap.parse_args()
    cache = os.path.join(os.path.dirname(os.path.abspath(A.o)), "cache")
    sents = split_sentences(open(A.script, encoding="utf-8-sig").read())
    for s in sents:
        s["k"] = kana(s["text"])
    W = words_of(A.wav, A.okoshi, cache)
    RW = words_of(A.raw, A.raw_okoshi, cache)
    T, c2w = chars(W)
    RT, rc2w = chars(RW)
    D_out, D_raw = sent_fit(sents, T), sent_fit(sents, RT)
    loss = [{"i": i + 1, "text": sents[i]["text"][:40], "kieta": D_out[i] - D_raw[i]} for i in range(len(sents)) if D_out[i] - D_raw[i] >= 2]
    tk, rtk = takes(sents, T), takes(sents, RT)
    y = load(A.wav)
    mins = len(y) / SR / 60
    fl = fillers_left(W, T, c2w, sents, tk)
    sk = "".join(s["k"] for s in sents)
    rep = kurikaeshi(T, sk)
    ck = clicks(y)
    zr = zero_runs(y)
    dn, up = hard_edges(y)
    al = adlib(RW, RT, rc2w, rtk, T, sents)
    res = {"wav": os.path.abspath(A.wav), "秒": round(len(y) / SR, 1),
           "①言葉の欠け": {"消えた字（元より増えた食い違い・2字以上の文の合計）": int(sum(l["kieta"] for l in loss)), "欠けた文": len(loss),
                       "1字以上増えた文": int(sum(1 for i in range(len(sents)) if D_out[i] > D_raw[i])), "台本の文": len(sents),
                       "一覧": sorted(loss, key=lambda l: -l["kieta"])[:40]},
           "②残ったつなぎ言葉": {"数": len(fl), "一覧": fl[:60]},
           "③残った言い直し（くり返し）": {"数": len(rep), "一覧": [[round(W[int(c2w[i])][0], 2), a] for i, L, g, a in rep][:60]},
           "④プツ音": {"数": len(ck), "1分あたり": round(len(ck) / mins, 2), "一覧": ck[:60]},
           "⑤無音0の区間（20ms以上）": {"本数": len(zr), "合計秒": round(sum(b - a for a, b in zr), 2), "1分あたり": round(len(zr) / mins, 2)},
           "⑥声の途中で切れた所（5msで30dB）": {"落ちる": len(dn), "上がる": len(up), "落ちる一覧": dn[:40], "上がる一覧": up[:40]},
           "⑦間": ma(A.wav, W, c2w, tk, mins),
           "⑧アドリブ": {"元にあった": len(al), "残った": sum(a["nokotta"] for a in al), "一覧": al}}
    if A.cut and os.path.exists(A.cut):
        res["切れ目の数"] = len(json.load(open(A.cut)).get("tsunagi", []))
    json.dump(res, open(A.o, "w"), ensure_ascii=False, indent=1)
    for k, v in res.items():
        if isinstance(v, dict):
            print(k, {kk: vv for kk, vv in v.items() if kk not in ("一覧", "落ちる一覧", "上がる一覧")})
        else:
            print(k, v)


if __name__ == "__main__":
    main()
