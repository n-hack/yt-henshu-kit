# ナレーションの下ごしらえ（プロの編集者がやる「声の編集」）
#   生のナレーション音声＋台本 → 編集済みの声（wav）＋文・言葉ごとの時刻（json）＋何をしたかの一覧
# 使い方: .venv/bin/python henshu.py 生の声.wav 台本.txt 出力フォルダ [--stretch rubberband|atempo] [--no-speed] [--no-gap]
#
# やること（順番）
#   1 下ごしらえ：低い音のカット・吹かれ（低い「ボフッ」）とリップノイズ（「プチッ」）を消す・部屋のノイズを減らす
#   2 文字起こし（whisper large-v3・言葉ごとの時刻）。拾い漏れた声の所だけ切り出してもう一度
#   3 台本の文と並べる（かなの読みで1字ずつ）。同じ文を何回か言った所は【最後のきれいな1回】を残す
#     （台本どおりに言えている回が別にあれば、そちらを優先）。言いかけ・つなぎ言葉・噛み・台本に無い独り言を消す
#   4 速さ：ナレーション全体で倍率を1つ（文ごとには伸縮しない）。全体の話す速さが見本202本の範囲（25%〜75%）から外れていれば中央へ
#   5 間：無音・息継ぎを、見本で測った無音の長さの分布（文中・文間・強調の前・場面の切り替わり）に合わせて詰める／足す
#   6 音量：文ごとの大きさをそろえ、見本の声の大きさ（LUFS）に合わせる
#   7 編集済みの声をもう一度文字起こしして、文・言葉ごとの時刻を出す（テロップの出入りに使う）。台本の文が1回ずつあるかも確かめる
#     出力：mojiokoshi.txt（生の声を whisper large-v3 で起こした文字＝声のとおりの台本）・mojiokoshi_henshu.txt（編集後の声の文字）・henshu.wav（編集済みの声）・jikoku.json（文と言葉の時刻。s_edit/e_edit は組み立ての記録＝確実な位置）・kiroku.md/json（消した一覧・速さ・間・見本との比べ）
# 試し：test/run_all.sh（わざと間違いを混ぜた試し音声2本＋人の生声2本）→ hyouka.py が取りこぼし・消しすぎを数える
import argparse, hashlib, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
from scipy.signal import butter, sosfilt
from common import (HERE, SR, HOP, PROMO, EMPH, FILLERS, FILLER_STRONG, load, save, frame_db, voice_mask, runs,
                    kana, mora, norm, split_sentences, SMALL, mlx_tight, short_sentences)

WHISPER = "mlx-community/whisper-large-v3-mlx"
PROMPT = "えー、あのー、えっと、まあ、そのー、うーん。"   # つなぎ言葉も書き起こさせるための呼び水（文の言葉を入れると、それを聞き違えて書く：「えっと」→「ということで」）
XF = 0.006          # つなぎ目のクロスフェード（秒）
LEAD, TAIL = 0.03, 0.07   # 声の前後に残す余白（子音の立ち上がり・語尾の息）
RETRY = [(0.25, PROMPT), (0.25, None), (0.1, None), (0.5, None)]   # 拾い漏れの読み直し（余白・呼び水）。前から順に試す
HALLU = re.compile(r"(ご視聴|ご覧いただき|最後までご覧).*ありがとうございま")   # 無音・音楽で whisper が書く決まり文句
KEEP_VOICE = 0.6    # 〔声〕（字にならなかった声）がこれより長ければ消さない：息・うなりは短い。長いのは whisper が書けなかった本文（10/16 HBg 7.9秒）


