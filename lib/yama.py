# 動き続け（61コマ超の動きの続き）を、変化の山で切り直す（作業AI・2026-10-16 作業AIの指示「門の動き続けを変化の山で切る」）
#   前処理（tools0b/ana.py）は、動きが61コマ以上続く所（背景動画・実写・ゆっくり寄る場面）を1つの変化として数え、
#   その中の字は1秒おきに読んだコマを出た時刻にしていた。手本の編集者さんの講義型の本は時間の約3割がこの「動き続け」で、
#   中で出た字・入れ替わった絵が変化に数えられず、テロップの出の時刻も最大1秒ずれていた（1ZdyxoKxiGg：字1542個のうち1052個が動き続けの中）。
#   ここでは ana.py の出力（blk.npz・ev.json・words_v3.json）はそのまま読み、動き続けの中の「変化の山」で区切り直した数字だけを作る。
#   ana.py は前処理の道具（夜の一括処理が使っている）なので触らない。手本の編集者さんの本も作業AIの1本も、門は同じこの関数を通す
#   山＝その前後15コマの変化の大きさ（区画の差の平均）の中央値より k 倍以上大きい極大（かつ absm 以上）、または変化した区画が前のコマより jump 割以上増えたコマ。
#   山どうしは gap コマ以上あける（1つの出方を何度も数えない）
import os, json
import numpy as np

P = {'R': 15, 'k': 2.0, 'absm': 6.0, 'jump': 0.12, 'gap': 8, 'back': 30}
VER = 1


def _peaks(nb, mean, a, b, NB):
    out = []; last = -999
    for f in range(a + 1, b + 1):
        lo, hi = max(a, f - P['R']), min(b, f + P['R'])
        w = np.r_[mean[lo:f], mean[f + 1:hi + 1]]
        base = float(np.median(w)) if len(w) else 0.0
        m = mean[f]
        loc = m >= mean[max(a, f - 2):f + 3].max() - 1e-9
        if ((loc and m >= max(P['absm'], P['k'] * base)) or (nb[f] - nb[f - 1]) >= P['jump'] * NB) and f - last >= P['gap']:
            out.append(f); last = f
    return out


def _norm(s):
    import unicodedata, re
    s = unicodedata.normalize('NFKC', s)
    return re.sub(r'[\s、。,.!?！？「」『』()（）・…ー\-〜~:：;；"\'”“’‘]', '', s)


def _dist(x, bins=None):
    x = np.asarray(x, float)
    if len(x) == 0: return {'n': 0}
    d = {'n': int(len(x)), 'mean': round(float(x.mean()), 2), 'median': round(float(np.median(x)), 2),
         'p10': round(float(np.percentile(x, 10)), 2), 'p90': round(float(np.percentile(x, 90)), 2), 'min': round(float(x.min()), 2), 'max': round(float(x.max()), 2)}
    if bins:
        h = {}
        for v in x:
            k = str(max(-30, min(30, int(round(v))))); h[k] = h.get(k, 0) + 1
        d['hist'] = dict(sorted(h.items(), key=lambda kv: float(kv[0])))
    return d


