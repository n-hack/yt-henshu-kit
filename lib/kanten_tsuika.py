#!/usr/bin/env python3
# 観点の足し分（yt-hozon 10/16・依頼主「13観点で足りるの？」→ 作業AI 14:4x「1〜6・8・9＋間の場所を足す」）
#   per_full の自由に書かれた欄（transition・telop.emphasis・telop.color・sfx.kind・visual・anim・role）を決まった語に名寄せし、指標にする
#   from_per_full(d) → {'x_…': 値}。kanten.py の from_per_full の最後で v.update(...) すれば同じ形で線が出る（線は yt-henshu-2 が今の決め方で置く）
#   試し  python3 kanten_tsuika.py [per_full のフォルダ]   … 本ごとの値と見本の幅を出す
import re, colorsys, statistics

# ---- 名寄せの辞書（語の一部が入っていればその組。上から順に当てる）----
TR = [('全消し', r'全消し|全部入れ替え|白へ|前の絵を消す|リセット|暗転|切り替え|カット|場面転換|別の画面|入れ替え'),
      ('足し算', r'足し|足す|追加|残して|積む|重ね|下へ|下に|帯だけ差し替え|差し替え'),
      ('ワイプ', r'ワイプ|スライド|横から|流れ込'),
      ('ぼかし', r'ぼかし|フェード|ディゾルブ|溶け')]
ROLE = [('つかみ', r'フック|つかみ|問題提起|問い|煽り|損失|共感|結論の先出し|先出し'),
        ('言い切り', r'結論|主張|本質|否定|常識破り|言い切'),
        ('山', r'山|限定|希少'),
        ('証拠', r'権威|実績|証拠|事例|お客様の声|受講生'),
        ('説明', r'具体例|手順|比較|理由|説明|解説|例'),
        ('まとめ', r'まとめ|振り返り'),
        ('告知', r'CTA|告知|宣伝|案内|LINE|概要欄'),
        ('つなぎ', r'つなぎ|場面|挿入|実写')]
SFX = {'ドン': 'ドン', 'ポン/ピコ': 'ポン', 'シュッ': 'シュッ', 'キラーン': 'キラーン', 'カチッ': 'カチッ'}
EMPH_NONE = r'^\s*(なし|無し|-|—|None|null)?\s*$'
MOTION = [('揺れ', r'揺れ|揺ら|ブレ|振動|シェイク'), ('ズーム', r'ズーム|拡大|寄る|寄り|迫'), ('ぼかし', r'ぼかし|ブラー'),
          ('フェード', r'フェード'), ('パン', r'パン|横移動|スクロール'), ('飛び出し', r'ポップ|弾|跳ね|バウンド')]
SHAPE = [('比較', r'比較|対比|vs|VS|左右|2列|二列|表|ビフォー|before|前→後'),
         ('手順', r'手順|ステップ|STEP|流れ|矢印|→|①|フロー'),
         ('列挙', r'箇条|リスト|チェック|3つ|三つ|並べ|一覧|番号')]
REAL = r'実写|画面録画|スクショ|スクリーンショット|管理画面|写真|映像'
DIAG = r'図|アイコン|ピクト|イラスト|線画|矢印|表|グラフ'
HEX = re.compile(r'#([0-9A-Fa-f]{6})')


def cls(text, table):
    t = str(text or '')
    for name, pat in table:
        if re.search(pat, t): return name
    return None


def hue_of(color):
    """telop.color の最初の色（縁ではない）→ 赤・青・黄・金・灰・白・黒"""
    s = str(color or '')
    s = re.split(r'縁', s)[0]
    m = HEX.search(s)
    if not m: return None
    r, g, b = (int(m.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4))
    h, l, sat = colorsys.rgb_to_hls(r, g, b)
    if sat < 0.2 or l < 0.12 or l > 0.92:
        return '黒' if l < 0.25 else ('白' if l > 0.85 else '灰')
    h *= 360
    if h < 20 or h >= 330: return '赤'
    if h < 45: return '金'
    if h < 70: return '黄'
    if h < 170: return '緑'
    if h < 260: return '青'
    return '紫'


def _t(s, k):
    try: return float(s.get(k) or 0)
    except Exception: return 0.0


