#!/usr/bin/env python3
# ナレーションのジャンプカット（撮り直し・言い直し・つなぎ言葉の多い生の声 → 編集者が切ったような声）（作業AI 2026-10-19）
#   依頼主 10/19 19:16「俺の声だと正しくジャンプカットって難しい？音声のカット微妙すぎてまじで壊滅的！ナレーションのジャンプカットも精度よくできたら最高」
#   使い方: narration/.venv/bin/python jumpcut.py 生の声.wav 出力フォルダ [--daihon 台本.txt] [--kakunin]
#   出力:   jumpcut.wav（切った声）・cut.json（カット表：残した区間・切れ目・消した所と理由）・cut.tsv（人が読む表）・kakunin.json（--kakunin のとき）
#   yt-henshu-pipe には切った声を渡す：python3 pipe/yt-pipe.py --koe <出力>/jumpcut.wav --daihon 台本.txt --out ...
#
#   決め方（前のやり方 henshu.py＋kiru_zen.py で壊れた所を1つずつ直した）
#   1 書き起こしが正（台本は撮る前・撮った後の声を見つけるのと、言い直しを「台本どおりの並び」と取り違えないためだけに使う）
#     依頼主は台本から言い換えて話すので、台本に当てて残す言葉を決めると話した文が落ちる（台本の文211のうち元の声で当たらない文が多い）
#   2 消すもの：撮る前・後の声／編集者さんへの指示・撮り直しの声／つなぎ言葉（えー・えっと・あのー…）／言い直し（同じ頭で言い直した前の回・言いかけ）
#     アドリブ（台本に無いが中身のある話）は残す。言い直しは【最後の回】を残す
#   3 切る位置は Whisper の時刻ではなく【声の大きさ】で決める：言葉の頭・語尾を、部屋の音より上の声が消える所まで探し、
#     頭に HEAD・語尾に TAIL の余白を必ず残す（値は元の声で測る：--hakaru-yohaku）。前のやり方は Whisper の時刻で切って頭・語尾を食った
#   4 間は消さない・0にしない：手本の作者さん15本の間の分布（文間・文中）に、この声の間を順位で写して詰める（長い間だけ詰まる）
#   5 間を埋めるのは【部屋の音】（元の声の静かな所）。前のやり方は無音0で埋め、部屋の音ごと消えてブツ切れに聞こえた
#   6 切れ目は 10ms のクロスフェード・ゼロ交差。音量は文ごとに ±4dB までそっと寄せる（前は ±10dB で段差が出た）→ 全体を手本の大きさ（LUFS）に
import argparse, json, os, re, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "narration"))
import henshu as H                                      # noqa: E402  fit・edit・level を借りる（henshu.py は変えない）
from common import load, save, kana, norm, split_sentences   # noqa: E402
import jumpcut_okoshi as OK                             # noqa: E402

SR = 48000
HOP = 0.005                       # 大きさを測る刻み（5ms）
TAKUTO = os.path.join(HERE, "jumpcut_tehon_ma.json")   # 手本の作者さん15本の間（jumpcut-1019/tehon_ma.py で作った）

# つなぎ言葉：言葉そのもの（Whisper が読点で区切ったもの）がこれなら消す
FILLER = {"えー", "えーと", "えっと", "えーっと", "ええと", "えぇ", "えと", "あのー", "あのぉ", "あー", "うーん", "うん", "んー", "ん", "まー", "そのー",
          "おー", "え", "あ", "っと", "と", "あの", "その", "なんか", "まあ", "まぁ", "ま"}
FILLER_ALWAYS = {"えー", "えーと", "えっと", "えーっと", "ええと", "えぇ", "えと", "あのー", "あのぉ", "あー", "うーん", "んー", "まー", "そのー", "おー", "っと"}
# 編集者さんへの指示・撮り直しの声
SHIJI = re.compile(r"(編集者さん|編集さん|へんしゅうしゃさん|素材を使って|素材は|撮っていきます|録っていく|撮っていく|撮り直|とりなお|もう一度|もう一回|もう1回|"
                   r"いきますね|通知音|カットして|切ってください|ポンって出して|って出してください|担当者から渡します|お世話になってます)")
PUNCT_END = "。？！?!"
PUNCT_ALL = "、。？！?!…"