def resegment(od, force=False):
    """raw/<id>/ の前処理の出力 → 動き続けを山で切った数字（full と first30 の差し替え分）。od/yama.json に控える"""
    cp = os.path.join(od, 'yama.json')
    src = [os.path.join(od, f) for f in ('blk.npz', 'ev.json')]
    if not all(os.path.exists(p) for p in src): return None
    if not force and os.path.exists(cp) and os.path.getmtime(cp) >= max(os.path.getmtime(p) for p in src):
        c = json.load(open(cp))
        if c.get('ver') == VER and c.get('param') == P: return c
    z = np.load(src[0]); nb = z['nb'].astype(float); mean = z['mean'].astype(float); NB = int(z['nblocks']); fps = float(z['fps']); T = len(nb)
    E = json.load(open(src[1])); ev = E['events']; tl = E.get('telop') or []; sfx = E.get('sfx') or []
    cont = [e for e in ev if e['kind'] == 'continuous']
    pk = sorted(f for e in cont for f in _peaks(nb, mean, e['f0'], e['f1'], NB))
    starts = np.array(sorted(set([e['f0'] for e in ev] + pk)))
    wp = os.path.join(od, 'words_v3.json')
    if not os.path.exists(wp): wp = os.path.join(od, 'words.json')
    W_ = []
    if os.path.exists(wp):
        wd = json.load(open(wp)); segs = wd['segments'] if isinstance(wd, dict) else wd
        W_ = [(w[0], w[1], w[2]) for s in segs for w in s['words']]
    pka = np.array(pk) if pk else np.array([], int)
    def in_cont(f): return any(e['f0'] < f <= e['f1'] for e in cont)
    def snap(f):
        # 動き続けの中で1秒おきに読んだコマ → その前 back コマの中でいちばん近い山（無ければそのまま）
        if not in_cont(f) or not len(pka): return f
        c = pka[(pka <= f) & (pka > f - P['back'])]
        return int(c.max()) if len(c) else f
    def word_match(text, f, edge):
        nt = _norm(text); t = f / fps
        cand = [(abs(w[0] - t), w) for w in W_ if abs(w[0] - t) < 4 and len(_norm(w[2])) >= 1 and _norm(w[2]) in nt]
        if not cand: return None
        if edge == 'in': w = min(cand)[1]; return f - w[0] * fps
        w = max((x for x in cand if x[1][0] <= t + 0.5), key=lambda x: x[1][0], default=None)
        return (f - w[1][1] * fps) if w else None
    tels = []
    for o in tl:
        fi, fo = snap(int(o['in_f'])), snap(int(o['out_f']))
        tels.append({'in_f': fi, 'moved_in': fi != int(o['in_f']), 'di': word_match(o['text'], fi, 'in'), 'do': word_match(o['text'], fo, 'out')})
    def block(a, b):
        fa, fb = int(round(a * fps)), min(T, int(round(b * fps))); sec = max(b - a, 1e-3)
        st = starts[(starts >= fa) & (starts < fb)]
        iv = np.diff(st) / fps if len(st) > 1 else []
        tb = [x for x in tels if fa <= x['in_f'] < fb]
        sb = [q for q in sfx if a <= q['t'] < b]
        smc = []
        for q in sb:
            f = q['t'] * fps; k = int(np.argmin(np.abs(starts - f))) if len(starts) else None
            if k is not None: smc.append(round(float(f - starts[k]), 1))
        return {'changes': int(len(st)), 'changes_per_min': round(len(st) / sec * 60, 1), 'change_interval_s': _dist(iv),
                'telop_in_minus_word_f': _dist([x['di'] for x in tb if x['di'] is not None], True),
                'telop_out_minus_wordend_f': _dist([x['do'] for x in tb if x['do'] is not None], True),
                'sfx_minus_change_f': _dist(smc, True), 'yama': int(sum(1 for f in pk if fa <= f < fb)),
                'telop_moved': int(sum(1 for x in tb if x['moved_in']))}
    D = T / fps
    out = {'ver': VER, 'param': dict(P), 'n_peaks': len(pk), 'n_cont': len(cont), 'full': block(0, D), 'first30': block(0, min(30.0, D))}
    json.dump(out, open(cp, 'w'), ensure_ascii=False)
    return out


def overlay(n, od):
    """per_full の numbers（または作業AIの ana から作った numbers）の full・first30 を、山で切った数字で差し替えた写しを返す（元は変えない）"""
    y = resegment(od) if od and os.path.isdir(od) else None
    if not y: return n
    n = dict(n)
    for k in ('full', 'first30'):
        if isinstance(n.get(k), dict):
            n[k] = dict(n[k]); n[k].update({kk: v for kk, v in y[k].items()})
    n['_yama'] = {'n_peaks': y['n_peaks'], 'n_cont': y['n_cont'], 'ver': y['ver']}
    return n