# ================================================================ 1 下ごしらえ
def preclean(x, log):
    """吹かれ（120Hz以下が急に強い所）だけ 180Hz の高域通過に差し替え → ffmpeg で 低域カット・クリック除去・ノイズ除去"""
    lo = sosfilt(butter(4, 120, "low", fs=SR, output="sos"), x)
    hp = sosfilt(butter(4, 180, "high", fs=SR, output="sos"), x)
    h = int(SR * HOP)
    n = len(x) // h
    el = 10 * np.log10(np.mean(lo[:n * h].reshape(n, h) ** 2, 1) + 1e-12)
    ea = 10 * np.log10(np.mean(x[:n * h].reshape(n, h) ** 2, 1) + 1e-12)
    top = np.percentile(ea, 95)
    r = el - ea
    # 吹かれ＝低い音が全体のほぼ全部で、声のいちばん大きい所（95%点）より大きく、直前から急に 12dB 以上跳ね上がり、0.15秒までで終わる。
    # 低い声の人は低音の割合が高いだけで、ここまで大きく・急にはならない（試しで 声の頭 106か所 → 本物 3か所）
    jump = np.r_[0, np.diff(el)]
    cand = (r > -3.0) & (el > top - 3)
    pop = np.zeros_like(cand)
    for a_, b_ in runs(cand, True):
        if b_ - a_ <= 15 and jump[max(0, a_ - 1):a_ + 2].max() > 12:
            pop[a_:b_] = True
    w = np.zeros(len(x), np.float32)
    k = 0
    for a, b in runs(pop, True):
        a, b = max(0, a - 2), min(n, b + 3)
        w[a * h:b * h] = 1
        k += 1
    if k:
        ramp = int(0.005 * SR)
        w = np.convolve(w, np.ones(ramp) / ramp, mode="same")
        x = x * (1 - w) + hp * w
    log.append({"what": "吹かれを消した", "n": k, "times": [round(a * HOP, 2) for a, b in runs(pop, True)][:200]})
    tmp = tempfile.mkdtemp()
    save(f"{tmp}/a.wav", x)
    af = "highpass=f=70:poles=2,adeclick=window=40:overlap=75:threshold=4,afftdn=nr=12:nf=-50:tn=1"
    subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-y", "-i", f"{tmp}/a.wav", "-af", af, "-ar", str(SR), f"{tmp}/b.wav"], check=True)
    y = load(f"{tmp}/b.wav")
    # ノイズ除去・クリック除去は音を少し遅らせる（試しで 1192標本＝約25ms）。元の時刻とそろうよう戻す
    lag = delay(x, y)
    if lag:
        y = np.concatenate([y[lag:], np.zeros(lag, np.float32)])
    log.append({"what": "整えたときの遅れを戻した", "samples": int(lag)})
    # リップノイズ（短いクリック）を数える：ほぼ1刻み未満の鋭い山が消えた所
    n2 = min(len(x), len(y))
    dx, dy = np.abs(np.diff(x[:n2])), np.abs(np.diff(y[:n2]))
    # 1標本の段差が大きく（0.15以上）、整えた後に 1/5 以下になった所だけ数える（声の立ち上がりは整えても段差が残る）
    h2 = 48
    dyw = np.maximum.reduceat(dy, np.arange(0, len(dy), h2))
    clicks = [c for c in np.flatnonzero(dx > 0.15) if dyw[min(c // h2, len(dyw) - 1)] < 0.2 * dx[c]]
    ct = sorted({round(c / SR, 2) for c in clicks})
    merged = [t for i, t in enumerate(ct) if i == 0 or t - ct[i - 1] > 0.05]
    log.append({"what": "リップノイズを消した（クリック）", "n": len(merged), "times": merged[:200]})
    log.append({"what": "部屋のノイズを減らした", "filter": af})
    return y.astype(np.float32)


def delay(x, y, maxlag=4800):
    """y が x より何標本遅れているか（声のいちばん大きい2秒で相互相関）"""
    h = int(SR * HOP)
    n = len(x) // h
    e = np.mean(x[:n * h].reshape(n, h) ** 2, 1)
    w = int(2 / HOP)
    c = np.convolve(e, np.ones(w), mode="valid")
    i0 = int(np.argmax(c)) * h if len(c) else 0
    a = x[i0:i0 + 2 * SR]
    b = y[i0:i0 + 2 * SR + maxlag]
    if len(b) < len(a) + maxlag:
        return 0
    from scipy.signal import correlate
    r = correlate(b, a, mode="valid", method="fft")
    return int(np.argmax(r))


# ================================================================ 2 文字起こし
def transcribe(x, cache, prompt=PROMPT):
    import mlx_whisper
    mlx_tight()   # GPU の溜めを 2GB まで（無いと起こすたびに太る）
    key = hashlib.md5(x[::7].tobytes() + (WHISPER + prompt).encode()).hexdigest()[:16]   # 呼び水を変えたら読み直す
    f = cache / f"whisper-{key}.json"
    if f.exists():
        return json.load(open(f))
    x16 = resample16(x)
    r = mlx_whisper.transcribe(x16, path_or_hf_repo=WHISPER, language="ja", word_timestamps=True,
                               condition_on_previous_text=False, initial_prompt=prompt or None, temperature=0.0,
                               no_speech_threshold=0.3, hallucination_silence_threshold=1.0)
    words = [[w["start"], w["end"], w["word"].strip()] for s in r["segments"] for w in s.get("words", []) if w["word"].strip()]
    del r, x16
    mlx_tight().clear_cache()
    json.dump(words, open(f, "w"), ensure_ascii=False)
    return words


def resample16(x):
    r = subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-", "-ar", "16000", "-f", "f32le", "-"],
                       input=x.astype(np.float32).tobytes(), capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.float32).copy()


def fill_missed(x, words, mask, cache, log):
    """声があるのに言葉が1つも無い所（whisper の拾い漏れ・つなぎ言葉）だけ切り出してもう一度"""
    import mlx_whisper
    mlx_tight()   # GPU の溜めを 2GB まで（無いと起こすたびに太る）
    covered = np.zeros(len(mask), bool)
    for s, e, _ in words:
        covered[int(s / HOP):int(e / HOP) + 1] = True
    add, holes = [], []
    for a, b in runs(mask & ~covered, True):
        if (b - a) * HOP < 0.25:
            continue
        holes.append((a * HOP, b * HOP))
    # 近い穴はまとめる
    merged = []
    for s, e in holes:
        if merged and s - merged[-1][1] < 0.3:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    retried = []
    for s, e in merged:
        # 1回目は呼び水つき（つなぎ言葉を拾う）。長い穴で字が少なすぎる・決まり文句の幻（「ご視聴ありがとうございました」）なら、
        # 呼び水なし・切り出しの余白を変えて読み直す（10/16 HBg：8秒の本文が幻になり〔声〕として消えていた。呼び水なしで本文が出た）
        best = []
        for k, (pad, pr) in enumerate(RETRY):
            a, b = max(0, s - pad), min(len(x) / SR, e + pad)
            seg = resample16(x[int(a * SR):int(b * SR)])
            r = mlx_whisper.transcribe(seg, path_or_hf_repo=WHISPER, language="ja", word_timestamps=True,
                                       condition_on_previous_text=False, initial_prompt=pr, temperature=0.0)
            got = [[a + w["start"], a + w["end"], w["word"].strip()] for sg in r["segments"] for w in sg.get("words", [])
                   if w["word"].strip() and a + w["end"] > s - 0.05 and a + w["start"] < e + 0.05]
            # 前後の既にある言葉と重なるものは捨てる
            got = [g for g in got if not any(g[0] < w[1] - 0.05 and g[1] > w[0] + 0.05 for w in words)]
            txt = norm("".join(g[2] for g in got))
            # すぐ隣の言葉の一部をもう一度書いただけ（10/16 HBg「ありがとうございました」0.22秒の後ろを「がとう ござ いました」と読み直した）は足さない
            nb = [norm(w[2]) for w in words if (0 <= s - w[1] < 0.3) or (0 <= w[0] - e < 0.3)]
            if txt and any(txt in t for t in nb):
                got, txt = [], ""
            cps = len(txt) / max(e - s, 0.01)
            if HALLU.search(txt) and cps < 4:
                got, txt = [], ""
            if len(txt) > len(norm("".join(g[2] for g in best))):
                best = got
            if best and (e - s < 1.5 or len(norm("".join(g[2] for g in best))) / (e - s) >= 2.5):
                break
        if k:
            retried.append([round(s, 2), round(e, 2), k, "".join(g[2] for g in best)[:40]])
        if best:
            add += best
        else:
            add.append([s, e, "〔声〕"])        # 字にならない声（息・うなり）も印をつけておく
    log.append({"what": "文字起こしの拾い漏れを切り出して読み直した", "n": len(merged), "retried": retried,
                "found": [[round(w[0], 2), round(w[1], 2), w[2]] for w in add][:100]})
    return sorted(words + add, key=lambda w: w[0])


# ================================================================ 3 台本と並べる
def fit(S, T):
    """S（台本の文の読み）を T（文字起こしの読み）のどこか一部分に当てる。返り値：各終わり位置での食い違いの数・始まり位置"""
    n = len(T)
    prev = np.zeros(n + 1)
    pst = np.arange(n + 1)
    ar = np.arange(n + 1)
    for c in S:
        sub = (T != c).astype(float)
        diag, up = prev[:-1] + sub, prev[1:] + 1
        cur = np.empty(n + 1)
        cst = np.empty(n + 1, int)
        cur[0], cst[0] = prev[0] + 1, pst[0]
        cur[1:] = np.minimum(diag, up)
        cst[1:] = np.where(diag <= up, pst[:-1], pst[1:])
        W = cur - ar
        cm = np.minimum.accumulate(W)
        arg = np.maximum.accumulate(np.where(W <= cm, ar, -1))
        new = cm + ar
        better = new < cur
        cst = np.where(better, cst[arg], cst)
        cur = np.where(better, new, cur)
        prev, pst = cur, cst
    return prev, pst


def edit(a, b):
    """普通の編集距離"""
    if not a:
        return len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def align_ops(S, T):
    """全体どうしの並べ方。T の1字ずつに 'M'（台本の字に当たる）か 'I'（台本に無い）を返す"""
    m, n = len(S), len(T)
    D = np.zeros((m + 1, n + 1), int)
    D[:, 0] = np.arange(m + 1)
    D[0, :] = np.arange(n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            D[i, j] = min(D[i - 1, j] + 1, D[i, j - 1] + 1, D[i - 1, j - 1] + (S[i - 1] != T[j - 1]))
    ops, i, j = ["I"] * n, m, n
    pairs = []
    while i > 0 and j > 0:
        if D[i, j] == D[i - 1, j - 1] + (S[i - 1] != T[j - 1]):
            ops[j - 1] = "M"
            pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif D[i, j] == D[i, j - 1] + 1:
            j -= 1
        else:
            i -= 1
    return ops, pairs[::-1]


def candidates(Sk, Tarr, max_d=0.5):
    """台本の1文が言われた所の候補（似ている度合い sim・始まり・終わり。字の位置）"""
    m = len(Sk)
    D, st = fit(np.array(list(Sk)), Tarr)
    lim = max_d * m
    w = max(2, m // 2)
    out = []
    for j in np.flatnonzero(D <= lim):
        lo, hi = max(0, j - w), min(len(D), j + w + 1)
        if D[j] == D[lo:hi].min():
            out.append((1 - D[j] / m, int(st[j]), int(j)))
    out.sort(key=lambda c: -c[0])
    kept = []
    for c in out:
        if all(min(c[2], k[2]) - max(c[1], k[1]) < 0.5 * (c[2] - c[1]) for k in kept) and c[2] > c[1]:
            kept.append(c)
    return sorted(kept, key=lambda c: c[1])


def choose(cands, n_chars):
    """文ごとに1回を選ぶ（順番は台本どおり）。きれいな回（いちばん台本に近い回から 0.06 以内）の中で【最後の回】を選ぶ"""
    N = len(cands)
    score = []
    for cs in cands:
        if not cs:
            score.append([])
            continue
        best = max(c[0] for c in cs)
        score.append([(10 if c[0] >= best - 0.06 else 0) + c[0] + 0.5 * c[1] / max(n_chars, 1) for c in cs])
    # 動的計画法：状態＝(文 i で選んだ候補 k)。「選ばない」も許す（点 0）
    NEG = -1e9
    best = [{-1: (0.0, None)}]
    for i in range(N):
        cur = {}
        for k, c in enumerate(cands[i]):
            bv, bp = NEG, None
            for pk, (pv, _) in best[i].items():
                pend = -1 if pk == -1 else best_end(best, i, pk, cands)
                # 隣の文と端が数字重なるのは、文字起こしの区切りがずれただけ（重なりは後で切り分ける）。前は2字までしか許さず、話した文を丸ごと落としていた（10/16 HBg 10文）
                if c[1] >= pend - max(2, int(0.25 * (c[2] - c[1]))) and pv > bv:
                    bv, bp = pv, pk
            if bp is not None or bv > NEG:
                cur[k] = (bv + score[i][k], bp)
        # 選ばない：前の終わりを引き継ぐ
        pv, pk = max(((v[0], k) for k, v in best[i].items()), key=lambda t: t[0])
        cur[("skip", pk)] = (pv - 60, pk)   # 文を落とす＝話した言葉を消す。候補がある限り選ぶ側に倒す（前は -5 で、重なり1つで落としていた）
        best.append(cur)
    # たどり戻す
    k = max(best[N], key=lambda kk: best[N][kk][0])
    pick = [None] * N
    for i in range(N, 0, -1):
        v, p = best[i][k]
        pick[i - 1] = None if isinstance(k, tuple) else k
        k = p
    return pick


def fill_take(take, sents, Tarr, log):
    """選んだ回の後始末（10/16）：①隣の文と重なった字は前の文に残して後ろの文の頭を詰める
    ②どの回にも当たらなかった文は、前後の文のあいだの字だけでもう一度ゆるく探す（食い違い8割まで）。それでも無ければ、あいだの声を丸ごとその文として残す。
    台本にある文の声を「台本に無い」として消さない（話した言葉を落とすのがいちばん質を下げる）"""
    n = len(take)
    take = list(take)
    for i in range(n):
        if take[i] is None:
            continue
        pe = next((take[j][2] for j in range(i - 1, -1, -1) if take[j] is not None), 0)
        sim, a, b = take[i]
        if a < pe:
            take[i] = (sim, min(pe, b - 1), b)
    filled = []
    for i in range(n):
        if take[i] is not None:
            continue
        lo = next((take[j][2] for j in range(i - 1, -1, -1) if take[j] is not None), 0)
        hi = next((take[j][1] for j in range(i + 1, n) if take[j] is not None), len(Tarr))
        if hi - lo < 2:
            continue
        cs = candidates(sents[i]["k"], Tarr[lo:hi], max_d=0.8)
        if cs:
            c = max(cs, key=lambda c: c[0])
            take[i] = (c[0], lo + c[1], lo + c[2]); filled.append((i, "ゆるく探して当てた", round(float(c[0]), 2)))
        else:
            # あいだに他の未対応の文があれば、字数の比で分ける
            run = [j for j in range(i, n) if take[j] is None and (j == i or all(take[t] is None for t in range(i, j)))]
            run = [j for j in run if next((take[t][1] for t in range(j + 1, n) if take[t] is not None), len(Tarr)) == hi]
            tot = sum(max(1, len(sents[j]["k"])) for j in run); pos = lo
            for j in run:
                w = int(round((hi - lo) * max(1, len(sents[j]["k"])) / tot)) if j != run[-1] else hi - pos
                if w >= 1 and take[j] is None:
                    take[j] = (0.0, pos, pos + w); filled.append((j, "前後のあいだを丸ごと残した", 0.0))
                pos += w
    if filled:
        log.append({"what": "当たらなかった文を残した", "n": len(filled), "list": [{"sent": i, "how": h, "sim": v} for i, h, v in filled]})
    return take


def best_end(best, i, pk, cands):
    """状態 pk（文 i-1 の選択）までで最後に選ばれた候補の終わり位置"""
    while isinstance(pk, tuple):
        i -= 1
        pk = pk[1]
        if pk == -1 or i <= 0:
            return -1
        # skip の連鎖は best[i] を遡る
        if isinstance(pk, tuple):
            continue
        return cands[i - 1][pk][2]
    if pk == -1:
        return -1
    return cands[i - 1][pk][2]


# ================================================================ 本体
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("script")
    ap.add_argument("out")
    ap.add_argument("--stretch", default="rubberband", choices=["rubberband", "atempo"])
    ap.add_argument("--no-speed", action="store_true")
    ap.add_argument("--no-gap", action="store_true")
    ap.add_argument("--no-verify", action="store_true")
    A = ap.parse_args()
    out = Path(A.out)
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "cache"
    cache.mkdir(exist_ok=True)
    ref = json.load(open(os.environ.get("NARR_REF") or HERE / "ref_stats.json"))   # NARR_REF で手本を差し替えられる（既定は202本・yt-tts-1018 は期1 13本）
    log = []

    raw = load(A.audio)
    print(f"読み込み {len(raw) / SR:.1f}秒", file=sys.stderr)
    x = preclean(raw, log)
    db = frame_db(x, SR)
    mask, thr = voice_mask(db)

    words = transcribe(x, cache)
    words = fill_missed(x, words, mask, cache, log)
    # 起こした文字を台本の形で残す（渡された台本・演出と比べるため。言い直しや「えー」も含めて声のとおり）
    Path(out / "mojiokoshi.txt").write_text(words_to_text(words))
    W = [{"s": w[0], "e": w[1], "t": w[2], "k": kana(w[2]) if w[2] != "〔声〕" else ""} for w in words]
    # 字の並び（かな）と、字→言葉の対応
    T, c2w = [], []
    for i, w in enumerate(W):
        T += list(w["k"])
        c2w += [i] * len(w["k"])
    Tarr = np.array(T) if T else np.array(["_"])
    c2w = np.array(c2w + [len(W) - 1])
    W_time.c2w = c2w
    w_c0 = {}
    for ci, wi in enumerate(c2w[:-1]):
        w_c0.setdefault(int(wi), ci)

    sents = split_sentences(Path(A.script).read_text())
    for s in sents:
        s["k"] = kana(s["text"])
    assign_sections(sents)
    print(f"台本 {len(sents)}文 ／ 文字起こし {len(W)}語 {len(T)}字", file=sys.stderr)

    cands = [candidates(s["k"], Tarr) for s in sents]
    pick = choose(cands, len(T))
    take = [cands[i][p] if p is not None else None for i, p in enumerate(pick)]
    take = fill_take(take, sents, Tarr, log)

    # ---- 残す言葉・消す言葉
    keep_w = np.zeros(len(W), bool)
    sent_of_w = np.full(len(W), -1)
    reason = {}
    for i, tk in enumerate(take):
        if tk is None:
            continue
        sim, a, b = tk
        ws = sorted({int(c2w[c]) for c in range(a, b)})
        if sim < 0.5:
            # ゆるく当てた・前後のあいだを丸ごと残した文：字の並びが台本と合わないので「台本に無い」で消さない。はっきりしたつなぎ言葉だけ消す
            for j in ws:
                keep_w[j], sent_of_w[j] = True, i
                if W[j]["k"] in FILLER_STRONG or (W[j]["t"] == "〔声〕" and W[j]["e"] - W[j]["s"] < KEEP_VOICE):
                    keep_w[j], reason[j] = False, ("字にならない声" if W[j]["t"] == "〔声〕" else "つなぎ言葉")
            continue
        seg_k = "".join(W[j]["k"] for j in ws)
        ops, _ = align_ops(sents[i]["k"], seg_k)
        pos = 0
        for j in ws:
            L = len(W[j]["k"])
            o = ops[pos:pos + L]
            pos += L
            ins = L == 0 or o.count("I") >= max(1, 0.8 * L)
            keep_w[j], sent_of_w[j] = True, i
            if ins:
                kk = W[j]["k"]
                nxt = W[j + 1]["k"] if j + 1 < len(W) else ""
                if kk in FILLER_STRONG or (kk in FILLERS and kk not in sents[i]["k"]):
                    keep_w[j], reason[j] = False, "つなぎ言葉"
                elif kk and nxt.startswith(kk) and len(kk) <= 3:
                    keep_w[j], reason[j] = False, "噛み"
                elif W[j]["t"] == "〔声〕" and W[j]["e"] - W[j]["s"] < KEEP_VOICE:
                    keep_w[j], reason[j] = False, "字にならない声"
        # 言葉の言い直し（「投稿の、投稿の作り方」）：台本に無い言葉の並びが、すぐ後ろと同じ
        run = [j for j in ws if keep_w[j] and is_inserted(j, ws, ops, W)]
        for j in run:
            kk = W[j]["k"]
            after = "".join(W[t]["k"] for t in ws if t > j)[:len(kk) + 1]
            if len(kk) >= 2 and after.startswith(kk):
                keep_w[j], reason[j] = False, "言い直し（言葉）"
        # 「と」「とー」のように 後ろが前の音を伸ばしただけ（「んっと」の聞き違いなど）なら、伸ばした方を消して前を残す
        for j in ws:
            if reason.get(j) != "噛み" or j + 1 not in ws:
                continue
            tail = [j + 1] + ([j + 2] if j + 2 in ws and W[j + 2]["k"] and set(W[j + 2]["k"]) <= {"ー"} else [])
            ext = "".join(W[t]["k"] for t in tail)
            if "ー" in ext and ext.replace("ー", "") == W[j]["k"]:
                keep_w[j] = True
                reason.pop(j)
                for t in tail:
                    keep_w[t], reason[t] = False, "つなぎ言葉"
        # 台本に無い言葉が続いている所はまとめて見る
        #   ・つなげると つなぎ言葉（「えー」＋「と」＝「えーと」）→ 消す
        #   ・前後に無音がある ひとかたまり（文の途中の独り言・言い間違い）→ 消す
        ins_run, runs_ = [], []
        for j in ws:
            if keep_w[j] and is_inserted(j, ws, ops, W):
                ins_run.append(j)
            else:
                if ins_run:
                    runs_.append(ins_run)
                ins_run = []
        if ins_run:
            runs_.append(ins_run)
        for r_ in runs_:
            kk = "".join(W[t]["k"] for t in r_)
            prev_f = r_[0] - 1 if r_[0] > 0 and reason.get(r_[0] - 1) == "つなぎ言葉" else None
            joined = ((W[prev_f]["k"] if prev_f is not None else "") + kk).replace("ー", "")
            if joined in {f.replace("ー", "") for f in FILLERS} or kk.replace("ー", "") in {f.replace("ー", "") for f in FILLERS}:
                for t in r_:
                    keep_w[t], reason[t] = False, "つなぎ言葉"
                continue
            before = W[r_[0]]["s"] - (W[r_[0] - 1]["e"] if r_[0] > 0 else 0)
            after = (W[r_[-1] + 1]["s"] if r_[-1] + 1 < len(W) else 1e9) - W[r_[-1]]["e"]
            if len(kk) >= 3 and r_[0] != ws[0] and r_[-1] != ws[-1] and before >= 0.15 and after >= 0.15 and kk not in sents[i]["k"]:
                for t in r_:
                    keep_w[t], reason[t] = False, "台本に無い（文の途中の独り言・言い間違い）"
        # 文の外側にはみ出した言葉（候補の端の1語）は文に入れない
    # ---- 言葉の続きの〔声〕：whisper が言葉を拍の数より短く書き、残りが〔声〕になった所（10/16 HBg「ありがとうございました」0.22秒＋〔声〕0.39秒）。
    #      すぐ隣（0.05秒以内）の残す言葉が、拍の数から見た長さの半分より短ければ、その〔声〕は言葉の続き＝残す
    for j in range(len(W)):
        if W[j]["t"] != "〔声〕" or keep_w[j]:
            continue
        for p in (j - 1, j + 1):
            if 0 <= p < len(W) and keep_w[p] and W[p]["k"] and sent_of_w[p] >= 0:
                near = (W[j]["s"] - W[p]["e"]) if p < j else (W[p]["s"] - W[j]["e"])
                if near < 0.05 and (W[p]["e"] - W[p]["s"]) < 0.5 * word_len(W[p]["k"]):
                    keep_w[j], sent_of_w[j] = True, sent_of_w[p]
                    reason.pop(j, None)
                    break
    # ---- 文の外で消した所を分類
    deleted = []
    j = 0
    while j < len(W):
        if keep_w[j]:
            j += 1
            continue
        k = j
        while k + 1 < len(W) and not keep_w[k + 1] and (W[k + 1]["s"] - W[k]["e"] < 0.35) and sent_of_w[k + 1] == sent_of_w[j]:
            k += 1
        deleted.append(classify(j, k, W, sents, cands, take, sent_of_w, reason, Tarr, w_c0))
        j = k + 1

    # ---- 文ごとに 残す声のかたまり（声の区間）を作る
    plan = build_plan(x, db, mask, W, keep_w, sent_of_w, sents, take)
    # ---- 速さと間
    gap_log = set_gaps(plan, sents, ref, off=A.no_gap)        # 間を先に決める（速さの計算に 文の中の短い間の長さを使う）
    speed_log = set_speed(plan, sents, ref, W, off=A.no_speed)
    # ---- 音を組み立てる
    y, timeline = render(x, plan, sents, A.stretch, cache)
    lv = level(y, ref)
    y = lv.pop("y")
    save(out / "henshu.wav", y)
    log.append({"what": "音量", **lv})
    print(f"書き出し {len(y) / SR:.1f}秒（元 {len(raw) / SR:.1f}秒）", file=sys.stderr)

    rep = {"input": str(A.audio), "script": str(A.script), "dur_in": round(len(raw) / SR, 2), "dur_out": round(len(y) / SR, 2),
           "sentences": [{"i": i, "text": s["text"], "sec": s["sec"], "kept": None if take[i] is None else
                          {"s": round(W[c2w[take[i][1]]]["s"], 2), "e": round(W[c2w[max(take[i][2] - 1, 0)]]["e"], 2), "sim": round(take[i][0], 3)},
                          "n_takes": len([c for c in cands[i] if c[0] >= 0.75])} for i, s in enumerate(sents)],
           "deleted": deleted, "speed": speed_log, "gaps": gap_log, "clean": log,
           "missing": [s["text"] for i, s in enumerate(sents) if take[i] is None],
           "kept_ranges": [[round(p["s"], 3), round(p["e"], 3), p["sent"]] for p in plan["chunks"]],
           "words": [[round(w["s"], 2), round(w["e"], 2), w["t"], bool(keep_w[j]), int(sent_of_w[j]) + 1 if sent_of_w[j] >= 0 else None,
                      reason.get(j)] for j, w in enumerate(W)]}
    if not A.no_verify:
        rep["timing"] = verify(out / "henshu.wav", sents, cache, timeline)
        json.dump(rep["timing"], open(out / "jikoku.json", "w"), ensure_ascii=False, indent=1)
        rep["after"] = measure_out(y, rep["timing"], sents, ref)
        Path(out / "mojiokoshi_henshu.txt").write_text(words_to_text(transcribe(y_saved(out), cache, prompt="")))
    json.dump(rep, open(out / "kiroku.json", "w"), ensure_ascii=False, indent=1)
    write_md(rep, out / "kiroku.md")
    print(f"→ {out}/henshu.wav ・ jikoku.json ・ kiroku.md", file=sys.stderr)


def words_to_text(words):
    """言葉の並び → 文の行（句点か 0.6秒以上の間で改行）"""
    out, line, prev = [], "", None
    for s_, e_, t in words:
        if t == "〔声〕":
            continue
        if line and prev is not None and s_ - prev >= 0.6:
            out.append(line)
            line = ""
        line += t
        prev = e_
        if t.endswith(("。", "？", "！", "?", "!")):
            out.append(line)
            line = ""
    if line:
        out.append(line)
    return "\n".join(out) + "\n"


SENT_END = re.compile(r"(です|ます|でした|ました|ません|ですね|ですよ|ますね|ますよ|ください|ので|けど|よね|んです|んですけど|ですけど|んですよ|でしょう|ましょう|思います|います|あります|なります|します|しました)$")
JOSHI = ("ね", "よ", "て", "が", "は", "で", "に", "を", "と", "も")


def split_words(words):
    """言葉の並び → 文ごとの並び。Whisper は句読点をほとんど付けず、日本語の言葉の時刻の切れ目も当てにならない（言葉の途中に間が出る）。
    だから「文の終わりの形」で切る：句点 ／ 0.6秒以上の間 ／ 20字を越えて「です・ます・ので…」で終わる所 ／
    90字を越えたら、その行の後ろ半分で助詞（ね・よ・て・が…）で終わる一番後ろの所。言葉の途中では切らない"""
    groups, cur = [], []
    def text(ws): return "".join(w[2] for w in ws)
    for w in words:
        if w[2] == "〔声〕":
            continue
        if cur:
            g = w[0] - cur[-1][1]; t = text(cur); n = len(t)
            tail_ok = not w[2].startswith(("よ", "ね", "けど", "けれど", "し", "か", "が", "から", "ので", "な", "わ", "って", "とか", "と", "の", "ん"))
            if g >= 0.6 or (n >= 20 and SENT_END.search(t) and tail_ok):   # 「です｜よ」「思うんです｜けど」の途中では切らない
                groups.append(cur); cur = []
            elif n >= 90:
                ks = [q for q in range(len(cur) // 2, len(cur)) if cur[q][2].endswith(JOSHI)]
                k = ks[-1] if ks else len(cur) - 1
                groups.append(cur[:k + 1]); cur = cur[k + 1:]
        cur.append(w)
        if w[2].endswith(("。", "？", "！", "?", "!")):
            groups.append(cur); cur = []
    if cur: groups.append(cur)
    out = []
    for ws in groups:                                # 4字に満たない切れ端は前の文につなぐ
        if out and len(re.sub(r"[、。？！\s]", "", text(ws))) < 4: out[-1] = out[-1] + ws
        else: out.append(ws)
    return out


def words_to_script(words):
    """言葉の並び → 台本の形（1行1文・文末に句点）。依頼主の台本が届くまでの代わりに使う（切り方は split_words）"""
    lines = ["".join(w[2] for w in ws).strip() for ws in split_words(words)]
    return "\n".join(x if x.endswith(("。", "？", "！", "?", "!")) else x + "。" for x in lines if x) + "\n"


def y_saved(out):
    return load(out / "henshu.wav")


def is_inserted(j, ws, ops, W):
    pos = 0
    for t in ws:
        L = len(W[t]["k"])
        if t == j:
            o = ops[pos:pos + L]
            return L > 0 and o.count("I") >= 0.8 * L
        pos += L
    return False


def assign_sections(sents):
    """区間：台本に【冒頭】などがあればそれ。無ければ 告知の言葉→告知、最初の段落→冒頭、最後の段落→締め、ほか本編"""
    if any(s["sec"] for s in sents):
        cur = "冒頭"
        for s in sents:
            cur = s["sec"] or cur
            s["sec"] = cur
        return
    n = len(sents)
    paras = sorted({s["para"] for s in sents})
    first = [s for s in sents if s["para"] == paras[0]]
    last = [s for s in sents if s["para"] == paras[-1]]
    for i, s in enumerate(sents):
        if PROMO.search(s["text"]):
            s["sec"] = "告知"
        elif (len(paras) > 2 and s in first and len(first) <= 0.3 * n) or (len(paras) <= 2 and i < max(2, n // 10)):
            s["sec"] = "冒頭"
        elif (len(paras) > 2 and s in last and len(last) <= 0.2 * n) or (len(paras) <= 2 and i >= n - max(2, n // 20)):
            s["sec"] = "締め"
        else:
            s["sec"] = "本編"


def classify(j, k, W, sents, cands, take, sent_of_w, reason, Tarr, w_c0):
    txt = "".join(W[t]["t"] for t in range(j, k + 1))
    kk = "".join(W[t]["k"] for t in range(j, k + 1))
    item = {"s": round(W[j]["s"], 2), "e": round(W[k]["e"], 2), "text": txt, "keep": None}
    if j in reason and k == j:
        item["reason"] = reason[j]
        i = sent_of_w[j]
        item["keep"] = None if i < 0 else f"文{i + 1}の中"
        return item
    if all(W[t]["k"] in FILLERS or W[t]["t"] == "〔声〕" for t in range(j, k + 1)):
        item["reason"] = "つなぎ言葉" if any(W[t]["k"] for t in range(j, k + 1)) else "字にならない声"
        return item
    c0 = w_c0.get(j, 0)
    c1 = c0 + len(kk)
    # 前の回（使わなかった候補）と重なる
    for i, cs in enumerate(cands):
        for c in cs:
            if take[i] is not None and c != take[i] and c[0] >= 0.7 and min(c[2], c1) - max(c[1], c0) > 0.5 * max(1, c1 - c0):
                item["reason"] = "言い直し（前の回）" if c[1] < take[i][1] else "言い直し（後の回・台本に近い前の回を残した）"
                item["keep"] = f"文{i + 1}（{W_time(W, take[i])}）"
                item["sim_dropped"], item["sim_kept"] = round(c[0], 2), round(take[i][0], 2)
                return item
    # 言いかけ：近くの文の頭と同じ
    near = [i for i in range(len(sents)) if take[i] is not None]
    after = [i for i in near if take[i][1] >= c0]
    before = [i for i in near if take[i][1] < c0]
    look = after[:2] + before[-1:]
    if len(kk) >= 2:
        for i in look:
            S = sents[i]["k"]
            if edit(kk, S[:len(kk)]) <= 0.3 * len(kk):
                item["reason"], item["keep"] = "言いかけ", f"文{i + 1}（{W_time(W, take[i])}）"
                return item
        for i in look:
            S = sents[i]["k"]
            D, _ = fit(np.array(list(kk)), np.array(list(S)))
            if D.min() <= 0.3 * len(kk):
                item["reason"], item["keep"] = "言い直し（途中から）", f"文{i + 1}（{W_time(W, take[i])}）"
                return item
    if len(kk) <= 3 and kk and any(sents[i]["k"].find(kk) >= 0 for i in look):
        item["reason"], item["keep"] = "噛み", f"文{look[0] + 1}" if look else None
        return item
    item["reason"] = "台本に無い（独り言・言い間違い）"
    return item


def W_time(W, tk):
    """候補（字の位置）の始まりの時刻"""
    return f"{W[int(W_time.c2w[tk[1]])]['s']:.1f}秒"


# ================================================================ 声のかたまり・間・速さ
def build_plan(x, db, mask, W, keep_w, sent_of_w, sents, take):
    """残す言葉 → 声のかたまり（VAD の声の区間）。文ごと。かたまりの間が「間」"""
    n = len(mask)
    chunks = []
    for i in range(len(sents)):
        ws = [j for j in range(len(W)) if keep_w[j] and sent_of_w[j] == i and (W[j]["k"] or W[j]["t"] == "〔声〕")]   # 残すと決めた〔声〕も声として入れる（10/16）
        if not ws:
            continue
        # 続いている言葉どうしをひとまとめ（間に消した言葉があれば切る）
        groups, g = [], [ws[0]]
        for a, b in zip(ws, ws[1:]):
            if b == a + 1:
                g.append(b)
            else:
                groups.append(g)
                g = [b]
        groups.append(g)
        for g in groups:
            s0 = cut_point(db, mask, W[g[0]]["s"], "start", W[g[0] - 1]["e"] if g[0] > 0 else 0)
            e0 = cut_point(db, mask, W[g[-1]]["e"], "end", W[g[-1] + 1]["s"] if g[-1] + 1 < len(W) else len(mask) * HOP)
            # 消す言葉と残す言葉の境目：whisper の言葉の時刻は 前後の「えー」を飲み込んで長くなることがある（試しで「でも」0.8秒・「つ」1.7秒）。
            # 残す言葉の拍の数から見た長さ（ただし言葉の長さの4割まで：漢字1字に切られると読みを長く取り違える「概」→おおむね）を超える分を
            # 探す範囲に入れ、その中の無音で切る
            s_cp, e_cp = s0, e0
            j = g[0]
            if j > 0 and not keep_w[j - 1] and W[j]["k"]:
                lo = W[j - 1]["s"]
                hi = max(W[j]["s"] + 0.05, W[j]["e"] - min(word_len(W[j]["k"]), 0.4 * (W[j]["e"] - W[j]["s"])))
                b_ = gap_in(mask, lo, hi, "last", W[j]["e"])
                if b_ is not None:
                    s0 = max(s0, b_)
            j = g[-1]
            if j + 1 < len(W) and not keep_w[j + 1] and W[j]["k"]:
                lo = min(W[j]["e"] - 0.05, W[j]["s"] + min(word_len(W[j]["k"]), 0.4 * (W[j]["e"] - W[j]["s"])))
                hi = W[j + 1]["e"]
                b_ = gap_in(mask, lo, hi, "first", W[j]["s"])
                if b_ is not None:
                    e0 = min(e0, b_)
            if e0 - s0 < 0.5 * min(sum(word_len(W[t]["k"]) for t in g), e_cp - s_cp):
                # 境目の切り詰めで声がほとんど残らない（whisper が言葉を短く書いた：10/16 HBg「ありがとうございました」0.22秒→残り -0.01秒）→ 切り詰めない
                s0, e0 = s_cp, e_cp
            # かたまりの中を 0.06秒以上の無音で分ける
            a, b = int(s0 / HOP), int(e0 / HOP)
            m = mask[a:b]
            vr = [(a + p, a + q) for p, q in runs(m, True)]
            # 0.06 秒未満の穴はつなぐ
            merged = []
            for p, q in vr:
                if merged and (p - merged[-1][1]) * HOP < 0.06:
                    merged[-1] = (merged[-1][0], q)
                else:
                    merged.append((p, q))
            merged = [(p, q) for p, q in merged if (q - p) * HOP >= 0.03] or [(a, b)]
            for k, (p, q) in enumerate(merged):
                chunks.append({"sent": i, "s": max(s0, p * HOP) if k == 0 else p * HOP,
                               "e": min(e0, q * HOP) if k == len(merged) - 1 else q * HOP,
                               "lim_s": s0 if k == 0 else None, "lim_e": e0 if k == len(merged) - 1 else None,
                               "words": [j for j in g if W[j]["s"] < q * HOP + 0.05 and W[j]["e"] > p * HOP - 0.05]})
    chunks.sort(key=lambda c: (c["sent"], c["s"]))
    # かたまりの前後に使える静かな所（元の音で、次の声まで）
    for c in chunks:
        a = int(c["s"] / HOP)
        k = a - 1
        while k > 0 and not mask[k] and (a - k) * HOP < 2.0:
            k -= 1
        c["sil_before"] = (a - k - 1) * HOP
        b = int(c["e"] / HOP)
        k = b
        while k < n and not mask[k] and (k - b) * HOP < 2.0:
            k += 1
        c["sil_after"] = (k - b) * HOP
    # 間（かたまりの後ろ）
    for a, b in zip(chunks, chunks[1:]):
        if a["sent"] == b["sent"]:
            kind = "文中"
            contiguous = b["s"] >= a["e"] and abs(b["s"] - a["e"] - a["sil_after"]) < 0.02
        else:
            sb = sents[b["sent"]]
            kind = "場面" if sb["para"] != sents[a["sent"]]["para"] else ("強調前" if EMPH.search(sb["text"]) else "文間")
            contiguous = b["s"] >= a["e"] and abs(b["s"] - a["e"] - a["sil_after"]) < 0.02
        orig = (b["s"] - a["e"]) if contiguous else (a["sil_after"] + b["sil_before"])
        a["gap"] = {"kind": kind, "orig": round(orig, 3), "contiguous": contiguous, "target": orig}
    chunks[-1]["gap"] = None
    return {"chunks": chunks}


def word_len(k):
    """言葉の拍の数から見た、いちばん速く言ったときの長さ（1秒に14拍）"""
    return max(0.08, mora(k) / 14.0)


def gap_in(mask, lo, hi, which, edge, min_len=0.07):
    """無音（min_len 秒以上。促音の詰まりで切らないよう 0.07秒）を探す。長さは窓で切らずに丸ごと測る
    which=last → lo〜edge の無音のうち 始まりが hi より前のもの の いちばん後ろ の終わり
    which=first → edge〜hi の無音のうち 終わりが lo より後のもの の いちばん前 の始まり"""
    a_, b_ = (lo, edge) if which == "last" else (edge, hi)
    a, b = max(0, int(a_ / HOP)), min(len(mask), int(b_ / HOP) + 1)
    if b - a < 2:
        return None
    rs = [(a + p, a + q) for p, q in runs(mask[a:b], False) if (q - p) * HOP >= min_len]
    if which == "last":
        rs = [r for r in rs if r[0] * HOP <= hi]
        return rs[-1][1] * HOP if rs else None
    rs = [r for r in rs if r[1] * HOP >= lo]
    return rs[0][0] * HOP if rs else None


def cut_point(db, mask, t, side, other):
    """言葉の端の時刻 t を、近くのいちばん静かな所に合わせる（言葉の頭は声の立ち上がりの直前、終わりは声が消えた所）"""
    n = len(mask)
    i = int(round(t / HOP))
    if side == "start":
        lo, hi = max(0, int((max(other, t - 0.2)) / HOP)), min(n - 1, i + 8)
        sil = [k for k in range(lo, hi + 1) if not mask[k]]
        before = [k for k in sil if k <= i + 3]
        if before:
            k = max(before)
            return (k + 1) * HOP
        k = lo + int(np.argmin(db[lo:hi + 1])) if hi > lo else i
        return k * HOP
    lo, hi = max(0, i - 8), min(n - 1, int(min(other, t + 0.3) / HOP))
    sil = [k for k in range(lo, hi + 1) if not mask[k]]
    after = [k for k in sil if k >= i - 3]
    if after:
        return min(after) * HOP
    k = lo + int(np.argmin(db[lo:hi + 1])) if hi > lo else i
    return k * HOP


def ref_q(ref_tbl, key, sec):
    t = ref_tbl.get(key, {})
    return t.get(sec) if t.get(sec, {}).get("n", 0) >= 50 else t.get("全体")


KIJUN_KANTEN = Path.home() / "rin6/state/yt-anime-1014/kata/kanten_kijun.json"
CHAR_DROP = re.compile(r"[\s、。,.!?！？「」『』…・]")   # 観点の門（kanten_sokutei）と同じ数え方の字


def rock_ref():
    """手本の編集者さん本人の講義型の本（観点の門の物差し kanten_kijun.json）から、声の本質ルールの値を取る（10/16 作業AI「答えより下にならない」）
    字/秒（話している間）の中央・最大と、0.3秒以上の間/分の中央。per_full が増えれば門と一緒に動く。読めないときは None（前の決め方に戻る）"""
    try:
        kj = json.load(open(KIJUN_KANTEN))
        d = kj["by_format"]["講義型"]["dist"]
        return {"cps_p50": d["n_cps"]["p50"], "cps_p75": d["n_cps"]["p75"], "cps_max": d["n_cps"]["max"],
                "p03_pm_p50": d["n_pause03_pm"]["p50"], "n": d["n_cps"]["n"]}
    except Exception:
        return None


def set_gaps(plan, sents, ref, off=False):
    """間の長さを見本の分布に合わせる：種類（文中・文間・強調前・場面）×区間ごとに、こちらの間の順位 → 見本の同じ順位の長さ
    そのうえで本質ルール「長い間を残しすぎない」（kanten-zenbu.md 13）に合わせる：0.3秒以上の間は 場面の切れ目・強調の前（結論・言い切りの前）だけに置き、
    本数は手本の編集者さん本人の講義型の中央（0.3秒以上/分）まで。ほかの間は 0.25秒（手本の編集者さんの無音の90%点）で止める（10/16 作業AI HBg 声 11.8対22.1）"""
    gaps = [c["gap"] for c in plan["chunks"] if c["gap"]]
    secs = [sents[c["sent"]]["sec"] for c in plan["chunks"] if c["gap"]]
    out = []
    groups = {}
    for g, sec in zip(gaps, secs):
        groups.setdefault(g["kind"], []).append((g, sec))
    for kind, lst in groups.items():
        vals = np.array([g["orig"] for g, _ in lst])
        order = vals.argsort().argsort()
        for (g, sec), r in zip(lst, order):
            q = ref_q(ref["pause_grid"], kind, sec) or ref_q(ref["pause_grid"], "全体", sec)
            pct = (r + 0.5) / len(lst) * 100
            tgt = float(np.interp(min(pct, 98.0), np.arange(101), q["grid"]))   # 上の2%は見本でも外れ値（数秒の溜め）なので使わない
            # 短い間（息継ぎより短い）はそのまま：見本も 0.06 秒未満は数えていない
            if g["orig"] < 0.06:
                tgt = g["orig"]
            g["target"] = g["orig"] if off else round(tgt, 3)
            g["sec"] = sec
    rr = rock_ref()
    long_kept = long_cut = 0
    if not off and rr:
        CAP, LONG = 0.25, 0.30
        mins = sum(c["e"] - c["s"] for c in plan["chunks"]) / 60 + sum(g["target"] for g in gaps) / 60
        allow = max(1, int(round(rr["p03_pm_p50"] * mins)))
        longs = [g for g in gaps if g["target"] >= LONG]
        # 残すのは 場面の切れ目・強調の前 の長い順に allow 本まで。文の中・ふつうの文の間の長い間は 0.25秒にする
        # 台本に段落（場面）や強調の言葉が無いときは、文の間の長い間から長い順に残す（0本にして息継ぎの無い声にしない）
        pri = [g for g in longs if g["kind"] in ("場面", "強調前")] or [g for g in longs if g["kind"] == "文間"]
        ok = sorted(pri, key=lambda g: -g["target"])[:allow]
        keep = {id(g) for g in ok}
        for g in longs:
            if id(g) not in keep:
                g["target"] = CAP
                long_cut += 1
        long_kept = len(keep)
    for g, sec in zip(gaps, secs):
        out.append({"kind": g["kind"], "sec": sec, "orig": g["orig"], "target": g["target"]})
    s = {}
    for o in out:
        d = s.setdefault(o["kind"], {"n": 0, "orig": [], "target": []})
        d["n"] += 1
        d["orig"].append(o["orig"])
        d["target"].append(o["target"])
    res = {k: {"n": v["n"], "orig_median": round(float(np.median(v["orig"])), 3), "target_median": round(float(np.median(v["target"])), 3),
               "orig_total": round(sum(v["orig"]), 2), "target_total": round(sum(v["target"]), 2)} for k, v in s.items()}
    res["長い間"] = {"残した": long_kept, "0.25秒にした": long_cut, "手本の編集者さんの中央（/分）": rr["p03_pm_p50"] if rr else None}
    return res


def set_speed(plan, sents, ref, W_, off=False):
    """話す速さ：区間（冒頭・本編・告知・締め）ごとに倍率を決める（10/16 作業AIの指示「set_speed を区間ごと」）。
    目標は手本の編集者さん本人の講義型の「話している間の字/秒」の中央（観点の門 13 の本質ルール・kanten_kijun.json）に、見本202本の区間ごとの速さの比
    （冒頭はやや遅く・告知と締めはやや速い）を掛けたもの。字は門と同じ数え方（台本の文の字から記号を除く）、秒は声のかたまり＋文の中の短い間（0.15秒未満）。
    遅い区間だけ上げる（目標以上の区間は触らない・手本の編集者さんの最大より速い区間だけ下げる）。区間どうしの倍率は全体の倍率から ±0.08 までにそろえ、
    聞いて段差が出ないようにする（編集者は全体で1つの倍率が基本＝依頼主 10/15）。0.01刻み・0.9〜1.45倍。
    手本の編集者さんの値が読めないときは前の決め方（全体1つ・見本202本の拍/秒の25〜75%）"""
    rr = rock_ref()
    by_sec = {}
    M = C = G = 0.0
    for i, s in enumerate(sents):
        cs = [c for c in plan["chunks"] if c["sent"] == i]
        if not cs:
            continue
        ch = len(CHAR_DROP.sub("", s["text"]))
        c_ = sum(c["e"] - c["s"] for c in cs)
        # 速さを f 倍にすると 声の長さ C は C/f。文の中の短い間（0.15秒未満）は 組み立てで目標どおりの長さ G になる
        g_ = sum(c["gap"]["target"] for c in cs[:-1] if c["gap"] and c["gap"]["target"] < 0.15)
        d = by_sec.setdefault(s["sec"] or "本編", {"ch": 0.0, "C": 0.0, "G": 0.0, "M": 0.0, "idx": []})
        d["ch"] += ch; d["C"] += c_; d["G"] += g_; d["M"] += mora(s["k"]); d["idx"].append(i)
        M += mora(s["k"]); C += c_; G += g_
    if not rr:
        rs = ref["speed"]["全体"]["mora_s"]
        lo, mid, hi = rs["p25"], rs["p50"], rs["p75"]
        r1 = M / (C + G) if C + G > 0 else 0.0
        f = 1.0
        if not off and r1 and not (lo <= r1 <= hi):
            den = M / mid - G
            f = C / den if den > 0.1 else 1.6
            f = round(float(np.clip(round(f / 0.05) * 0.05, 0.75, 1.6)), 2)
        for s in sents:
            s["speed"] = f
        return {"rate_before": round(r1, 2), "rate_after": round(M / (C / f + G), 2) if C else 0.0, "factor": f,
                "ref_p25": lo, "ref_median": mid, "ref_p75": hi}

    def fac(ch, c_, g_, tgt, top):
        r = ch / (c_ + g_) if c_ + g_ > 0 else 0.0
        if off or not r or (r >= tgt and r <= top):
            return 1.0, r
        want = tgt if r < tgt else top
        den = ch / want - g_
        return (c_ / den if den > 0.1 else 1.45), r
    base = ref["speed"]["全体"]["char_s"]["p50"]
    ch_all = sum(d["ch"] for d in by_sec.values())
    f_all, r_all = fac(ch_all, C, G, rr["cps_p50"], rr["cps_max"])
    f_all = float(np.clip(f_all, 0.9, 1.45))
    secs = {}
    for sec, d in by_sec.items():
        ratio = ref["speed"].get(sec, ref["speed"]["全体"])["char_s"]["p50"] / base
        f, r = fac(d["ch"], d["C"], d["G"], rr["cps_p50"] * ratio, rr["cps_max"] * ratio)
        f = round(float(np.clip(np.clip(f, f_all - 0.08, f_all + 0.08), 0.9, 1.45)), 2)
        if off:
            f = 1.0
        for i in d["idx"]:
            sents[i]["speed"] = f
        secs[sec] = {"chars_s_before": round(r, 2), "target": round(rr["cps_p50"] * ratio, 2), "factor": f,
                     "chars_s_after": round(d["ch"] / (d["C"] / f + d["G"]), 2) if d["C"] else 0.0, "n_sent": len(d["idx"])}
    for s in sents:
        s.setdefault("speed", 1.0)
    C2 = sum(sum(c["e"] - c["s"] for c in plan["chunks"] if c["sent"] == i) / sents[i]["speed"] for i in range(len(sents)))
    return {"rate_before": round(r_all, 2), "rate_after": round(ch_all / (C2 + G), 2) if C2 else 0.0, "factor": round(f_all, 2),
            "unit": "字/秒（話している間・観点の門と同じ数え方）", "rock_cps_p50": rr["cps_p50"], "rock_cps_max": rr["cps_max"], "rock_n": rr["n"], "kukan": secs}


# ================================================================ 組み立て
def render(x, plan, sents, method, cache):
    cs = plan["chunks"]
    # 文ごとに：かたまり＋文中の間 → 速さを変える → 文と文の間でつなぐ
    by = {}
    for c in cs:
        by.setdefault(c["sent"], []).append(c)
    pieces = {}

    def seg(a, b):
        a, b = max(0, int(a * SR)), min(len(x), int(b * SR))
        return x[a:b].copy()

    def sent_audio(i):
        lst = by[i]
        f = sents[i].get("speed", 1.0)
        parts = []
        for k, c in enumerate(lst):
            lead = min(LEAD, c["sil_before"]) if k == 0 else 0
            tail = min(TAIL, c["sil_after"]) if k == len(lst) - 1 else 0
            a, b = c["s"] - lead, c["e"] + tail
            if k > 0:
                g = lst[k - 1]["gap"]
                P = g["target"] * f        # 速さを変えると間も伸び縮みするので、先に割り戻しておく
                parts[-1], a = join_gap(parts[-1], lst[k - 1], c, P, x)
            parts.append(seg(a, b))
        y = parts[0]
        for p in parts[1:]:
            y = xfade(y, p)
        y = stretch(y, f, method, cache, i) if f != 1.0 else y
        return y

    with ThreadPoolExecutor(2) as ex:   # 重い処理は同時2本まで（GENDO.md）
        res = list(ex.map(sent_audio, sorted(by)))
    order = sorted(by)
    out = Tsugi(np.zeros(int(0.3 * SR), np.float32))   # 文を足すたびに全体を作り直さない（長い声で全体の写しが何百回も出来ていた）
    timeline = []
    for n, (i, y) in enumerate(zip(order, res)):
        lst = by[i]
        y = gain_sentence(y)
        if n > 0:
            prev_last = by[order[n - 1]][-1]
            g = prev_last["gap"]
            P = g["target"]
            # 前の文の語尾の余白（TAIL）と この文の頭の余白（LEAD）は間に含める
            pad = min(TAIL, prev_last["sil_after"]) + min(LEAD, lst[0]["sil_before"])
            sil = max(0.0, P - pad)
            out.add(np.zeros(int(sil * SR) + int(2 * XF * SR), np.float32))
        timeline.append({"sent": i, "s": out.n / SR})
        out.add(y)
        timeline[-1]["e"] = out.n / SR
    out = np.concatenate([out.get(), np.zeros(int(0.4 * SR), np.float32)])
    return out, timeline


def join_gap(prev_audio, a, b, P, x):
    """文の中の間：元の静かな所を使って P 秒にする（足りなければ無音を足す）。返り値：前の音（後ろに静かな所を足したもの）・次の始まり時刻"""
    if a["gap"]["contiguous"]:
        G = b["s"] - a["e"]
        if P <= G:
            # 静かな所の真ん中を抜く
            h = P / 2
            prev_audio = xfade(prev_audio, x[int(a["e"] * SR):int((a["e"] + h) * SR)])
            return prev_audio, b["s"] - h
        prev_audio = xfade(prev_audio, x[int(a["e"] * SR):int((a["e"] + G / 2) * SR)])
        prev_audio = xfade(prev_audio, np.zeros(int((P - G) * SR) + int(2 * XF * SR), np.float32))
        return prev_audio, b["s"] - G / 2
    h1, h2 = min(a["sil_after"], P / 2), min(b["sil_before"], P / 2)
    prev_audio = xfade(prev_audio, x[int(a["e"] * SR):int((a["e"] + h1) * SR)])
    rest = P - h1 - h2
    if rest > 0:
        prev_audio = xfade(prev_audio, np.zeros(int(rest * SR) + int(2 * XF * SR), np.float32))
    return prev_audio, b["s"] - h2


class Tsugi:
    """つないだ音を部品のまま持ち、最後に1回だけ並べる。xfade を続けて呼んだのと同じ音になる"""
    def __init__(self, a):
        self.parts, self.n = [a.astype(np.float32)], len(a)

    def add(self, b, d=XF):
        n = int(d * SR)
        if self.n < n or len(b) < n:
            self.parts.append(b.astype(np.float32))
            self.n += len(b)
            return
        while len(self.parts[-1]) < n:      # 最後の部品が重ねる長さより短いときは前とまとめる
            last = self.parts.pop()
            self.parts[-1] = np.concatenate([self.parts[-1], last])
        a = self.parts[-1]
        t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
        mid = a[-n:] * np.cos(t) + b[:n] * np.sin(t)
        self.parts[-1] = a[:-n]
        self.parts += [mid.astype(np.float32), b[n:].astype(np.float32)]
        self.n += len(b) - n

    def get(self):
        return np.concatenate(self.parts).astype(np.float32)


def xfade(a, b, d=XF):
    """つなぎ目でブツッと鳴らないよう、数ミリ秒重ねる（等パワー）"""
    n = int(d * SR)
    if len(a) < n or len(b) < n:
        return np.concatenate([a, b]).astype(np.float32)
    t = np.linspace(0, np.pi / 2, n, dtype=np.float32)
    mid = a[-n:] * np.cos(t) + b[:n] * np.sin(t)
    return np.concatenate([a[:-n], mid, b[n:]]).astype(np.float32)


def stretch(y, f, method, cache, i):
    """ピッチを変えずに速さだけ f 倍"""
    d = tempfile.mkdtemp(dir=cache)
    save(f"{d}/i.wav", y)
    if method == "rubberband":
        subprocess.run(["rubberband", "-q", "-3", "--formant", "-T", f"{f:.4f}", f"{d}/i.wav", f"{d}/o.wav"], check=True,
                       capture_output=True)
    else:
        subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-y", "-i", f"{d}/i.wav", "-af", f"atempo={f:.4f}", f"{d}/o.wav"], check=True)
    z = load(f"{d}/o.wav")
    for p in Path(d).iterdir():
        p.unlink()
    os.rmdir(d)
    return z


def gain_sentence(y):
    """文ごとの声の大きさ（声のある所の中央）を -20dBFS 付近にそろえる（±10dB まで）"""
    db = frame_db(y, SR)
    m, _ = voice_mask(db)
    if m.sum() < 10:
        return y
    lvl = np.median(db[m])
    g = np.clip(-20 - lvl, -10, 10)
    return (y * 10 ** (g / 20)).astype(np.float32)


def level(y, ref):
    """見本の声の大きさ（LUFS）に合わせる（2回測る loudnorm・ピークは -1.5dBTP まで）"""
    tgt = ref["loud"]["voice_lufs"]["p50"]
    d = tempfile.mkdtemp()
    save(f"{d}/a.wav", y)
    r = subprocess.run(["ffmpeg", "-threads", "4", "-hide_banner", "-i", f"{d}/a.wav", "-af", f"loudnorm=I={tgt}:TP=-1.5:LRA=7:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(r.stderr[r.stderr.rfind("{"):r.stderr.rfind("}") + 1])
    af = (f"loudnorm=I={tgt}:TP=-1.5:LRA=7:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-threads", "4", "-v", "error", "-y", "-i", f"{d}/a.wav", "-af", af, "-ar", str(SR), f"{d}/b.wav"], check=True)
    z = load(f"{d}/b.wav")
    r2 = subprocess.run(["ffmpeg", "-threads", "4", "-hide_banner", "-i", f"{d}/b.wav", "-af", "ebur128=peak=true:framelog=quiet", "-f", "null", "-"],
                        capture_output=True, text=True)
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", r2.stderr)
    return {"y": z, "target_lufs": tgt, "before_lufs": float(js["input_i"]), "after_lufs": float(m[-1]) if m else None}


# ================================================================ 確かめ・時刻
def verify(path, sents, cache, timeline=None):
    """編集済みの声をもう一度文字起こし → 台本の文ごとの 始まり・終わり・言葉の時刻。台本の文が何回出てくるかも数える
    whisper は長い音で文をまるごと飛ばすことがあるので、見つからない文は 組み立ての記録（timeline）の範囲だけ切り出して読み直す"""
    x = load(path)
    words = transcribe(x, cache, prompt="")   # 確かめでは呼び水を使わない（「えっと」の呼び水で、無い「えっと」を書くことがある）
    if timeline:
        words = reread_missing(x, words, sents, timeline)
    W = [{"s": w[0], "e": w[1], "t": w[2], "k": kana(w[2])} for w in words]
    T, c2w = [], []
    for i, w in enumerate(W):
        T += list(w["k"])
        c2w += [i] * len(w["k"])
    Tarr = np.array(T) if T else np.array(["_"])
    out, used = [], np.zeros(len(T), bool)
    pos = 0
    for i, s in enumerate(sents):
        cs = candidates(s["k"], Tarr, max_d=0.45)
        n_hits = len([c for c in cs if c[0] >= 0.75])
        nxt = [c for c in cs if c[1] >= pos - 3]
        tl = next((t for t in (timeline or []) if t["sent"] == i), None)
        if not nxt and tl:
            # 台本と言い方が違う回しか無かった文（意味は同じ）：組み立ての記録の範囲を使い、台本との近さを書いておく
            ks = [k for k in range(len(W)) if W[k]["s"] >= tl["s"] - 0.05 and W[k]["e"] <= tl["e"] + 0.05]
            kk = "".join(W[k]["k"] for k in ks)
            cis = [ci for ci, w in enumerate(c2w) if w in set(ks)]
            used[cis] = True
            if cis:
                pos = max(cis) + 1
            out.append({"i": i + 1, "text": s["text"], "sec": s["sec"], "found": True, "by": "組み立ての記録（台本と言い方が違う）",
                        "sim": round(1 - edit(kk, s["k"]) / max(len(s["k"]), 1), 3), "hits": 1, "said": "".join(W[k]["t"] for k in ks),
                        "s": round(tl["s"], 3), "e": round(tl["e"], 3), "s_edit": round(tl["s"], 3), "e_edit": round(tl["e"], 3),
                        "words": [{"t": W[k]["t"], "s": round(W[k]["s"], 3), "e": round(W[k]["e"], 3)} for k in ks]})
            continue
        if not nxt:
            out.append({"i": i + 1, "text": s["text"], "sec": s["sec"], "found": False, "hits": n_hits})
            continue
        c = max(nxt[:3], key=lambda c: c[0])
        used[c[1]:c[2]] = True
        pos = c[2]
        ws = sorted({c2w[k] for k in range(c[1], c[2])})
        out.append({"i": i + 1, "text": s["text"], "sec": s["sec"], "found": True, "sim": round(c[0], 3), "hits": n_hits,
                    "s": round(W[ws[0]]["s"], 3), "e": round(W[ws[-1]]["e"], 3),
                    "s_edit": round(tl["s"], 3) if tl else None, "e_edit": round(tl["e"], 3) if tl else None,
                    "words": [{"t": W[k]["t"], "s": round(W[k]["s"], 3), "e": round(W[k]["e"], 3)} for k in ws]})
    extra = []
    for k in range(len(W)):
        cs = [ci for ci, w in enumerate(c2w) if w == k]
        if cs and not used[cs].any():
            extra.append({"t": W[k]["t"], "s": round(W[k]["s"], 2)})
    return {"sentences": out, "not_in_script": extra, "dur": round(len(x) / SR, 2)}


def reread_missing(x, words, sents, timeline):
    import mlx_whisper
    mlx_tight()   # GPU の溜めを 2GB まで（無いと起こすたびに太る）
    T = "".join(kana(w[2]) for w in words)
    add = []
    for tl in timeline:
        k = sents[tl["sent"]]["k"]
        D, _ = fit(np.array(list(k)), np.array(list(T)) if T else np.array(["_"]))
        if D.min() <= 0.25 * len(k):
            continue
        a, b = max(0, tl["s"] - 0.15), min(len(x) / SR, tl["e"] + 0.15)
        r = mlx_whisper.transcribe(resample16(x[int(a * SR):int(b * SR)]), path_or_hf_repo=WHISPER, language="ja",
                                   word_timestamps=True, condition_on_previous_text=False, temperature=0.0)
        got = [[a + w["start"], a + w["end"], w["word"].strip()] for sg in r["segments"] for w in sg.get("words", []) if w["word"].strip()]
        # その範囲にあった言葉は 読み直した分で置き換える
        words = [w for w in words if not (w[0] >= tl["s"] - 0.05 and w[1] <= tl["e"] + 0.05)]
        add += got
    return sorted(words + add, key=lambda w: w[0])


def measure_out(y, timing, sents, ref):
    """編集後の声を、見本202本と同じ測り方で測る（文の速さ＝拍／(文の長さ−0.15秒以上の無音)・無音の長さの分布）"""
    from common import silences
    sil, _, _, _ = silences(y, SR, min_len=0.06)
    ts = [t for t in timing["sentences"] if t["found"]]
    rates = {}
    from common import frame_db as _fdb, voice_mask as _vm
    m, _ = _vm(_fdb(y, SR))
    for t in ts:
        a, b = t.get("s_edit") or t["s"], t.get("e_edit") or t["e"]
        on = np.flatnonzero(m[int(a / HOP):int(b / HOP)])
        if len(on) < 30:
            continue
        a, b = a + on[0] * HOP, a + (on[-1] + 1) * HOP          # 見本と同じく 声の最初から最後まで
        inner = sum(min(e, b) - max(st, a) for st, e in sil if e - st >= 0.15 and st > a and e < b)
        art = b - a - max(inner, 0)
        k = sents[t["i"] - 1]["k"]
        if art >= 1.0 and mora(k) >= 8:
            rates.setdefault(t["sec"], []).append(mora(k) / art)
    bounds = [(p["e"], n["s"], n) for p, n in zip(ts, ts[1:])]
    kinds = {}
    for st, e in sil:
        kind = "文中"
        for be, bs, n in bounds:
            if st - 0.25 <= be <= e + 0.25 or st - 0.25 <= bs <= e + 0.25:
                pn = sents[n["i"] - 2] if n["i"] >= 2 else None
                kind = "場面" if pn and pn["para"] != sents[n["i"] - 1]["para"] else ("強調前" if EMPH.search(n["text"]) else "文間")
                break
        kinds.setdefault(kind, []).append(e - st)
    q = lambda v: {"n": len(v), "p25": round(float(np.percentile(v, 25)), 3), "p50": round(float(np.percentile(v, 50)), 3),
                   "p90": round(float(np.percentile(v, 90)), 3)} if v else {"n": 0}
    out = {"speed": {}, "pause": {}}
    for sec, v in rates.items():
        r = ref["speed"].get(sec) or ref["speed"]["全体"]
        out["speed"][sec] = {"n": len(v), "median": round(float(np.median(v)), 2), "ref_p25": r["mora_s"]["p25"],
                             "ref_median": r["mora_s"]["p50"], "ref_p75": r["mora_s"]["p75"]}
    for kind, v in kinds.items():
        r = ref["pause"].get(kind, {}).get("全体", {})
        out["pause"][kind] = {**q(v), "ref_p25": r.get("p25"), "ref_p50": r.get("p50"), "ref_p90": r.get("p90")}
    allp = [x for v in kinds.values() for x in v]
    r = ref["pause"]["全体"]["全体"]
    out["pause"]["全体"] = {**q(allp), "ref_p25": r["p25"], "ref_p50": r["p50"], "ref_p90": r["p90"]}
    return out


def write_md(rep, path):
    L = [f"# ナレーションの編集の記録", "",
         f"- 元 {rep['dur_in']}秒 → 編集後 {rep['dur_out']}秒",
         f"- 台本 {len(rep['sentences'])}文 ／ 見つからなかった文 {len(rep['missing'])}", ""]
    if rep["missing"]:
        L += ["## 見つからなかった台本の文（声に無い・読み飛ばし）", ""] + [f"- {t}" for t in rep["missing"]] + [""]
    L += ["## 消した所", "", "| 元の秒 | 消した理由 | 消した声 | 残した版 |", "|---|---|---|---|"]
    for d in rep["deleted"]:
        L.append(f"| {d['s']:.2f}〜{d['e']:.2f} | {d['reason']} | {d['text']} | {d.get('keep') or ''} |")
    sp = rep["speed"]
    if "kukan" in sp:
        L += ["", "## 速さ（区間ごと・字／秒＝話している間・観点の門と同じ数え方）", "",
              f"- 全体：元 {sp['rate_before']} → 編集後の見込み {sp['rate_after']}（全体の倍率 {sp['factor']} 倍）",
              f"- 手本の編集者さん本人の講義型（{sp['rock_n']}本）：中央 {sp['rock_cps_p50']} ／ 最大 {sp['rock_cps_max']}（遅い区間だけ中央まで上げる）", "",
              "| 区間 | 文 | 元 | 目標 | 倍率 | 見込み |", "|---|---|---|---|---|---|"]
        for k, v in sp["kukan"].items():
            L.append(f"| {k} | {v['n_sent']} | {v['chars_s_before']} | {v['target']} | {v['factor']} | {v['chars_s_after']} |")
    else:
        L += ["", "## 速さ（ナレーション全体で倍率1つ・拍／秒）", "",
              f"- 元 {sp['rate_before']} → 編集後の見込み {sp['rate_after']}（全体の倍率 {sp['factor']} 倍）",
              f"- 見本202本：25%点 {sp['ref_p25']} ／ 中央 {sp['ref_median']} ／ 75%点 {sp['ref_p75']}（この範囲に入っていれば倍率は1.0のまま）"]
    L += ["", "## 間（無音）", "", "| 種類 | 数 | 元の中央 | 編集後の中央 | 元の合計 | 編集後の合計 |", "|---|---|---|---|---|---|"]
    for k, v in rep["gaps"].items():
        if k == "長い間":
            L.append(f"| 0.3秒以上 | 残した {v['残した']} | 0.25秒にした {v['0.25秒にした']} | 手本の編集者さんの中央 {v['手本の編集者さんの中央（/分）']}/分 | | |")
            continue
        L.append(f"| {k} | {v['n']} | {v['orig_median']} | {v['target_median']} | {v['orig_total']} | {v['target_total']} |")
    L += ["", "## 音の整え", ""]
    for c in rep["clean"]:
        L.append(f"- {c['what']}: " + ", ".join(f"{k}={v}" for k, v in c.items() if k not in ("what", "times", "found")))
    if "timing" in rep:
        t = rep["timing"]
        bad = [s for s in t["sentences"] if not s["found"] or s["hits"] != 1]
        alt = [s for s in t["sentences"] if s.get("by")]
        L += ["", "## 編集後の確かめ（もう一度文字起こし）", "",
              f"- 台本の文が ちょうど1回ある: {len(t['sentences']) - len(bad)} ／ {len(t['sentences'])}",
              f"- 台本に無い言葉（編集後に残った）: {' '.join(e['t'] for e in t['not_in_script']) or 'なし'}"]
        for s in bad:
            L.append(f"  - 文{s['i']}: 見つかった={s['found']} 回数={s['hits']} {s['text']}")
        sh = short_sentences(t)
        L.append(f"- 落とした文（見つからない・残った声が字数に比べて短すぎる）: {len(sh)}")
        for s in sh:
            L.append(f"  - 文{s['i']}: 残った声 {s['dur']}秒（字数からの見込み {s['expect']}秒）{s['text']}")
        for s in alt:
            L.append(f"  - 文{s['i']}: 台本と言い方が違う回を残した（台本との近さ {s['sim']}）「{s['said']}」← 台本「{s['text']}」")
    if "after" in rep:
        L += ["", "## 編集後を見本と同じ測り方で測った", "", "| 区間 | 文の数 | 速さの中央（拍／秒） | 見本の25%点 | 見本の中央 | 見本の75%点 |", "|---|---|---|---|---|---|"]
        for k, v in rep["after"]["speed"].items():
            L.append(f"| {k} | {v['n']} | {v['median']} | {v['ref_p25']} | {v['ref_median']} | {v['ref_p75']} |")
        L += ["", "| 無音の種類 | 数 | 25%点 | 中央 | 90%点 | 見本の25%点 | 見本の中央 | 見本の90%点 |", "|---|---|---|---|---|---|---|---|"]
        for k, v in rep["after"]["pause"].items():
            if v["n"]:
                L.append(f"| {k} | {v['n']} | {v['p25']} | {v['p50']} | {v['p90']} | {v['ref_p25']} | {v['ref_p50']} | {v['ref_p90']} |")
    Path(path).write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