def _share(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _consist(pairs):
    """(組, 値) の並び → 組ごとに一番多い値が占める割合の、件数で重みを付けた平均（同じ役割に同じ物を使っているか）"""
    by = {}
    for g, x in pairs:
        if g and x: by.setdefault(g, []).append(x)
    n = sum(len(v) for v in by.values() if len(v) >= 3)
    if not n: return None
    return sum(max(v.count(y) for y in set(v)) for v in by.values() if len(v) >= 3) / n


def from_per_full(d):
    sc = sorted([s for s in d.get('scenes') or [] if isinstance(s, dict)], key=lambda s: _t(s, 't0'))
    D = float(d.get('duration_s') or 0); v = {}
    if not sc or not D: return v
    role = [s.get('role_group') or cls(s.get('role'), ROLE) for s in sc]   # 決まった語の欄（AGENT_FULL 追記14）があればそちらを使う
    # 1. 場面転換：話題（役割の組）が変わる所は全消し・同じ話題の中は足し算
    chg, same = [], []
    for i in range(1, len(sc)):
        tr = sc[i].get('transition_kind') or cls(sc[i].get('transition'), TR)
        if not tr or not role[i] or not role[i - 1]: continue
        (chg if role[i] != role[i - 1] else same).append(tr)
    if len(chg) >= 5: v['x_tr_clear_at_topic'] = sum(1 for x in chg if x in ('全消し', 'ワイプ', 'ぼかし')) / len(chg)
    if len(same) >= 5: v['x_tr_add_in_topic'] = sum(1 for x in same if x == '足し算') / len(same)
    trs = [s.get('transition_kind') or cls(s.get('transition'), TR) for s in sc]
    if any(trs): v['x_tr_kinds'] = float(len(set(x for x in trs if x)))
    # 2. 強調：強調した場面の割合・山の場面に集まっているか（山・言い切り・つかみの割合 ÷ ほかの割合）
    def _em(s):
        t = s.get('telop') or {}; k = t.get('emphasis_kind')
        if isinstance(k, list): return 1 if [x for x in k if x != 'なし'] else None
        return None if re.match(EMPH_NONE, str(t.get('emphasis') or '')) else 1
    em = [_em(s) for s in sc]
    has = [1 if e else 0 for e in em]
    v['x_emph_share'] = sum(has) / len(has)
    hi = [h for h, r in zip(has, role) if r in ('山', '言い切り', 'つかみ')]; lo = [h for h, r in zip(has, role) if r in ('説明', 'つなぎ', 'まとめ')]
    if len(hi) >= 5 and len(lo) >= 5 and sum(lo): v['x_emph_yama_ratio'] = (sum(hi) / len(hi)) / (sum(lo) / len(lo))
    # 3. 色の役割：役割ごとに同じ色（色相）で通しているか／言い切り・山に赤か金を使う割合
    hues = [(s.get('telop') or {}).get('color_hue') or hue_of((s.get('telop') or {}).get('color')) for s in sc]
    c = _consist([(r, h) for r, h in zip(role, hues) if h not in (None, '黒', '白', '灰')])
    if c is not None: v['x_color_role_consist'] = c
    k = [h in ('赤', '金') for r, h in zip(role, hues) if r in ('言い切り', '山') and h not in (None,)]
    if len(k) >= 5: v['x_color_redgold_on_key'] = sum(k) / len(k)
    # 4. 効果音の役割：役割ごとに同じ音を使っているか
    pairs = []
    for s, r in zip(sc, role):
        for x in s.get('sfx') or []:
            if isinstance(x, dict):
                kd = next((vv for kk, vv in SFX.items() if kk in str(x.get('kind') or '')), None)
                pairs.append((r, kd))
    c = _consist(pairs)
    if c is not None: v['x_sfx_role_consist'] = c
    # 5. BGM：告知に入る所（最初の告知の場面の頭 ±10秒）で曲か音量が変わったか（numbers.bgm_switch_candidates）
    n = d.get('numbers') or {}; sw = n.get('bgm_switch_candidates')
    cta = [_t(s, 't0') for s, r in zip(sc, role) if r == '告知']
    if isinstance(sw, list) and cta:
        ts = [float(x.get('t') if isinstance(x, dict) else x) for x in sw if (isinstance(x, (int, float)) or (isinstance(x, dict) and isinstance(x.get('t'), (int, float))))]
        v['x_bgm_switch_at_cta'] = 1.0 if any(abs(t - cta[0]) <= 10 for t in ts) else 0.0
    # 6. 図の形が話の形に合っているか（比較→左右・表／手順→流れ・矢印／列挙→箇条）
    #    形の分からない書き方（「図解」だけ）の場面は分母に入れない（10/16 yt-henshu-2 の指摘：Depy は比較8場面が「図解」だけで 0.24 に落ちていた）
    #    形を書いた割合は x_shape_named_share に別に出す（作業AIの記録で図解の形を書いていないと低く出る）
    ok = []; named = []
    for s in sc:
        want = cls(s.get('role'), SHAPE)
        if not want: continue
        vis = ' '.join(str((s.get('visual') or {}).get(x) or '') for x in ('kind', 'layout', 'what'))
        has = any(re.search(p, vis) for _, p in SHAPE); named.append(1 if has else 0)
        if has: ok.append(1 if re.search(dict(SHAPE)[want], vis) else 0)
    if len(ok) >= 5: v['x_shape_match'] = sum(ok) / len(ok)
    if len(named) >= 5: v['x_shape_named_share'] = sum(named) / len(named)
    # 7. 画面の動き：種類ごとの数/10分・山の場面で動きが多いか
    per10 = D / 600
    mot = [[nm for nm, pat in MOTION if re.search(pat, str(s.get('anim') or ''))] for s in sc]
    for nm, _ in MOTION: v['x_motion_%s_per10' % {'揺れ': 'shake', 'ズーム': 'zoom', 'ぼかし': 'blur', 'フェード': 'fade', 'パン': 'pan', '飛び出し': 'pop'}[nm]] = sum(1 for m in mot if nm in m) / per10
    hi = [len(m) for m, r in zip(mot, role) if r in ('山', '言い切り')]; lo = [len(m) for m, r in zip(mot, role) if r == '説明']
    if len(hi) >= 5 and len(lo) >= 5 and sum(lo): v['x_motion_yama_ratio'] = (sum(hi) / len(hi)) / (sum(lo) / len(lo))
    # 8. フック：最初の問い（「？」か問題提起）の秒・最初の言い切り（結論）の秒（最初のテロップの秒は見本42本とも0秒で差が出ないので測らない）
    q = [_t(s, 't0') for s in sc if '？' in str((s.get('telop') or {}).get('shown') or '') or '?' in str((s.get('telop') or {}).get('shown') or '') or re.search(r'問題提起|問い', str(s.get('role') or ''))]
    if q: v['x_hook_first_q_s'] = q[0]
    a = [_t(s, 't0') for s, r in zip(sc, role) if r == '言い切り']
    if a: v['x_hook_first_claim_s'] = a[0]
    # 9. 話の順番：①つかみが最初の1割に在る ②まとめが後ろ3分の1に在る ③告知が本編の真ん中（3〜7割）を食わない ④言い切りが前半に1回は在る → 満たした割合
    def at(g): return [_t(s, 't0') / D for s, r in zip(sc, role) if r == g]
    conds = [any(x <= 0.1 for x in at('つかみ')), any(x >= 0.66 for x in at('まとめ')),
             not any(0.3 <= x <= 0.7 for x in at('告知')), any(x <= 0.5 for x in at('言い切り'))]
    v['x_order_score'] = sum(conds) / len(conds)
    #    後半ほど速く：後半の画面の変化/分 ÷ 前半（scenes.frames.changes）
    half = D / 2; c1 = c2 = 0
    for s in sc:
        ch = (s.get('frames') or {}).get('changes')
        ch = len(ch) if isinstance(ch, list) else (ch if isinstance(ch, (int, float)) else None)
        if ch is None: continue
        if _t(s, 't0') < half: c1 += ch
        else: c2 += ch
    if c1: v['x_late_speedup'] = c2 / c1
    #    図解が続く最長（実写・画面録画を挟まずに図・アイコンの場面が続いた秒）
    run = best = 0.0
    for s in sc:
        vis = ' '.join(str((s.get('visual') or {}).get(x) or '') for x in ('kind', 'what'))
        dur = max(0.0, _t(s, 't1') - _t(s, 't0'))
        if re.search(REAL, vis): run = 0.0
        elif re.search(DIAG, vis): run += dur; best = max(best, run)
    v['x_diagram_run_max_s'] = best
    # 間の場所：0.3秒以上の間のうち、言い切り・まとめ・つかみの直後にある割合
    p03 = (n.get('4_silence') or {}).get('pauses_0.3s_plus')
    if isinstance(p03, list) and len(p03) >= 3:
        k = [cls(p.get('role'), ROLE) in ('言い切り', 'まとめ', 'つかみ', '山') for p in p03 if isinstance(p, dict)]
        if k: v['x_pause_at_key'] = sum(k) / len(k)
    return v


if __name__ == '__main__':
    import sys, json, glob, os
    d0 = sys.argv[1] if len(sys.argv) > 1 else '~/rin6/state/yt-anime-1014/kata/per_full'
    rows = {}
    for p in sorted(glob.glob(os.path.join(d0, '*.json'))):
        try: rows[os.path.basename(p)[:-5]] = from_per_full(json.load(open(p)))
        except Exception as e: print('err', p, e)
    keys = sorted({k for r in rows.values() for k in r})
    print('本', len(rows))
    for k in keys:
        xs = sorted(r[k] for r in rows.values() if k in r)
        q = lambda a: xs[min(len(xs) - 1, int(a * len(xs)))]
        print('%-26s n=%2d  中央 %.3g  10%% %.3g  90%% %.3g  最小 %.3g  最大 %.3g' % (k, len(xs), statistics.median(xs), q(0.1), q(0.9), xs[0], xs[-1]))