# ================================================================ 大きさ
def env_db(x, sr=SR, hop=HOP, win=0.010):
    """5ms ごとの大きさ（dB）。120Hz より下（机の振動・吹かれ）を除いてから測る"""
    from scipy.signal import butter, sosfiltfilt
    y = sosfiltfilt(butter(2, 120, "high", fs=sr, output="sos"), x)
    h, w = int(sr * hop), int(sr * win)
    n = max(1, (len(y) - w) // h + 1)
    out = np.empty(n)
    for a in range(0, n, 40000):
        idx = np.arange(w)[None, :] + h * np.arange(a, min(n, a + 40000))[:, None]
        out[a:a + len(idx)] = np.sqrt(np.mean(y[idx] ** 2, 1) + 1e-12)
    return 20 * np.log10(out + 1e-9)


def quiet_runs(q, lo, hi, min_len):
    """q[lo:hi] の True の続き（刻みの番号）で min_len 刻み以上"""
    lo, hi = max(0, lo), min(len(q), hi)
    seg = q[lo:hi]
    if not len(seg):
        return []
    d = np.diff(np.r_[0, seg.astype(int), 0])
    st, en = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
    return [(lo + a, lo + b) for a, b in zip(st, en) if b - a >= min_len]


# ================================================================ 書き起こし → 句
def make_phrases(W):
    """言葉の並び → 句（読点・句点・…・0.35秒以上の間で切る）"""
    P, cur = [], []
    for i, w in enumerate(W):
        if cur and w[0] - W[cur[-1]][1] >= 0.35:
            P.append(cur); cur = []
        cur.append(i)
        if w[2] and w[2][-1] in PUNCT_ALL:
            P.append(cur); cur = []
    if cur:
        P.append(cur)
    out = []
    for ws in P:
        t = "".join(W[j][2] for j in ws)
        out.append({"w": ws, "text": t, "k": kana(t), "s": W[ws[0]][0], "e": W[ws[-1]][1],
                    "end": t[-1] if t and t[-1] in PUNCT_ALL else ""})
    return out


def bare(t):
    return re.sub(r"[、。？！?!…\s]", "", t)


# ================================================================ 消す所を決める
def decide(W, P, sents):
    """言葉ごとに 残す／消す と理由。返り値 keep[np.bool]・reason{言葉の番号: 理由}"""
    n = len(W)
    keep = np.ones(n, bool)
    reason = {}

    def drop(ws, why):
        for j in ws:
            if keep[j]:
                keep[j] = False
                reason[j] = why

    T = np.array(list("".join(kana(w[2]) for w in W)) or ["_"])
    c2w = []
    for i, w in enumerate(W):
        c2w += [i] * len(kana(w[2]))
    c2w = np.array(c2w + [n - 1])
    SK = "".join(s["k"] for s in sents) if sents else ""

    # 1 撮る前・撮った後：台本の最初の文・最後の文が元の声に当たる所より外
    if sents:
        def where(k, last=False):
            D, st = H.fit(np.array(list(k)), T)
            ok = np.flatnonzero(D <= max(2, 0.35 * len(k)))
            if not len(ok):
                return None
            j = ok[-1] if last else ok[int(np.argmin(D[ok]))]
            return int(st[j]), int(j)
        a = where(sents[0]["k"])
        if a:
            w0 = int(c2w[a[0]])
            drop(range(0, w0), "撮る前の声")
        z = where(sents[-1]["k"], last=True)
        if z:
            w1 = int(c2w[max(z[1] - 1, 0)])
            drop(range(w1 + 1, n), "撮った後の声")

    # 2 編集者さんへの指示・撮り直しの声（句ごと。句の半分以上が指示の言葉なら、続く短い句も）
    for p in P:
        if SHIJI.search(p["text"]):
            drop(p["w"], "編集者さんへの指示・撮り直しの声")

    # 3 つなぎ言葉
    for i, w in enumerate(W):
        t = bare(w[2])
        if not t:
            continue
        nxt = W[i + 1] if i + 1 < n else None
        gap_after = (nxt[0] - w[1]) if nxt else 1.0
        gap_before = (w[0] - W[i - 1][1]) if i else 1.0
        delimited = (w[2][-1] in PUNCT_ALL) or gap_after >= 0.15 or (nxt is not None and bare(nxt[2]) in FILLER_ALWAYS)
        if t in FILLER_ALWAYS or (t.replace("ー", "") in {"え", "あ", "ん", "えと"} and (delimited or gap_before >= 0.15)):
            drop([i], "つなぎ言葉")
        elif t in {"あの", "その", "まあ", "まぁ", "なんか", "ま"} and delimited and (t + "、") not in "".join(s["text"] for s in sents):
            drop([i], "つなぎ言葉")

    # 4 言い直し：後ろの句が同じ頭で言い直している → 前の句から後ろの句の手前まで消す（最後の回を残す）
    #   台本に「前の句＋後ろの句」の並びがあれば、台本どおりのくり返し（「コピーして、修正して」など）なので消さない
    live = [p for p in P if any(keep[j] for j in p["w"])]
    for a in range(len(live)):
        pa = live[a]
        ka = kana("".join(W[j][2] for j in pa["w"] if keep[j]))
        if len(ka) < 3:
            continue
        for b in range(a + 1, min(len(live), a + 14)):
            pb = live[b]
            if pb["s"] - pa["s"] > 60:
                break
            kb = kana("".join(W[j][2] for j in pb["w"] if keep[j]))
            if len(kb) < 2:
                continue
            # 前の句が、後ろの句（＋その次の2句）の頭の所に ほぼそのまま入っているか（「しかも1日で」→「しかもたった1日で」のように言葉を足した言い直しも拾う）
            kb2 = kb + "".join(kana("".join(W[j][2] for j in live[c]["w"] if keep[j])) for c in range(b + 1, min(len(live), b + 3)))
            head = kb2[:len(ka) + 8]
            D, _ = H.fit(np.array(list(ka)), np.array(list(head)))
            d = float(D.min())
            same_start = H.edit(ka[:3], kb[:3]) <= 1
            cut_off = pa["text"].endswith("…") and same_start and len(ka) >= 3
            close = b <= a + 2 and len(ka) >= 12 and d <= 0.25 * len(ka)   # 言葉の順を入れ替えた言い直し（「実際にこれで私は」→「これで実際私は」）
            if not (cut_off or (d <= 0.3 * len(ka) and (same_start or close))):
                continue
            if SK:
                pair = ka + "".join(kana("".join(W[j][2] for j in live[c]["w"] if keep[j])) for c in range(a + 1, b)) + kb[:min(10, len(kb))]
                D, _ = H.fit(np.array(list(pair)), np.array(list(SK)))
                if D.min() <= 0.15 * len(pair):
                    continue                              # 台本どおりのくり返し
            span = [j for c in range(a, b) for j in live[c]["w"]]
            if W[span[-1]][1] - W[span[0]][0] > 60:
                continue                                  # 60秒を超えて消すのは言い直しではない（同じ言い出しの別の話）
            drop(span, "言い直し（後の回を残した）")
            break

    # 5 言いかけ：短い句（6字まで）で「…」で終わる、または次の句がその頭で始まる
    live = [p for p in P if any(keep[j] for j in p["w"])]
    for a in range(len(live) - 1):
        pa, pb = live[a], live[a + 1]
        ka = kana("".join(W[j][2] for j in pa["w"] if keep[j]))
        kb = kana("".join(W[j][2] for j in pb["w"] if keep[j]))
        if not ka or len(ka) > 6:
            continue
        if pa["text"].endswith("…") or (len(ka) >= 2 and kb.startswith(ka[:2]) and ka not in SK):
            drop(pa["w"], "言いかけ")

    # 6 言葉のくり返し（同じ言葉2字以上がすぐ続く・台本に無い）
    for i in range(n - 1):
        if keep[i] and keep[i + 1]:
            k1, k2 = kana(W[i][2]), kana(W[i + 1][2])
            if len(k1) >= 2 and k1 == k2 and (k1 + k2) not in SK:
                drop([i], "言葉のくり返し")
    return keep, reason


def from_shijisho(W, sj):
    """指示書 → 言葉ごとの 残す／消す と理由（句の言葉の番号 w=[頭, 尻] を使う）"""
    keep, reason = [True] * len(W), {}
    seen = set()
    for k in sj["ku"]:
        a, b = k["w"]
        seen.update(range(a, b + 1))
        if k["hantei"] == "消す":
            for j in range(a, b + 1):
                keep[j] = False; reason[j] = k["riyuu"]
        elif k["hantei"] == "一部残す":
            na, nb = k["nokosu_w"]
            for j in range(a, b + 1):
                if not (na <= j <= nb):
                    keep[j] = False; reason[j] = k["riyuu"]
    assert seen == set(range(len(W))), "指示書の句が書き起こしの言葉を全部覆っていない（書き起こしと指示書が別物）"
    # 窓の差し替え：島ごとの起こしが言い直しの回を1回にまとめた所・つなぎ言葉を書かなかった所は、別の耳（かたまりの起こし）の言葉に入れ替え、
    #   消す時刻 kesu=[[始, 終, 理由]] に頭が入る言葉を消す（10/19：「そして今起きているのが…段階…」2回目・「この面…」・あのー・えっと）
    for m in sj.get("sashikae", []):
        a, b = m["mado"]
        alt = [list(w) for w in json.load(open(m["okoshi"])) if a <= w[0] < b]
        rest = [(w, k, reason.get(j)) for j, (w, k) in enumerate(zip(W, keep)) if not (a <= w[0] < b)]
        add = []
        for w in alt:
            why = next((z[2] for z in m["kesu"] if z[0] <= w[0] < z[1]), None)
            add.append((w, why is None, why))
        allw = sorted(rest + add, key=lambda t: t[0][0])
        W[:] = [t[0] for t in allw]
        keep = [t[1] for t in allw]
        reason = {j: t[2] for j, t in enumerate(allw) if t[2]}
    return keep, reason


# ================================================================ 切る位置・間
def refine(db, q, W, keep, HEAD, TAIL):
    """残す言葉の続き（かたまり）ごとに、声の大きさで頭と語尾を決める"""
    n = len(W)
    f = lambda t: int(round(t / HOP))
    groups, cur = [], []
    for j in range(n):
        if keep[j]:
            cur.append(j)
        elif cur:
            groups.append(cur); cur = []
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        a, b = g[0], g[-1]
        s, e = W[a][0], W[b][1]
        prev_e = W[a - 1][1] if a > 0 else 0.0
        next_s = W[b + 1][0] if b + 1 < n else len(q) * HOP
        # 頭：s+0.25 より前で終わる静かな所（40ms以上）のうち いちばん後ろの終わり＝声の立ち上がり。前の言葉の終わりより前には行かない
        lo = f(max(prev_e - 0.05, s - 1.5)) if a > 0 else f(max(0, s - 1.5))   # Whisper の時刻は語の頭を遅く・尻を早く書くことがある（1.5秒まで探す）
        # 頭の言葉の中の静けさ（っ・か行の閉じ・弱い「あ」）を頭と取り違えないよう、まず s+0.05 までで探し、無いときだけ s+0.25 まで広げる
        #  （10/19 判断カット：s+0.25 で探して「あと、まだ…」の「あと」、「そして、」の頭を食った）
        #  広げるのは 前の言葉との間が 0.15秒より長いときだけ（続けて話した所では、言葉の中の静けさしか見つからない）
        rs = [r for r in quiet_runs(q, lo, f(s + 0.05), 8) if r[1] * HOP <= s + 0.05] or \
             ([r for r in quiet_runs(q, lo, f(s + 0.25), 8) if r[1] * HOP <= s + 0.25] if s - prev_e > 0.15 else [])
        if rs:
            on, hard_s, qs = rs[-1][1] * HOP, False, rs[-1]
        else:
            w0, w1 = f(max(prev_e - 0.03, s - 0.15)), f(s + 0.05)
            on = (w0 + int(np.argmin(db[w0:w1 + 1]))) * HOP if w1 > w0 else s
            hard_s, qs = True, None
        # 語尾：e-0.25 より後に始まる静かな所（40ms以上）のうち いちばん前の始まり＝声が消えた所
        hi = f(min(next_s + 0.05, e + 1.5)) if b + 1 < n else f(min(len(q) * HOP, e + 1.5))   # 「と思います」を 0.3秒と書かれ、0.6秒で探して語尾を食った（10/19）
        # 語尾も同じ：まず e-0.05 より後の静けさ、無いときだけ e-0.25 まで（「決まってない。」の「い」を食った）
        #  広げるのは 次の言葉との間が 0.15秒より長いときだけ（「決まってない。そういう方には」を続けて話した所で「ない」を食った）
        rs = [r for r in quiet_runs(q, f(e - 0.05), hi, 8) if r[0] * HOP >= e - 0.05] or \
             ([r for r in quiet_runs(q, f(e - 0.25), hi, 8) if r[0] * HOP >= e - 0.25] if next_s - e > 0.15 else [])
        if rs:
            off, hard_e, qe = rs[0][0] * HOP, False, rs[0]
        else:
            w0, w1 = f(e - 0.05), f(min(next_s + 0.03, e + 0.15))
            off = (w0 + int(np.argmin(db[w0:w1 + 1]))) * HOP if w1 > w0 else e
            hard_e, qe = True, None
        out.append({"w": g, "on": on, "off": max(off, on + 0.05), "hard_s": hard_s, "hard_e": hard_e,
                    "room_before": (qs[1] - qs[0]) * HOP if qs else 0.0, "room_after": (qe[1] - qe[0]) * HOP if qe else 0.0})
    return out


def inner_pauses(q, g, W, min_len=0.25):
    """かたまりの中の自然な間：声の大きさで静かな所（min_len 以上）を全部拾う
    min_len は 0.25秒（10/19 判断カットで直した）：0.06秒だと「チャ|ット」「聞|けば」の詰まる音（っ・か行の閉じ）まで間と見て切り、言葉の中が割れた（Whisper の1語が間をまたいで長く書かれることがあるので、言葉の時刻は使わない）。
    種類（文間・文中）は、間の始まりにいちばん近い言葉の終わりの句読点で決める"""
    res = []
    a, b = int(g["on"] / HOP) + 1, int(g["off"] / HOP) - 1
    for r0, r1 in quiet_runs(q, a, b, int(round(min_len / HOP))):
        t0 = r0 * HOP
        j = min(g["w"][:-1] or g["w"], key=lambda k: abs(W[k][1] - t0))
        res.append({"after": j, "off": t0, "on": r1 * HOP})
    return res


def kind_of(W, j, sents_text=""):
    t = W[j][2]
    return "文間" if t and t[-1] in PUNCT_END else "文中"


def grid_of(tk, kind):
    return np.array(tk[kind]["grid"])


def plan_gaps(segs, HEAD, TAIL, tk):
    """切れ目ごとに目標の間を決める：この声の間の順位 → 手本の作者さんの同じ順位の長さ（長い方だけ詰める・伸ばさない）"""
    by = {"文間": [], "文中": []}
    for g in segs:
        by[g["kind"]].append(g)
    for k, lst in by.items():
        if not lst:
            continue
        v = np.array([g["nat"] for g in lst])
        r = v.argsort().argsort()
        G = grid_of(tk, k)
        for g, rr in zip(lst, r):
            pct = (rr + 0.5) / len(lst) * 100
            tgt = float(np.interp(min(pct, 98.0), np.arange(101), G))
            g["target"] = round(min(g["nat"], tgt) if not g["cut_needed"] else tgt, 3)
    return segs


# ================================================================ 組み立て
def zc(x, i, w=144):
    """i の近く（±3ms）のゼロ交差"""
    a, b = max(1, i - w), min(len(x) - 1, i + w)
    s = np.flatnonzero(np.signbit(x[a - 1:b - 1]) != np.signbit(x[a:b]))
    return a + int(s[np.argmin(np.abs(s + a - i))]) if len(s) else i


class Bed:
    """部屋の音（元の声の静かな所を集めたもの）から長さ L の音を出す"""
    def __init__(self, x, q):
        parts = []
        for a, b in quiet_runs(q, 0, len(q), int(0.3 / HOP)):
            a2, b2 = int((a * HOP + 0.06) * SR), int((b * HOP - 0.06) * SR)
            if b2 - a2 > int(0.15 * SR):
                parts.append(x[a2:b2])
        self.bed = np.concatenate(parts) if parts else np.zeros(SR, np.float32)
        self.pos = 0

    def take(self, L):
        n = int(L * SR)
        if n <= 0:
            return np.zeros(0, np.float32)
        if self.pos + n > len(self.bed):
            self.pos = 0
        out = self.bed[self.pos:self.pos + n]
        if len(out) < n:
            out = np.resize(self.bed, n)
        self.pos += n
        return out.astype(np.float32)


def join(parts, xf=0.010):
    """部品を順に等パワーのクロスフェードでつなぐ"""
    n = int(xf * SR)
    out = [parts[0]]
    tot = len(parts[0])
    for p in parts[1:]:
        a = out[-1]
        if len(a) < n or len(p) < n:
            out.append(p); tot += len(p); continue
        t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
        mid = a[-n:] * np.cos(t) + p[:n] * np.sin(t)
        out[-1] = a[:-n]
        out += [mid, p[n:]]
        tot += len(p) - n
    return np.concatenate(out).astype(np.float32)


# ================================================================ 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--daihon")
    ap.add_argument("--okoshi", help="元の声の書き起こし（jumpcut_okoshi.py の出力）を使い回す")
    ap.add_argument("--head", type=float, default=None, help="言葉の頭の余白（秒）。無ければ元の声で測った値")
    ap.add_argument("--tail", type=float, default=None, help="語尾の余白（秒）。無ければ元の声で測った値")
    ap.add_argument("--kakunin", action="store_true", help="切った声をもう一度起こして、残すと決めた言葉が全部あるか確かめる")
    ap.add_argument("--shijisho", help="判断カットの指示書（作業AIが1句ずつ決めた 残す／消す／一部残す と理由）。あれば決まりで決めず、これに従う")
    A = ap.parse_args()
    os.makedirs(A.out, exist_ok=True)
    cache = os.path.join(A.out, "cache")
    x = load(A.audio)
    W = json.load(open(A.okoshi)) if A.okoshi else OK.okosu(OK.load16(A.audio), cache)
    sents = []
    if A.daihon:
        sents = split_sentences(open(A.daihon, encoding="utf-8-sig").read())
        for s in sents:
            s["k"] = kana(s["text"])
    print("元の声 %.1f秒 ／ 言葉 %d ／ 台本の文 %d" % (len(x) / SR, len(W), len(sents)), file=sys.stderr)

    # ---- 大きさ：静か＝部屋の音（10%点）から 6dB 以内
    db = env_db(x)
    floor = float(np.percentile(db, 10))
    top = float(np.percentile(db, 95))
    thr = max(top - 30.0, floor + 8.0)          # 手本の作者さんの間を測った式（common.silences）と同じ線
    q = db < thr
    # 息：言葉の無い所（Whisper の言葉の前後 30ms の外）で、声より 22dB 以上小さい音は「間」に入れる（息を吸う音は消す・前は声として残り、間が長くなった）
    cov = np.zeros(len(q), bool)
    for w in W:
        cov[max(0, int((w[0] - 0.03) / HOP)):int((w[1] + 0.03) / HOP) + 1] = True
    breath = (~cov) & (~q) & (db < top - 22)
    q = q | breath

    # ---- 余白を測る：長い間（0.3秒以上）に接する言葉の頭・語尾で、「部屋の音より 6dB 上」を越えてから声らしい大きさ（上から30dB下）に届くまで／
    #      語尾は声らしい大きさを下回ってから 部屋の音より 6dB 上を下回るまで ＝ 弱い子音・息・語尾の消え入りの長さ
    loud = db > thr + 6
    rise, fall = [], []
    for a, b in quiet_runs(q, 0, len(q), int(0.3 / HOP)):
        k = b
        while k < len(db) and not loud[k] and k - b < 60:
            k += 1
        if k - b < 60:
            rise.append((k - b) * HOP)
        k = a - 1
        while k > 0 and not loud[k] and a - k < 60:
            k -= 1
        if a - k < 60:
            fall.append((a - k) * HOP)
    rise, fall = np.array(rise), np.array(fall)
    HEAD = A.head if A.head is not None else float(np.clip(round(np.percentile(rise, 75) + 0.02, 3), 0.04, 0.10))
    TAIL = A.tail if A.tail is not None else float(np.clip(round(np.percentile(fall, 75) + 0.04, 3), 0.08, 0.16))
    yohaku = {"頭の立ち上がり_中央": round(float(np.median(rise)), 3), "頭_90%": round(float(np.percentile(rise, 90)), 3),
              "頭_75%": round(float(np.percentile(rise, 75)), 3), "語尾の消え入り_中央": round(float(np.median(fall)), 3),
              "語尾_75%": round(float(np.percentile(fall, 75)), 3), "語尾_90%": round(float(np.percentile(fall, 90)), 3),
              "測った数": [len(rise), len(fall)], "HEAD": HEAD, "TAIL": TAIL, "部屋の音dB": round(floor, 1), "声dB_95%": round(top, 1)}
    print("余白", yohaku, file=sys.stderr)

    # ---- 消す所
    P = make_phrases(W)
    if A.shijisho:
        keep, reason = from_shijisho(W, json.load(open(A.shijisho)))
    else:
        keep, reason = decide(W, P, sents)
    groups = refine(db, q, W, keep, HEAD, TAIL)

    # ---- 切れ目（かたまりの間＝消した所の前後・かたまりの中の長い自然な間）
    tk = json.load(open(TAKUTO))
    segs = []      # 声の部品（元の秒 [a, b]）と、その後ろの間
    for gi, g in enumerate(groups):
        cuts = inner_pauses(q, g, W)
        st = g["on"]
        for c in cuts:
            nat = c["on"] - c["off"]
            segs.append({"a": st, "b": c["off"], "kind": kind_of(W, c["after"]), "nat": round(nat, 3), "cut_needed": False,
                         "after_w": c["after"], "hard": False, "inner": True, "off": c["off"], "on": c["on"]})
            st = c["on"]
        nxt = groups[gi + 1] if gi + 1 < len(groups) else None
        nat = (g["room_after"] + nxt["room_before"]) if nxt else 0.0
        segs.append({"a": st, "b": g["off"], "kind": kind_of(W, g["w"][-1]), "nat": round(min(nat, 2.0), 3), "cut_needed": True,
                     "after_w": g["w"][-1], "hard": g["hard_e"] or (nxt["hard_s"] if nxt else False), "inner": False,
                     "off": g["off"], "on": nxt["on"] if nxt else None, "last": nxt is None})
    plan_gaps([s for s in segs if not s.get("last")], HEAD, TAIL, tk)

    # ---- 組み立て：声の部品＋（間が目標より長い所だけ）部屋の音でつなぐ
    bed = Bed(x, q)
    parts, table, tsunagi = [], [], []
    pos = 0.0
    i = 0
    xf = 0.010
    while i < len(segs):
        s = segs[i]
        a0 = s["a"] - HEAD                          # 部品の頭（声の立ち上がりの HEAD 前）
        if parts and not s.get("_joined"):
            pass
        # 自然な間が目標以下なら、次の部品とつないだまま（切らない）
        j = i
        while j < len(segs) - 1 and segs[j]["inner"] and segs[j]["target"] >= segs[j]["nat"] - 0.005:
            j += 1
        e = segs[j]
        b0 = e["b"] + TAIL                           # 部品の終わり（声が消えてから TAIL 後）
        if e.get("last"):
            b0 = e["b"] + max(TAIL, 0.35)            # 最後の言葉は余韻を残す（「ございました」の消え入りを切らない）
        if e.get("on") is not None and not e.get("last"):
            b0 = min(b0, e["b"] + max(TAIL, 0.5 * (e["on"] - e["b"])) if e["inner"] else b0)
        ia, ib = zc(x, int(max(0, a0) * SR)), zc(x, int(min(len(x) / SR, b0) * SR))
        seg = x[ia:ib].copy()
        parts.append(seg)
        table.append({"moto": [round(ia / SR, 3), round(ib / SR, 3)], "ato": round(pos, 3),
                      "text": "".join(W[w][2] for w in range(len(W)) if keep[w] and ia / SR - 0.02 <= W[w][0] < ib / SR)})
        pos += len(seg) / SR - (xf if len(parts) > 1 else 0)
        if not e.get("last"):
            # この部品の後ろの間（出来上がりの静かな長さ）＝ TAIL ＋ 部屋の音 ＋ 次の頭の HEAD（＋つなぎ目の重なり分を足す）
            fill = max(0.0, e["target"] - TAIL - HEAD) + 2 * xf
            parts.append(bed.take(fill))
            pos += fill - xf
            tsunagi.append({"ato": round(pos, 3), "kind": e["kind"], "nat": e["nat"], "target": e["target"], "hard": e["hard"],
                            "naka": e["inner"], "moto_mae": round(ib / SR, 3), "moto_ato": round(segs[j + 1]["a"] - HEAD, 3) if j + 1 < len(segs) else None})
        i = j + 1
    y = join(parts, xf)

    # ---- 音量：文（句点まで）ごとの声の大きさを ±4dB までそっと寄せる → 全体を手本の大きさに
    dby = env_db(y)
    vm = dby > max(float(np.percentile(dby, 95)) - 30, float(np.percentile(dby, 10)) + 12)
    med_all = float(np.median(dby[vm])) if vm.any() else -20.0
    g = np.ones(len(y), np.float32)
    bounds = [0.0] + [t["ato"] for t in tsunagi if t["kind"] == "文間"] + [len(y) / SR]
    gains = []
    for a, b in zip(bounds, bounds[1:]):
        ia, ib = int(a / HOP), int(b / HOP)
        m = vm[ia:ib]
        if m.sum() < 20:
            gains.append(0.0); continue
        gains.append(float(np.clip(0.6 * (med_all - np.median(dby[ia:ib][m])), -4, 4)))
    for (a, b), gd in zip(zip(bounds, bounds[1:]), gains):
        g[int(a * SR):int(b * SR)] = 10 ** (gd / 20)
    k = int(0.05 * SR)
    g = np.convolve(g, np.ones(k) / k, "same").astype(np.float32)      # 50ms でならす（間の中で変わる）
    y = y * g
    ref = json.load(open(os.path.join(HERE, "narration", "ref_stats.json")))
    lv = H.level(y, ref)
    y = lv.pop("y")
    save(os.path.join(A.out, "jumpcut.wav"), y)

    # ---- カット表
    kesu, j = [], 0
    while j < len(W):
        if keep[j]:
            j += 1; continue
        k2 = j
        while k2 + 1 < len(W) and not keep[k2 + 1] and reason.get(k2 + 1) == reason.get(j):
            k2 += 1
        kesu.append({"moto": [round(W[j][0], 2), round(W[k2][1], 2)], "why": reason.get(j), "text": "".join(W[t][2] for t in range(j, k2 + 1))})
        j = k2 + 1
    nk = {}
    for kk in kesu:
        nk[kk["why"]] = nk.get(kk["why"], 0) + 1
    rep = {"moto": os.path.abspath(A.audio), "moto_sec": round(len(x) / SR, 2), "ato_sec": round(len(y) / SR, 2), "yohaku": yohaku,
           "kesu_kazu": nk, "tsunagi_kazu": len(tsunagi), "hard": sum(t["hard"] for t in tsunagi),
           "ma": {k: {"n": sum(1 for t in tsunagi if t["kind"] == k), "nat_p50": round(float(np.median([t["nat"] for t in tsunagi if t["kind"] == k] or [0])), 3),
                      "target_p50": round(float(np.median([t["target"] for t in tsunagi if t["kind"] == k] or [0])), 3)} for k in ("文間", "文中")},
           "onryou": {"文ごとの寄せ_dB": [round(v, 1) for v in gains[:400]], **{k: v for k, v in lv.items()}},
           "nokosu": table, "tsunagi": tsunagi, "kesu": kesu,
           "nokosu_text": "".join(W[t][2] for t in range(len(W)) if keep[t])}
    json.dump(rep, open(os.path.join(A.out, "cut.json"), "w"), ensure_ascii=False, indent=1)
    with open(os.path.join(A.out, "cut.tsv"), "w") as f:
        f.write("種類\t元の秒\t切った後の秒\t理由・間\t言葉\n")
        ev = [(k["moto"][0], "消す", "%.2f〜%.2f" % tuple(k["moto"]), "", k["why"], k["text"]) for k in kesu] + \
             [(t["moto_mae"], "つなぐ", "%.2f→%s" % (t["moto_mae"], t["moto_ato"]), "%.2f" % t["ato"],
               "%s 間 %.2f→%.2f%s" % (t["kind"], t["nat"], t["target"], "（声の切れ目なし・最小の所で切った）" if t["hard"] else ""), "") for t in tsunagi]
        for e_ in sorted(ev, key=lambda e: e[0]):
            f.write("\t".join(e_[1:]) + "\n")
    print("切った声 %.1f秒（元 %.1f秒）／ 切れ目 %d（声の途切れの無い所 %d）／ 消した %s" % (len(y) / SR, len(x) / SR, len(tsunagi), rep["hard"], nk), file=sys.stderr)

    if A.kakunin:
        kakunin(A.out, rep, cache)


def kakunin(out, rep, cache):
    """切った声をもう一度起こし、残すと決めた言葉（nokosu_text）の並びがそろっているか：句ごとに当てて、欠けた字を数える"""
    y16 = OK.load16(os.path.join(out, "jumpcut.wav"))
    W2 = OK.okosu(y16, cache)
    json.dump(W2, open(os.path.join(out, "okoshi_jumpcut.json"), "w"), ensure_ascii=False)
    T2 = np.array(list("".join(kana(w[2]) for w in W2)) or ["_"])
    ref_phr = [p for p in re.split(r"[、。？！?!…]", rep["nokosu_text"]) if kana(p)]
    miss, pos = [], 0
    for p in ref_phr:
        k = kana(p)
        lo, hi = max(0, pos - 40), min(len(T2), pos + len(k) + 80)
        D, st = H.fit(np.array(list(k)), T2[lo:hi])
        j = int(np.argmin(D))
        if D[j] >= max(2, 0.3 * len(k)):
            D, st = H.fit(np.array(list(k)), T2)          # 近くに無ければ全体から
            j = int(np.argmin(D)); lo = 0
        else:
            pos = lo + j
        if D[j] >= 2:
            miss.append({"ku": p, "kakeji": int(D[j])})
    res = {"残すと決めた句": len(ref_phr), "欠けた字が2字以上の句": len(miss), "欠けた字の合計": int(sum(m["kakeji"] for m in miss)), "一覧": miss}
    json.dump(res, open(os.path.join(out, "kakunin.json"), "w"), ensure_ascii=False, indent=1)
    print("確かめ", {k: v for k, v in res.items() if k != "一覧"}, file=sys.stderr)


if __name__ == "__main__":
    main()
