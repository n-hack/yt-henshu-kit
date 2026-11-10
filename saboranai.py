#!/usr/bin/env python3
# サボらない門（作業AI・2026-10-15・依頼主「サボらない仕組みだけ作っておいて」「記録するだけだと意味ない」）
#   作業者の per_full/<id>.json の申告を信じず、元動画から自分で測った数字と突き合わせる。
#   python3 saboranai.py            … 全部測って報告・やり直し一覧・不合格があれば作業AIの知らせへ1行
#   python3 saboranai.py --id <id>  … 1本だけ（知らせは出さない）
#   python3 saboranai.py --budget 1500  … 重い測り（全コマの差）にかける秒の上限（既定 1500秒。残りは次の回）
# 置き場
#   報告        kata/full/saboranai-<日時>.md
#   やり直し    kata/full/yarinaoshi.txt（id<TAB>shard<TAB>理由）
#   門の控え    kata/full/saboranai/（cache=全コマ差の npz と測った数・verdict=1本ごとの判定）
import os, sys, json, time, glob, random, re, fcntl, datetime, statistics
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sokutei as S
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))
import vm_check   # 追記9 video_marketing（1本の流れ）の門。check.py と同じもの
import importlib.util
_sp = importlib.util.spec_from_file_location('mienai_kensa', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mienai-kensa.py'))
MIENAI = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(MIENAI)   # 画像が出なかった回（10/16 夜 shard5・shard6 の取り下げ）
_sp = importlib.util.spec_from_file_location('mienai_kotoba', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mienai-kotoba.py'))
KOTOBA = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(KOTOBA)   # 見た印（合言葉）。10/15 15:45 から記録に media removed が残らないので、こちらが本体
_ev_orig, _ev = MIENAI.events, {}
def _events_kioku():
    """events.jsonl（4.5MB）を本ごとに読み直していた（1本0.7秒）→ 大きさか更新時刻が変わったときだけ読み直す。返る中身は同じ"""
    try:
        st = os.stat(MIENAI.EVENTS); k = (st.st_size, st.st_mtime_ns)
    except OSError:
        k = None
    if k is None or _ev.get('k') != k:
        _ev['k'] = k; _ev['v'] = _ev_orig()
    return _ev['v']
MIENAI.events = _events_kioku

BASE = '~/rin6/state/yt-anime-1014'
FULL = os.path.join(BASE, 'kata/full')
PER = os.path.join(BASE, 'kata/per_full')
SOZAI = os.path.join(BASE, 'sozai2')
ME = os.path.join(FULL, 'saboranai')
CACHE = os.path.join(ME, 'cache'); VERD = os.path.join(ME, 'verdict'); TMP = os.path.join(ME, 'tmp')
ALERT = os.path.expanduser('~/rin6/state/rin6-todo-alerts.jsonl')
STATE = os.path.join(ME, 'state.json')

# ---- 合格の線（ここを変えたら報告の「線」にも出る） ----
LINE = dict(
    FRAMES_TOL=2,            # frames_total と実フレーム数の差は 2コマまで
    GAP_MAX_S=1.0,           # 場面の隙間の合計は 1秒 または 長さの 0.5% の大きい方まで
    GAP_MAX_FRAC=0.005,
    MUST_SEEN_MIN=0.95,      # 追記3 の「見るべきコマ」（独立に選んだもの）のうち見た割合が 95% 以上
    RUN_UNSEEN_TOL=0.02,     # 「ランの間で見なかった」は 独立に数えた61コマ超ランの間（5コマおきの外）の数 +2% まで
    STILL_UNSEEN_TOL=0.05,   # 「静止」＋「ゆらぎのみ」で見なかった数は 独立に数えた 静止＋ゆらぎ の +5% まで
    SEL_MISS_MAX=0.50,       # scenes[].selection（追記4）が無い場面の割合
    VIS_MISS_MAX=0.50,       # 文字のある場面のうち telop.visibility（追記2）が無い割合
    SCENES_MIN_RATIO=0.50,   # 場面の数は 独立に数えた場面転換の 50% 以上
    SAMPLE=5,                # 抜き取る場面の数
    COLOR_MISS_MAX=0.34,     # 書かれた16進のうち画面に無いものが 34% を超えたら不合格（3色以上見たとき）
    TEXT_HIT_MIN=0.50,       # telop.shown の文字の 50% 以上が画面で読めれば その場面は当たり
    TEXT_MISS_MAX=0.40,      # 外れの場面が 40% を超え、かつ 2場面以上で不合格
    NOHEX_MAX=0.50,          # 文字のある場面のうち telop.color に16進が無い（目分量）割合が 50% を超えたら不合格
    FUMEI_MAX=0.30,          # 場面の欄のうち「不明」の割合
    WHY_RUN_MAX=3,           # 同じ why が 3場面以上続いたら不合格
    WHY_DUP_MAX=0.40,        # 同じ本の中で why が他の場面と同じ文の割合
    CROSS_WHY_MAX=0.30,      # why が別の本と同じ文の割合
    CROSS_JACCARD_MAX=0.50,  # 本どうしの文（5文字の切れ端）の重なり
    SPEED_MIN_RATIO=1.0,     # 1本にかけた時間 ÷ 動画の長さ が 1.0 未満は速すぎ
    SE_CORR_MIN=0.45,        # 効果音と元動画のその秒の音の相関
    SE_MARGIN_MIN=0.10,      # 相関は 5秒ずらした所より 0.10 以上高いこと
    SHEET_MISS_MAX=0.25,     # シートごとの抜き取り（画像を見ないと書けない事実）の外れが全シートの 25% を超えたら不合格
    SHEET_PART_MISS_MAX=0.40,  # 前・中・後ろの どの区間でも 外れが 40% を超えたら不合格（後ろだけ見て前を推した、を捕まえる）
    GEO_H_TOL=0.35,          # 字の高さ：書いた px と画面の文字の箱の高さの差が 35% 以内（か 14px 以内）
    GEO_POS_TOL=0.10,
    GEO_MIN_PX=30,           # 字の高さが 30px 未満の行（背景の細かい字）は文字読みが拾えないので抜き取りに選ばない（10/16 目で確かめた）        # 文字の位置：書いた余白から出した中心と画面の文字の中心の差が 画面の幅・高さの 10% 以内
    VM=vm_check.LINE,        # 追記9 video_marketing：無い・薄い（target・promise・hook の秒・flow・retention・cta・why_it_works 3つ・reusable 3〜5）は不合格
)


def load_shards():
    m = {}
    for n in range(8):
        p = os.path.join(FULL, 'shard%d.txt' % n)
        if not os.path.exists(p): continue
        for line in open(p):
            line = line.strip()
            if not line: continue
            vid = os.path.splitext(os.path.basename(line))[0]
            m[vid] = {'shard': n, 'mp4': os.path.join(BASE, line)}
    return m


def jload(p, d=None):
    try:
        return json.load(open(p))
    except Exception:
        return d


def jsave(p, d):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'; json.dump(d, open(tmp, 'w'), ensure_ascii=False, indent=1); os.replace(tmp, p)


# ---------- 重い測り：元動画を全コマ ----------
def measure(vid, mp4):
    p = os.path.join(CACHE, vid + '.json')
    m = jload(p)
    if m and m.get('th') == S.THRESHOLDS and m.get('blk_th') == S.BLK_TH: return m
    pr = S.probe(mp4)
    t = time.time()
    fd = S.framediff(mp4, os.path.join(CACHE, vid + '.npz'))
    fps = pr['fps']
    cuts = S.cuts_from_diff(fd, fps)
    bd = S.blockdiff(mp4, os.path.join(CACHE, vid + '.blk.npz'))
    ms = S.must_see(bd, fd['cutfrac'])
    ms.pop('must')
    m = {'probe': pr, 'decoded': int(fd['n']), 'same': int(fd['same'].sum()), 'any': int((~fd['same']).sum()),
         'vis': int((fd['vis'] >= S.VIS_MIN_PX).sum()), 'cuts': len(cuts), 'cut_t': [round(x, 3) for x in cuts],
         'changes': len(S.changes_from_diff(fd, fps)), 'blk_n': int(bd['n']), 'blk': ms,
         'sec': round(time.time() - t, 1), 'th': S.THRESHOLDS, 'blk_th': S.BLK_TH}
    jsave(p, m)
    return m


# ---------- 申告の内訳（追記3） ----------
ALIAS = {
    'seen': ('frames_seen', '見たコマ'),
    'still': ('static_identical_unseen', 'static_unseen', 'identical_unseen', '静止', '静止（完全一致）'),
    'yuragi': ('yuragi_only_unseen', 'yuragi_unseen', 'jitter_only_unseen', 'ゆらぎのみ'),
    'run': ('run_unseen', 'run_gap_unseen', 'run_mid_unseen', 'ランの間で見なかったコマ', 'ランの間で見なかった'),
}


def breakdown(d):
    """numbers.frames → numbers → 上の段 の順で内訳を探す（作業者ごとに置き場が違ってもよい）"""
    nums = d.get('numbers') if isinstance(d.get('numbers'), dict) else {}
    places = [nums.get('frames'), (nums.get('full') or {}) if isinstance(nums.get('full'), dict) else None, nums, d]
    out = {}
    for k, names in ALIAS.items():
        for pl in places:
            if not isinstance(pl, dict): continue
            v = next((pl[n] for n in names if isinstance(pl.get(n), (int, float))), None)
            if v is not None:
                out[k] = int(v); break
    return out


def seen_list(vid, d):
    """見たコマの番号の一覧があれば（per_full の frames_seen_list か、作業者の raw/<id>/pick.json）"""
    for pl in (d, (d.get('numbers') or {}).get('frames') if isinstance(d.get('numbers'), dict) else None):
        if isinstance(pl, dict) and isinstance(pl.get('frames_seen_list'), list):
            return set(int(x) for x in pl['frames_seen_list']), 'per_full'
    pk = jload(os.path.join(FULL, 'raw', vid, 'pick.json'))
    if isinstance(pk, dict) and isinstance(pk.get('seen'), dict):
        return set(int(x) for x in pk['seen']), 'raw/%s/pick.json' % vid
    return None, None


# ---------- 文の正規化 ----------
def nt(s):
    return re.sub(r'[\s、。,.!！?？・「」『』（）()\[\]【】\d]+', '', str(s or ''))


def leaves(o):
    if isinstance(o, dict):
        for v in o.values(): yield from leaves(v)
    elif isinstance(o, list):
        for v in o: yield from leaves(v)
    elif isinstance(o, str):
        yield o


def shingles(s, k=5):
    s = nt(s)
    return {s[i:i + k] for i in range(max(0, len(s) - k + 1))}


def scene_text(sc):
    return ' '.join(str(sc.get(k, '')) for k in ('intent', 'why', 'anim', 'transition')) + ' ' + json.dumps(sc.get('telop', {}), ensure_ascii=False) \
        + ' ' + json.dumps(sc.get('visual', {}), ensure_ascii=False)


# ---------- 1本の判定 ----------
def judge(vid, info, d, m):
    fails, notes = [], []
    dur = float(m['probe']['duration'] or d.get('duration_s') or 0)
    real_frames = m['decoded']
    sc = [s for s in d.get('scenes', []) if isinstance(s, dict)]
    # 1 網羅
    if d.get('window') not in (None, 'full') or any(s.get('window') not in (None, 'full') for s in sc):
        fails.append('window が full でない場面がある（窓だけ見た疑い）')
    ft = d.get('frames_total')
    if ft is None:
        fails.append('frames_total が書かれていない')
    elif abs(int(ft) - real_frames) > LINE['FRAMES_TOL']:
        fails.append('frames_total 申告 %s ／ 実測 %d（ffprobe パケット %d）' % (ft, real_frames, m['probe']['packets']))
    iv = sorted((float(s.get('t0', 0)), float(s.get('t1', 0))) for s in sc if s.get('t1') is not None)
    gaps = []; cur = 0.0
    for a, b in iv:
        if a > cur + 0.05: gaps.append((round(cur, 2), round(a, 2)))
        cur = max(cur, b)
    if dur - cur > 0.05: gaps.append((round(cur, 2), round(dur, 2)))
    gap_s = sum(b - a for a, b in gaps)
    gap_lim = max(LINE['GAP_MAX_S'], LINE['GAP_MAX_FRAC'] * dur)
    if gap_s > gap_lim:
        big = sorted(gaps, key=lambda g: g[0] - g[1])[:5]
        fails.append('場面の隙間 計%.1f秒（線 %.1f秒）例 %s' % (gap_s, gap_lim, ', '.join('%s〜%s' % g for g in big)))
    # 2 見たコマの数
    fs = d.get('frames_seen')
    if fs is None:
        fails.append('frames_seen が書かれていない')
    else:
        fs = int(fs)
        if fs > real_frames + LINE['FRAMES_TOL']:
            fails.append('frames_seen %d が 全コマ %d より多い' % (fs, real_frames))
        # 2a 内訳を足すと frames_total
        bk = breakdown(d); bk['seen'] = fs
        lack = [k for k in ('still', 'yuragi', 'run') if k not in bk]
        if lack:
            fails.append('numbers に内訳が無い：%s（追記3：見た・静止・ゆらぎのみ・ランの間で見なかった を分けて書く）'
                         % '・'.join({'still': '静止（完全一致）', 'yuragi': 'ゆらぎのみ', 'run': 'ランの間で見なかった'}[k] for k in lack))
        else:
            tot = bk['seen'] + bk['still'] + bk['yuragi'] + bk['run']
            if ft is not None and abs(tot - int(ft)) > LINE['FRAMES_TOL']:
                fails.append('内訳の合計 %d（見た %d＋静止 %d＋ゆらぎ %d＋ランの間 %d）が frames_total %s と合わない'
                             % (tot, bk['seen'], bk['still'], bk['yuragi'], bk['run'], ft))
        # 2b 見るべきコマ（独立に選んだもの）を見たか
        bl = m['blk']
        sl, src = seen_list(vid, d)
        if sl is not None and abs(len(sl) - fs) <= LINE['FRAMES_TOL']:
            must = S.must_see(np.load(os.path.join(CACHE, vid + '.blk.npz')),
                              np.load(os.path.join(CACHE, vid + '.npz'))['cutfrac'])['must']
            hit = sum(1 for f in must if int(f) in sl)
            how = '一覧（%s）と照合' % src
        else:
            hit = min(fs, bl['n_must'])
            how = '数で比べた（見たコマの一覧なし）' if sl is None else '一覧 %d コマが frames_seen と合わないので数で比べた' % len(sl)
        ratio = hit / max(1, bl['n_must'])
        m['_seen_note'] = '見るべき %d のうち見た %d（%.1f%%・%s）' % (bl['n_must'], hit, 100 * ratio, how)
        if ratio < LINE['MUST_SEEN_MIN']:
            fails.append('追記3の見るべきコマ %d のうち見た %d（%.1f%%・%s）。見るべき＝ラン60以下の全コマ＋61超の頭10・終わり10・5コマおき・跳ねたコマ %d＋止まった直後'
                         % (bl['n_must'], hit, 100 * ratio, how, bl['jumps']))
        # 2c ランの間で見なかった数 ≦ 独立に数えた 61超ランの間（5コマおきの外）
        if 'run' in bk:
            lim = bl['run_mid_offgrid'] * (1 + LINE['RUN_UNSEEN_TOL']) + LINE['FRAMES_TOL']
            if bk['run'] > lim:
                fails.append('「ランの間で見なかった」%d が 独立に数えた 61コマ超ランの間（5コマおきの外）%d より多い（ラン %d・うち61超 %d）'
                             % (bk['run'], bl['run_mid_offgrid'], bl['runs'], bl['runs_over60']))
        if 'still' in bk and 'yuragi' in bk:
            lim = (bl['identical'] + bl['yuragi']) * (1 + LINE['STILL_UNSEEN_TOL']) + LINE['FRAMES_TOL']
            if bk['still'] + bk['yuragi'] > lim:
                fails.append('見なかった 静止＋ゆらぎ %d が 独立に数えた 静止 %d＋ゆらぎ %d より多い（動いたコマを静止扱いにした疑い）'
                             % (bk['still'] + bk['yuragi'], bl['identical'], bl['yuragi']))
    if len(sc) < LINE['SCENES_MIN_RATIO'] * m['cuts']:
        fails.append('場面 %d ／ 独立に数えた場面転換 %d（%.0f%%）' % (len(sc), m['cuts'], 100 * len(sc) / max(1, m['cuts'])))
    # 4 使い回し（本の中）
    vals = [v for s in sc for v in leaves(s)]
    fumei = sum(1 for v in vals if '不明' in v) / max(1, len(vals))
    if fumei > LINE['FUMEI_MAX']:
        fails.append('「不明」が欄の %.0f%%' % (100 * fumei))
    whys = [nt(s.get('why')) for s in sc]
    run = best = 1
    for i in range(1, len(whys)):
        run = run + 1 if whys[i] and whys[i] == whys[i - 1] else 1
        best = max(best, run)
    if best >= LINE['WHY_RUN_MAX']:
        fails.append('同じ why が %d 場面続く' % best)
    c = Counter(w for w in whys if w)
    dup = sum(n for n in c.values() if n > 1) / max(1, len(whys))
    if dup > LINE['WHY_DUP_MAX']:
        fails.append('why の %.0f%% が同じ本の別の場面と同じ文' % (100 * dup))
    # 目分量の色
    shown_sc = [s for s in sc if nt((s.get('telop') or {}).get('shown')) not in ('', 'なし', '不明')]
    nohex = sum(1 for s in shown_sc if not S.hexes(str((s.get('telop') or {}).get('color')))) / max(1, len(shown_sc))
    if shown_sc and nohex > LINE['NOHEX_MAX']:
        fails.append('文字のある場面の %.0f%% で telop.color に16進が無い（画素から拾っていない）' % (100 * nohex))
    # 追記4 selection・追記2 visibility の有無
    nosel = sum(1 for s in sc if not s.get('selection')) / max(1, len(sc))
    if sc and nosel > LINE['SEL_MISS_MAX']:
        fails.append('場面の %.0f%% に selection（話した言葉→画面に出したもの・追記4）が無い' % (100 * nosel))
    novis = sum(1 for s in shown_sc if not (s.get('telop') or {}).get('visibility')) / max(1, len(shown_sc))
    if shown_sc and novis > LINE['VIS_MISS_MAX']:
        fails.append('文字のある場面の %.0f%% に telop.visibility（見やすさの数字・追記2）が無い' % (100 * novis))
    # 追記9 1本の流れ（video_marketing）。依頼主 10/15 19:55「動画1本単位でちゃんとマーケター目線で分析」
    fails += vm_check.fails(d.get('video_marketing'), dur)
    bl = m['blk']; bk = breakdown(d)
    notes.append('長さ %.1f秒・全コマ %d・場面転換 %d・場面 %d・隙間 %.1f秒・不明 %.0f%%' % (dur, real_frames, m['cuts'], len(sc), gap_s, 100 * fumei))
    notes.append('門の32x32：静止 %d・ゆらぎ %d・動き %d・ラン %d（61超 %d）・見るべき %d・61超ランの間（5コマおきの外）%d'
                 % (bl['identical'], bl['yuragi'], bl['moving'], bl['runs'], bl['runs_over60'], bl['n_must'], bl['run_mid_offgrid']))
    notes.append('申告：見た %s・静止 %s・ゆらぎ %s・ランの間 %s・%s' % (d.get('frames_seen'), bk.get('still', '無し'), bk.get('yuragi', '無し'), bk.get('run', '無し'),
                                                       m.pop('_seen_note', '見るべきコマの照合なし')))
    return fails, notes


def spot(vid, info, d, seed):
    """3 中身の抜き取り：無作為に場面を選び、元動画のコマで色と文字を照合"""
    sc = [s for s in d.get('scenes', []) if isinstance(s, dict) and s.get('t1') is not None and float(s['t1']) > float(s.get('t0', 0))]
    rnd = random.Random(seed)
    pick = rnd.sample(sc, min(LINE['SAMPLE'], len(sc)))
    os.makedirs(TMP, exist_ok=True)
    rows = []; all_lab = []; plan = []
    # 1) 場面ごとにコマを切り出す（文字読みは最後にまとめて＝場面ごとに Vision を起こさない・10/17）
    for k, s in enumerate(pick):
        t0, t1 = float(s.get('t0', 0)), float(s['t1'])
        ts = sorted({round(min(t1 - 0.05, max(t0 + 0.1, t0 + f * (t1 - t0))), 2) for f in (0.0, 0.33, 0.66, 1.0)})
        frames = pmap(lambda t: S.grab(info['mp4'], t), ts)
        labs = [S.rgb2lab(f) for f in frames if f is not None]
        all_lab += labs
        pngs = grab_pngs([(info['mp4'], t, os.path.join(TMP, '%s_%d_%d.png' % (vid, k, j))) for j, t in enumerate(ts)])
        plan.append((s, t0, t1, labs, pngs))
    rd = ocr_many([p for x in plan for p in x[4]], S.ocr)
    # 2) 場面ごとに色と文字を照合
    for s, t0, t1, labs, pngs in plan:
        texts = [x for p in pngs for x in rd.get(p, [])]
        tel = s.get('telop') or {}
        hx = S.hexes(str(tel.get('color'))) + S.hexes(str(tel.get('zabuton')))
        col = [(h,) + S.color_presence(labs, h) for h in hx]
        shown = str(tel.get('shown') or '')
        th = None if nt(shown) in ('', 'なし', '不明') else S.text_hit(shown, texts)
        rows.append({'t0': t0, 't1': t1, 'colors': [(h, bool(ok), round(de, 1)) for h, ok, de in col], 'shown': shown[:60],
                     'text_hit': None if th is None else round(th, 2), 'ocr': ' / '.join(texts)[:120]})
        for p in pngs:
            try: os.remove(p)
            except Exception: pass
    bg = S.hexes(str((d.get('base_look') or {}).get('bg')))
    bgc = [(h,) + S.color_presence(all_lab, h) for h in bg]
    fails = []
    cc = [c for r in rows for c in r['colors']] + [(h, bool(ok), round(de, 1)) for h, ok, de in bgc]
    miss = [c for c in cc if not c[1]]
    if len(cc) >= 3 and len(miss) / len(cc) > LINE['COLOR_MISS_MAX']:
        fails.append('色の16進 %d 中 %d が画面に無い（例 %s）' % (len(cc), len(miss), ', '.join('%s ΔE%.0f' % (h, de) for h, _, de in miss[:4])))
    tt = [r for r in rows if r['text_hit'] is not None]
    tm = [r for r in tt if r['text_hit'] < LINE['TEXT_HIT_MIN']]
    if len(tm) >= 2 and len(tm) / max(1, len(tt)) > LINE['TEXT_MISS_MAX']:
        fails.append('テロップの文字 %d 場面中 %d が画面に無い（例 %.1f秒「%s」→ 画面「%s」）' % (len(tt), len(tm), tm[0]['t0'], tm[0]['shown'][:20], tm[0]['ocr'][:30]))
    return fails, {'rows': rows, 'bg': [(h, bool(ok), round(de, 1)) for h, ok, de in bgc]}


def ocr_boxes(paths):
    """macOS Vision → {path: [(文字, x, y, w, h), ...]}（0〜1・左上原点）"""
    import subprocess
    if not paths: return {}
    o = subprocess.run([S.OCR_BIN] + list(paths), capture_output=True, text=True, timeout=900).stdout   # 混んでいると80枚で120秒を超えた（10/16）
    r = {}
    for line in o.splitlines():
        try: q = json.loads(line)
        except Exception: continue
        r[q['p']] = [tuple(x[:5]) for x in (q.get('r') or [])]
    return r


# 文字読みの回し方（10/17 23:2x 実測・1920x1080 を40枚）：1本で119秒／4本同時で62秒／8本同時で33秒。1枚ずつの結果は1字も違わない。
#   1回に渡す枚数は20枚で1枚2.95秒・40枚で2.98秒＝増やしても速くならない（遅いのは Vision の1枚ごとの待ち）。動画の書き出しに GPU を残すため同時4本
OCR_PAR = 4
OCR_CHUNK = 20


def pmap(fn, items):
    """fn を OCR_PAR 本同時に（返す順は items の順のまま）。コマの切り出し（ffmpeg）に使う：混んでいると1枚2.6秒かかり、1本で200枚を1枚ずつ待っていた（10/18）"""
    from concurrent.futures import ThreadPoolExecutor
    items = list(items)
    if len(items) <= 1: return [fn(x) for x in items]
    with ThreadPoolExecutor(OCR_PAR) as ex:
        return list(ex.map(fn, items))


def grab_pngs(jobs):
    """[(mp4, 秒, 置き場)] を同時に切り出し、できたもの（ファイルがある）の置き場を順に返す"""
    ok = pmap(lambda j: S.grab_png(*j), jobs)
    return [j[2] for j, o in zip(jobs, ok) if o]


def ocr_many(paths, fn=ocr_boxes):
    """fn（ocr_boxes か S.ocr）を OCR_CHUNK 枚以下ずつ OCR_PAR 本同時に回して1つにまとめる"""
    from concurrent.futures import ThreadPoolExecutor
    paths = list(paths)
    if not paths: return {}
    k = max(1, min(OCR_CHUNK, -(-len(paths) // OCR_PAR)))
    r = {}
    with ThreadPoolExecutor(OCR_PAR) as ex:
        for x in ex.map(fn, [paths[i:i + k] for i in range(0, len(paths), k)]): r.update(x)
    return r


_LOOK = str.maketrans({'ニ': '二', 'ー': '一', 'ロ': '口', 'カ': '力', 'エ': '工', 'ハ': '八', 'ト': '卜', 'タ': '夕', '〇': '0', 'O': '0', 'o': '0', 'l': '1', 'I': '1', '|': '1'})
def _look(s):
    """文字読みが取り違えやすい形の似た字をそろえる（第ニ弾→第二弾 など・10/16 目で確かめた）"""
    return (s or '').translate(_LOOK)


def sheet_ranges(vid, d, fps, n_frames):
    """作業者が見たシートごとのコマの範囲（raw/<id>/pick.json の sheets）。無ければ sb の枚数で全コマを等分"""
    pk = jload(os.path.join(FULL, 'raw', vid, 'pick.json'))
    if isinstance(pk, dict) and isinstance(pk.get('sheets'), list) and pk['sheets'] and isinstance(pk['sheets'][0], list):
        return [(min(x) / fps, max(x) / fps) for x in pk['sheets'] if x], 'pick.json'
    k = len(glob.glob(os.path.join(FULL, 'raw', vid, 'sb', 's*.jpg'))) or 60
    return [(i * n_frames / k / fps, (i + 1) * n_frames / k / fps) for i in range(k)], '全コマを%d等分' % k


def sheet_spot(vid, info, d, m, seed):
    """3b 全シートの抜き取り（10/16 取り下げ3件目のあと）：シートごとに1場面を選び、画像を見ないと書けない事実を1つずつ元動画のコマで確かめる。
    事実は ①テロップの位置と字の高さ（visibility の margin_px・height_px を文字の箱と照合） ②テロップ・座布団の色の16進（ΔE）の順で選ぶ。
    確かめる事実が書かれていない場面しか無いシートも外れに数える。前・中・後ろの3区間に分けて外れの割合を見る"""
    fps = float(m['probe'].get('fps') or d.get('fps') or 30); dur = float(m['probe']['duration'] or d.get('duration_s') or 0)
    rngs, how = sheet_ranges(vid, d, fps, m['decoded'])
    sc = [s for s in d.get('scenes', []) if isinstance(s, dict) and s.get('t1') is not None]
    rnd = random.Random(seed); os.makedirs(TMP, exist_ok=True); rows = []; plans = []
    def facts(s):
        tel = s.get('telop') or {}
        geo = [r for r in (tel.get('visibility') or []) if isinstance(r, dict) and isinstance(r.get('height_px'), (int, float)) and isinstance(r.get('margin_px'), dict)
               and nt(r.get('text')) and r['height_px'] >= LINE['GEO_MIN_PX'] and len(S.norm_chars(r.get('text'))) >= 2]
        hx = S.hexes(str(tel.get('color'))) + S.hexes(str(tel.get('zabuton')))
        return geo, hx
    # 1) シートごとに確かめる事実を決めてコマを切り出す（文字読みは最後にまとめて1回＝Vision を1回だけ起こす）
    for k, (a, b) in enumerate(rngs):
        part = min(2, int(3 * ((a + b) / 2) / max(dur, 1e-6)))
        cand = [s for s in sc if float(s['t1']) > a and float(s.get('t0', 0)) < b and any(facts(s))]
        if not cand:
            rows.append({'sheet': k, 'part': part, 't': round(a, 2), 'kind': 'なし', 'ok': False, 'why': 'このシートの範囲に、画像を見ないと書けない事実（位置・字の高さ・色）を書いた場面が無い'}); continue
        s = rnd.choice(cand); geo, hx = facts(s)
        lo, hi = max(a, float(s.get('t0', 0))), min(b, float(s['t1']))
        # 10/16 目で確かめた：足し算で後から出る文字・ぼかしで入る途中・1〜2秒で替わる下の字幕帯を 0.2/0.7 の2枚では外していた（門の測り違い）
        #   → 場面の中を約0.6秒おき（3〜12枚）。事実は「その場面のどこかのコマで、書いた位置と高さに書いた字がある」で見る
        n_ = max(3, min(12, int(max(0.0, hi - lo) / 0.6) + 1))
        ts = sorted({round(lo + (k_ + 0.5) / n_ * max(0.0, hi - lo - 0.05), 2) for k_ in range(n_)})
        if geo:
            r = rnd.choice(geo)
            plans.append((k, part, ts, r, [(info['mp4'], t, os.path.join(TMP, '%s_sh%d_%d.png' % (vid, k, j))) for j, t in enumerate(ts)]))
        else:
            frames = pmap(lambda t: S.grab(info['mp4'], t), ts)
            labs = [S.rgb2lab(f) for f in frames if f is not None]
            res = [(h,) + S.color_presence(labs, h) for h in hx]
            ok = sum(1 for x in res if x[1]) >= max(1, (len(res) + 1) // 2)
            rows.append({'sheet': k, 'part': part, 't': ts[0] if ts else round(a, 2), 'kind': '色', 'ok': bool(ok), 'why': ' '.join('%s ΔE%.0f' % (h, de) for h, _, de in res)})
    # コマの切り出しは最後にまとめて同時に（1枚ずつ待たない）。できたコマだけを使うのは前と同じ
    got = set(grab_pngs([j_ for pl in plans for j_ in pl[4]]))
    plans = [(k, part, ts, r, [j_[2] for j_ in jobs if j_[2] in got]) for k, part, ts, r, jobs in plans]
    bx = ocr_many([p_ for pl in plans for p_ in pl[4]])
    # 2) 書いた字の高さ・位置と、画面の文字の箱を照合
    for k, part, ts, r, pngs in plans:
        mg = r['margin_px']; want = nt(r.get('text'))
        cx = (mg.get('left', 0) + 1920 - mg.get('right', 0)) / 2 / 1920; cy = (mg.get('top', 0) + 1080 - mg.get('bottom', 0)) / 2 / 1080
        best = None; cands = []
        for pth in pngs:
            for (tx, x, y, w, h) in bx.get(pth, []):
                hit = S.text_hit(_look(want), [_look(tx)]) or 0
                if hit < 0.5: continue
                wn, tn = ''.join(S.norm_chars(_look(want))), ''.join(S.norm_chars(_look(tx)))
                if wn and tn and wn in tn and len(wn) < len(tn) and w > h:   # 書いた語が横書きの行の一部（色分けした語など）→ その部分の中心
                    i_ = tn.index(wn); x, w = x + w * i_ / len(tn), w * len(wn) / len(tn)
                cands.append((hit, x, y, w, h))
        top = max((c[0] for c in cands), default=0)
        for (hit, x, y, w, h) in cands:
            if hit < top - 0.15: continue   # 字の一致が明らかに低い隣の行（第一弾と第二弾など）には当てない
            dh = abs(h * 1080 - r['height_px']); dpos = max(abs(x + w / 2 - cx), abs(y + h / 2 - cy))
            sc_ = dh / max(r['height_px'], 1) + dpos
            if best is None or sc_ < best[0]: best = (sc_, round(h * 1080), round(dpos, 3))
            try: os.remove(pth)
            except Exception: pass
        if best is None:
            ok, why = False, '書いた文字「%s」が画面で見つからない' % r.get('text', '')[:12]
        else:
            ok = abs(best[1] - r['height_px']) <= max(LINE['GEO_H_TOL'] * r['height_px'], 14) and best[2] <= LINE['GEO_POS_TOL']
            why = '「%s」高さ 書いた%dpx／画面%dpx・位置のずれ %.0f%%' % (r.get('text', '')[:12], r['height_px'], best[1], 100 * best[2])
        rows.append({'sheet': k, 'part': part, 't': ts[0] if ts else 0, 'kind': '位置と字の高さ', 'ok': bool(ok), 'why': why})
    rows.sort(key=lambda r: r['sheet'])
    fails = []
    if rows:
        miss = sum(1 for r in rows if not r['ok']) / len(rows)
        if miss > LINE['SHEET_MISS_MAX']:
            fails.append('全シートの抜き取り %d 枚中 %d 枚で画像の事実が合わない（%.0f%%・線 %.0f%%）例 %s' % (len(rows), sum(1 for r in rows if not r['ok']), 100 * miss,
                         100 * LINE['SHEET_MISS_MAX'], '；'.join('シート%d %.0f秒 %s' % (r['sheet'], r['t'], r['why']) for r in rows if not r['ok'])[:300]))
        for pt, nm in enumerate(('前', '中', '後ろ')):
            rr = [r for r in rows if r['part'] == pt]
            if rr and sum(1 for r in rr if not r['ok']) / len(rr) > LINE['SHEET_PART_MISS_MAX']:
                fails.append('%sの区間で抜き取り %d 枚中 %d 枚が合わない（その区間の画像を見ていない疑い）' % (nm, len(rr), sum(1 for r in rr if not r['ok'])))
    return fails, {'how': how, 'rows': rows, 'by_part': [[sum(1 for r in rows if r['part'] == p and r['ok']), sum(1 for r in rows if r['part'] == p)] for p in range(3)]}


# ---------- 本どうし・速さ ----------
SH_VER = 'scene_text+shingles5:v1'   # 下の切れ端の作り方を変えたらここも変える（控えを使わなくなる）


def book_shingles(vid, d, mt):
    """1本の文の切れ端（本どうしの重なり用）。per_full の更新時刻が同じなら控えを使う（毎回 73本ぶん作り直すと混んだ時に3分かかった・10/18）"""
    import pickle
    p = os.path.join(CACHE, vid + '.shingles.pkl')
    try:
        c = pickle.load(open(p, 'rb'))
        if c.get('mt') == mt and c.get('ver') == SH_VER: return c['v']
    except Exception:
        pass
    v = set().union(*[shingles(scene_text(s)) for s in d.get('scenes', [])] or [set()])
    try:
        tmp = '%s.%d.tmp' % (p, os.getpid()); pickle.dump({'mt': mt, 'ver': SH_VER, 'v': v}, open(tmp, 'wb')); os.replace(tmp, p)
    except Exception:
        pass
    return v


def cross(per):
    out = {}
    why_owner = {}
    for vid, (d, mt) in sorted(per.items(), key=lambda x: x[1][1]):
        for s in d.get('scenes', []):
            w = nt(s.get('why'))
            if len(w) >= 8: why_owner.setdefault(w, vid)
    sh = {vid: book_shingles(vid, d, mt) for vid, (d, mt) in per.items()}
    ids = sorted(per, key=lambda v: per[v][1])
    for i, a in enumerate(ids):
        d = per[a][0]
        ws = [nt(s.get('why')) for s in d.get('scenes', [])]
        ws = [w for w in ws if len(w) >= 8]
        other = [w for w in ws if why_owner.get(w) not in (None, a)]
        f = []
        if ws and len(other) / len(ws) > LINE['CROSS_WHY_MAX']:
            f.append('why の %.0f%% が先に書かれた別の本（例 %s）と同じ文' % (100 * len(other) / len(ws), why_owner[other[0]]))
        for b in ids[:i]:
            A, B = sh[a], sh[b]
            if A and B:
                k = len(A & B); j = k / (len(A) + len(B) - k)   # ＝ len(A & B) / len(A | B)（同じ整数の割り算・和集合を作らない分だけ速い）
                if j > LINE['CROSS_JACCARD_MAX']:
                    f.append('先に書かれた %s と文の重なり %.0f%%（コピペの疑い）' % (b, 100 * j)); break
        if f: out[a] = f
    return out


def progress_times():
    """progress-*.txt の「時刻 id 場面数」の行から、その本を最初に書き終えた時刻（取り下げ・破棄の行は数えない）"""
    first = {}
    for pg in glob.glob(os.path.join(FULL, 'progress-*.txt')):
        # 日付の無い行は、その前にある日付つきの行の日付を引き継ぐ（10/17 6d の指摘：ファイルの更新日を当てると前日の行が「今日」になり速すぎと誤判定）
        # 前に日付つきの行が無いときだけ更新日を使い、更新時刻より後の時刻なら前の日とみなす
        mt = os.path.getmtime(pg)
        lines = open(pg).read().splitlines()
        # 先頭の日付無し行は、最初の日付つき行の日付（その時刻より後なら前の日）。日付つき行が無いときは更新日
        first_dated = next((l.split()[:2] for l in lines if re.match(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', l)), None)
        day = None
        for line in lines:
            w = line.split()
            if len(w) >= 4 and re.match(r'\d{4}-\d\d-\d\d$', w[0]): day = w[0]; ts, w = w[0] + ' ' + w[1], w[2:]
            elif len(w) >= 3 and re.match(r'\d\d:\d\d:\d\d$', w[0]):
                d0 = day
                if d0 is None and first_dated:
                    t1 = time.mktime(time.strptime(first_dated[0], '%Y-%m-%d'))
                    d0 = first_dated[0] if w[0] <= first_dated[1] else time.strftime('%Y-%m-%d', time.localtime(t1 - 86400 + 3600))
                if d0 is None:
                    d0 = time.strftime('%Y-%m-%d', time.localtime(mt))
                    if w[0] > time.strftime('%H:%M:%S', time.localtime(mt)):
                        d0 = time.strftime('%Y-%m-%d', time.localtime(mt - 86400))
                ts, w = d0 + ' ' + w[0], w[1:]
            else: continue
            if not re.match(r'\d+$', w[1]): continue
            try: t = time.mktime(time.strptime(ts, '%Y-%m-%d %H:%M:%S'))
            except ValueError: continue
            if w[0] not in first or t < first[w[0]]: first[w[0]] = t
    return first


def speed(per, shards, meas):
    out = {}; note = {}
    by = {}
    # 10/15 19:4x 別のAIの指摘：per_full の更新時刻だと書き直した本が短く見えて落ちる（M-fTbhTZJJY の 508秒）
    #   → progress の最初に書き終えた時刻で並べる。progress に行が無い本は今までどおり更新時刻
    pt = progress_times()
    for vid, (d, mt) in per.items():
        if vid in shards: by.setdefault(shards[vid]['shard'], []).append((pt.get(vid, mt), vid))
    for n, lst in by.items():
        lst.sort()
        for (m0, v0), (m1, v1) in zip(lst, lst[1:]):
            dur = (meas.get(v1) or {}).get('probe', {}).get('duration') or per[v1][0].get('duration_s') or 0
            spent = m1 - m0
            note[v1] = spent
            if dur and spent < LINE['SPEED_MIN_RATIO'] * dur:
                out[v1] = ['1本に %.0f秒（動画は %.0f秒・前の本 %s の %s から）速すぎ' % (spent, dur, v0, time.strftime('%H:%M:%S', time.localtime(m0)))]
    return out, note


# ---------- sozai2 ----------
SRC_RE = re.compile(r'([A-Za-z0-9_-]{11})\D{1,3}(\d+(?:\.\d+)?)')


def check_sozai(shards, rnd):
    r = {'fails': [], 'notes': [], 'rows': []}
    idx = os.path.join(SOZAI, 'index.tsv')
    files = [p for sub in ('se', 'bgm', 'e', 'kokuchi') for p in glob.glob(os.path.join(SOZAI, sub, '**', '*'), recursive=True) if os.path.isfile(p)]
    r['notes'].append('実ファイル se %d・bgm %d・e %d・kokuchi %d' % tuple(sum(1 for p in files if os.sep + sub + os.sep in p) for sub in ('se', 'bgm', 'e', 'kokuchi')))
    if not os.path.exists(idx):
        r['notes'].append('index.tsv はまだ無い（作業中）'); return r
    lines = [l.rstrip('\n').split('\t') for l in open(idx, encoding='utf-8') if l.strip()]
    head = [h.strip().lower() for h in lines[0]]; rows = lines[1:]
    fc = next((i for i, h in enumerate(head) if h in ('file', 'path', 'ファイル', 'filename')), None)
    if fc is None:
        r['fails'].append('index.tsv に file 列が無い（列 %s）' % head); return r
    listed = set()
    missing = []
    for row in rows:
        if fc >= len(row): continue
        p = os.path.normpath(os.path.join(SOZAI, row[fc]))
        listed.add(p)
        if not os.path.exists(p): missing.append(row[fc])
    extra = [p for p in files if os.path.normpath(p) not in listed and not p.endswith(('.png.json', '.txt', '.md'))]
    r['notes'].append('index %d 行・実ファイル %d・index にあって無い %d・index に無いファイル %d' % (len(rows), len(files), len(missing), len(extra)))
    if missing: r['fails'].append('index にあるのにファイルが無い %d（例 %s）' % (len(missing), ', '.join(missing[:3])))
    if len(extra) > 0.05 * max(1, len(files)): r['fails'].append('index に載っていないファイル %d（例 %s）' % (len(extra), ', '.join(os.path.relpath(p, SOZAI) for p in extra[:3])))
    # 効果音の出どころを抜き取り
    se = []
    for row in rows:
        if fc >= len(row) or not row[fc].startswith('se'): continue
        m = None
        for i, h in enumerate(head):
            if i < len(row) and any(k in h for k in ('src', 'source', '出どころ', 'from', 'origin')):
                m = SRC_RE.search(row[i])
                if m: break
        if m and m.group(1) in shards: se.append((row[fc], m.group(1), float(m.group(2))))
    if not se:
        if any(r_[fc].startswith('se') for r_ in rows if fc < len(r_)):
            r['fails'].append('効果音に出どころ（元動画のid と秒）が読めない（src 列に「<id> 12.34」の形が要る）')
        return r
    bad = 0
    for f, vid, t in rnd.sample(se, min(5, len(se))):
        clip = S.audio(os.path.join(SOZAI, f))[:16000 * 1]
        seg = S.audio(shards[vid]['mp4'], t - 0.5, 0.5 + len(clip) / 16000 + 0.5)
        ctl = S.audio(shards[vid]['mp4'], t + 5 - 0.5, 0.5 + len(clip) / 16000 + 0.5)
        c, at = S.spec_match(clip, seg); c2, _ = S.spec_match(clip, ctl)
        ok = c >= LINE['SE_CORR_MIN'] and c - c2 >= LINE['SE_MARGIN_MIN']
        bad += not ok
        r['rows'].append((f, vid, t, round(c, 2), round(c2, 2), round(at - 0.5, 2), ok))
    if bad >= 2:
        r['fails'].append('効果音の出どころ 抜き取り %d 本中 %d 本でその秒の音と合わない' % (len(r['rows']), bad))
    return r


# ---------- 本体 ----------
def main():
    a = sys.argv[1:]
    only = a[a.index('--id') + 1] if '--id' in a else None
    budget = float(a[a.index('--budget') + 1]) if '--budget' in a else 1500
    os.makedirs(ME, exist_ok=True)
    if '--count' in a:   # 合格の数だけ（--id の回のあとに自動で走る）
        i = a.index('--count')
        count_main(a[i + 1] if i + 1 < len(a) else '--count'); return
    try:
        os.nice(max(0, 15 - os.nice(0)))   # 重い測り（全コマ・元の大きさ）は nice 15
    except OSError:
        pass
    # --id のときは本ごとの札＋同時3本までの枠（10/17 02:4x：全体で1本ずつだと書き手9人が門の前で順番待ちになり、10/18夜に間に合わない）
    # --id の回は判定を本ごとのファイルにだけ書き、まとめ・やり直し一覧は書かない（下の if only で返す）ので、別の本となら同時に走れる
    if only:
        lk = open(os.path.join(ME, '.lock-%s' % only), 'w')
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print('同じ本の前の回が走っています'); return
        slot = None
        while slot is None:
            for i in range(3):
                f = open(os.path.join(ME, '.slot-%d' % i), 'w')
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB); slot = f; break
                except OSError:
                    f.close()
            if slot is None:
                time.sleep(20)
    else:
        lk = open(os.path.join(ME, '.lock'), 'w')
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            print('前の回が走っています'); return
    t_start = time.time()
    shards = load_shards()
    per = load_per()
    targets = [only] if only else sorted(per, key=lambda v: per[v][1])
    # 書き手の会話記録を前回の続きから読む（画像の Read の結果が request limit で出なかった回を拾う）
    mienai_err = mienai_scan()
    kotoba_rows = KOTOBA.rows()
    meas, verd = {}, {}
    pending, running = [], []
    for vid in targets:
        if vid not in shards:
            verd[vid] = {'fails': ['担当表（shard）に無い id'], 'notes': []}; continue
        d, mt = per[vid]
        if d.get('_broken'):
            verd[vid] = {'fails': ['per_full が JSON として読めない'], 'notes': []}; continue
        vp = os.path.join(VERD, vid + '.json')
        key = verd_key(vid, mt)
        if not only and held(vid):
            # --id の回がいまこの本を測っている → 同じコマを二重に読まない（10/17 23:1x：まとめの回と --id の回が同じ本の同じ札を同時に読んでいた）
            # その回が書いた判定が今の per_full のものなら使う。まだなら次の回で数える。ここでは書かない（その回が書く新しい判定を古いもので上書きしうる）
            v = jload(vp)
            if not v or v.get('key') != key:
                running.append(vid); continue
            nf, nn = gates(vid, v, mt, mienai_err, kotoba_rows)
            verd[vid] = dict(v, fails=nf, notes=nn); continue
        cache_ok = os.path.exists(os.path.join(CACHE, vid + '.json'))
        if not cache_ok and time.time() - t_start > budget:
            pending.append(vid); continue
        meas[vid] = measure(vid, shards[vid]['mp4'])
        v = jload(vp)
        if not v or v.get('key') != key:
            f1, n1 = judge(vid, shards[vid], d, meas[vid])
            f3, sp = spot(vid, shards[vid], d, key)
            f4, ss = sheet_spot(vid, shards[vid], d, meas[vid], key)
            n1 = n1 + ['全シートの抜き取り（%s）：前 %d/%d・中 %d/%d・後ろ %d/%d が合った' % ((ss['how'],) + tuple(x for p in ss['by_part'] for x in p))]
            v = {'key': key, 'fails': f1 + f3 + f4, 'notes': n1, 'spot': sp, 'sheet_spot': ss, 'at': datetime.datetime.now().isoformat(timespec='seconds')}
            jsave(vp, v)
        # 画像が出なかったシートを読み直していない本は不合格（per_full が同じでも記録は動くので、毎回入れ替える）
        nf, nn = gates(vid, v, mt, mienai_err, kotoba_rows)
        if nf != v['fails'] or nn != v.get('notes'):
            v['fails'] = nf; v['notes'] = nn; jsave(vp, v)
        verd[vid] = v
    # 測り終えた本も 全部の本の cache を読む（速さの判定に長さが要る）
    load_meas(per, meas)
    if not only:
        add_cross_speed(verd, per, shards, meas)
    soz = check_sozai(shards, random.Random(datetime.date.today().isoformat())) if not only else None
    report(shards, per, verd, pending + running, meas, soz, only, time.time() - t_start, running)
    if only:
        # 合格の数をまとめの回を待たずに出す（書き手を待たせないよう別の回で・札と枠は先に返す）
        slot.close(); lk.close()
        import subprocess
        subprocess.Popen([sys.executable, os.path.abspath(__file__), '--count', 'id:%s' % only], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=open(COUNT_LOG, 'a'), start_new_session=True)
    else:
        count_main('まとめの回のあと')


def load_per():
    per = {}
    for p in glob.glob(os.path.join(PER, '*.json')):
        vid = os.path.basename(p)[:-5]
        d = jload(p)
        per[vid] = (d if isinstance(d, dict) else {'_broken': True}, os.path.getmtime(p))
    return per


def load_meas(per, meas):
    for vid in per:
        if vid not in meas and os.path.exists(os.path.join(CACHE, vid + '.json')): meas[vid] = jload(os.path.join(CACHE, vid + '.json'))
    return meas


def verd_key(vid, mt):
    return '%s:%d:%s' % (vid, int(mt), json.dumps(LINE, sort_keys=True))


def mienai_scan():
    try:
        MIENAI.scan(); return None
    except Exception as e:
        return '%s の検査が動かなかった（%s）。直して通し直す' % (MIENAI.FAIL_HEAD, e)


def gates(vid, v, mt, mienai_err, kotoba_rows):
    """画像が出なかった門・見た印の門を、いまの記録で入れ替えた (fails, notes)"""
    mf = mienai_err or MIENAI.gate_fail(vid, do_scan=False)
    kf, kn = KOTOBA.gate(vid, kotoba_rows, mt)
    nf = [f for f in v['fails'] if not f.startswith((MIENAI.FAIL_HEAD, KOTOBA.FAIL_HEAD))] + ([mf] if mf else []) + ([kf] if kf else [])
    nn = [n for n in v.get('notes', []) if not n.startswith('見た印')] + [kn]
    return nf, nn


def held(vid):
    """--id の回がその本の札（.lock-<id>）を持っているか"""
    p = os.path.join(ME, '.lock-%s' % vid)
    if not os.path.exists(p): return False
    with open(p, 'a') as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return True
        fcntl.flock(f, fcntl.LOCK_UN)
    return False


def add_cross_speed(verd, per, shards, meas):
    good = {v: per[v] for v in per if not per[v][0].get('_broken')}
    for vid, f in cross(good).items():
        verd.setdefault(vid, {'fails': [], 'notes': []})['fails'] = verd[vid]['fails'] + f
    sp_fail, sp_note = speed(good, shards, meas)
    for vid, f in sp_fail.items():
        verd.setdefault(vid, {'fails': [], 'notes': []})['fails'] = verd[vid]['fails'] + f


def counts(shards, per, verd, pending):
    """まとめの表の数（報告の「計」の行と goukaku-count.json は、この1つの式から出す）。合格＝fails が空"""
    bad = {v for v, x in verd.items() if x['fails']}
    ok = {v for v, x in verd.items() if not x['fails']}
    rows = []
    for n in range(8):
        ids = [v for v, i in shards.items() if i['shard'] == n]
        got = [v for v in ids if v in per]
        rows.append((n, len(ids), len(got), sum(1 for v in got if v in ok), sum(1 for v in got if v in bad), sum(1 for v in got if v in pending)))
    return {'rows': rows, 'kei': (len(shards), len(per), len(ok), len(bad), len(pending))}


# ---------- 合格の数（まとめの回を待たずに） ----------
COUNT = os.path.join(ME, 'goukaku-count.json')
COUNT_LOG = '~/rin6/logs/yt-saboranai-count.log'


def count_now(src):
    """verdict/ にある「いまの per_full の判定」を、まとめの回と同じ式（門2つの入れ替え・本どうし・速さ・counts）で数える。
    判定がまだ無い本（per_full が新しくなった本を含む）は測定待ち。verdict/ には書かない（走っている --id の回の判定を上書きしないため）"""
    shards = load_shards(); per = load_per()
    mienai_err = mienai_scan(); kotoba_rows = KOTOBA.rows()
    verd, pending = {}, []
    for vid in sorted(per, key=lambda v: per[v][1]):
        if vid not in shards:
            verd[vid] = {'fails': ['担当表（shard）に無い id'], 'notes': []}; continue
        d, mt = per[vid]
        if d.get('_broken'):
            verd[vid] = {'fails': ['per_full が JSON として読めない'], 'notes': []}; continue
        v = jload(os.path.join(VERD, vid + '.json'))
        if not v or v.get('key') != verd_key(vid, mt):
            pending.append(vid); continue
        nf, nn = gates(vid, v, mt, mienai_err, kotoba_rows)
        verd[vid] = dict(v, fails=nf, notes=nn)
    add_cross_speed(verd, per, shards, load_meas(per, {}))
    c = counts(shards, per, verd, pending)
    zen, tsu, ok, ng, machi = c['kei']
    out = {'at': datetime.datetime.now().isoformat(timespec='seconds'), 'goukaku': ok, 'fugoukaku': ng, 'machi': machi, 'tsuita': tsu, 'zenbu': zen,
           'shard': {'shard%d' % r[0]: dict(zip(('zenbu', 'tsuita', 'goukaku', 'fugoukaku', 'machi'), r[1:])) for r in c['rows']},
           'from': src, 'shiki': 'saboranai.py counts()。まとめの報告 saboranai-*.md の「計」の行と同じ式（合格＝fails が空・本どうしと速さも入れる）。判定がまだ無い本は machi'}
    tmp = '%s.%d.tmp' % (COUNT, os.getpid())
    json.dump(out, open(tmp, 'w'), ensure_ascii=False, indent=1); os.replace(tmp, COUNT)
    return out


def count_main(src):
    """数えるのは同時に1つ。走っている間に頼まれたら、終わってからもう1回（その間に出た判定も入れる）"""
    again = os.path.join(ME, '.count-again')
    while True:
        lk = open(os.path.join(ME, '.lock-count'), 'w')
        try:
            fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            open(again, 'w').close(); return
        try:
            while True:
                try: os.remove(again)
                except FileNotFoundError: pass
                print(json.dumps(count_now(src), ensure_ascii=False))
                if not os.path.exists(again): break
        finally:
            lk.close()
        if not os.path.exists(again): return


def report(shards, per, verd, pending, meas, soz, only, took, running=()):
    now = datetime.datetime.now()
    bad = {v: x for v, x in verd.items() if x['fails']}
    ok = [v for v, x in verd.items() if not x['fails']]
    L = ['# サボらない門 %s' % now.strftime('%Y-%m-%d %H:%M'), '',
         '作業者の申告（per_full）を、元動画から独立に測った数字と突き合わせた結果。測るのにかかった時間 %.0f秒。' % took, '']
    L += ['## まとめ', '', '| 担当 | 全本 | 着いた | 合格 | 不合格 | 測定待ち |', '|---|---|---|---|---|---|']
    c = counts(shards, per, verd, pending)
    for r in c['rows']:
        L.append('| shard%d | %d | %d | %d | %d | %d |' % r)
    L.append('| 計 | %d | %d | %d | %d | %d |' % c['kei'])
    tomari = []
    for n in range(8):
        pg = os.path.join(FULL, 'progress-%d.txt' % n)
        if os.path.exists(pg):
            last = (open(pg).read().strip().splitlines() or [''])[-1]
            L.append('- shard%d の最後の進み：%s（%.0f分前）' % (n, last, (time.time() - os.path.getmtime(pg)) / 60))
            # 10/17 18:4x 書き手は2人だけ（別の作業AI案）。止めている shard は止まりに数えない
            if glob.glob('~/rin6/state/workers/prompts-paused-*/yt-full-%dd.json' % n): continue
            if (time.time() - os.path.getmtime(pg)) > 90 * 60:
                tomari.append('shard%d（%.0f分）' % (n, (time.time() - os.path.getmtime(pg)) / 60))
    # 書き手が90分進まない＝作業員が消えた疑い（10/16 全員が2〜8時間止まっていたのに誰も気づかなかった）→ 作業AIを起こす（2時間に1回まで）
    if tomari:
        st = os.path.join(FULL, 'saboranai', 'tomari-wake.txt')
        if not os.path.exists(st) or time.time() - os.path.getmtime(st) > 120 * 60:
            open(st, 'w').write(' '.join(tomari))
            import subprocess
            subprocess.run(['~/rin/scripts/wake-rin.sh', '[YouTube止まり] 書き手が90分以上進んでいません：%s。ListAgents で yt-full-*d が生きているか見て、いなければ state/workers/MANIFEST.md どおりすぐ出し直す' % '・'.join(tomari), 'rin6'], check=False)
    L += ['', '## やり直し（不合格）', '']
    if not bad: L.append('なし')
    for v, x in sorted(bad.items(), key=lambda z: (shards.get(z[0], {}).get('shard', 9), z[0])):
        L.append('### %s（shard%s）' % (v, shards.get(v, {}).get('shard', '?')))
        L += ['- ' + f for f in x['fails']]
        L += ['- 測った数：' + n for n in x.get('notes', [])]
        L.append('')
    L += ['## 合格', '']
    for v in sorted(ok):
        x = verd[v]
        L.append('- %s：%s' % (v, '；'.join(x.get('notes', []))))
        rows = (x.get('spot') or {}).get('rows', [])
        if rows:
            L.append('  - 抜き取り %d 場面：色 %d/%d 一致・文字 %s' % (len(rows), sum(c[1] for r in rows for c in r['colors']), sum(len(r['colors']) for r in rows),
                     ' '.join('%.1f秒=%s' % (r['t0'], '-' if r['text_hit'] is None else '%.0f%%' % (100 * r['text_hit'])) for r in rows)))
    wait = [v for v in pending if v not in running]
    if wait:
        L += ['', '## 測定待ち（全コマの差をまだ数えていない・次の回）', '', ' '.join(wait)]
    if running:
        L += ['', '## 測り中（--id の回がこの本を測っている・判定はその回が書く・次の回で数える）', '', ' '.join(running)]
    if soz:
        L += ['', '## 素材（sozai2）', '']
        L += ['- ' + n for n in soz['notes']]
        L += ['- 不合格：' + f for f in soz['fails']]
        for f, vid, t, c, c2, off, okk in soz['rows']:
            L.append('- 抜き取り %s ← %s %.2f秒：相関 %.2f（5秒ずらし %.2f・ずれ %+.2f秒）%s' % (f, vid, t, c, c2, off, '合' if okk else '外れ'))
    L += ['', '## 測り方と線', '', '- 全コマの差：%s' % json.dumps(S.THRESHOLDS, ensure_ascii=False), '- 追記3の見方：%s' % json.dumps(S.BLK_TH, ensure_ascii=False), '- 合格の線：%s' % json.dumps(LINE, ensure_ascii=False),
          '- 抜き取りは per_full の更新ごとに無作為で選び直す（同じ版なら同じ場面）。色は CIE76 ΔE、文字は macOS Vision で 1920x1080 のコマを読む']
    if only:
        print('\n'.join(L)); return
    out = os.path.join(FULL, 'saboranai-%s.md' % now.strftime('%Y%m%d-%H%M'))
    open(out, 'w').write('\n'.join(L) + '\n')
    ya = ['%s\t%s\t%s' % (v, shards.get(v, {}).get('shard', '?'), '；'.join(x['fails'])) for v, x in sorted(bad.items())]
    if soz and soz['fails']: ya.append('sozai2\t-\t%s' % '；'.join(soz['fails']))
    tmp = os.path.join(FULL, 'yarinaoshi.txt.tmp'); open(tmp, 'w').write('\n'.join(ya) + ('\n' if ya else '')); os.replace(tmp, os.path.join(FULL, 'yarinaoshi.txt'))
    print(out)
    # 不合格があれば作業AIの知らせへ 1行（同じ顔ぶれなら 1時間に1回）
    st = jload(STATE, {})
    sig = ','.join(sorted(bad)) + ('|sozai' if soz and soz['fails'] else '')
    if ya and (sig != st.get('sig') or time.time() - st.get('at', 0) >= 3600):
        msg = ('【サボらない門・自動】YouTube型の全編データ化：不合格 %d 本（合格 %d・着いた %d/%d）%s。やり直し一覧 %s／報告 %s。'
               '作業者にやり直しを出す（一覧の id を shard の担当へ）。'
               % (len(bad), len(ok), len(per), len(shards), '・素材にも不合格' if soz and soz['fails'] else '', os.path.join(FULL, 'yarinaoshi.txt'), out))
        with open(ALERT, 'a') as a:
            a.write(json.dumps({'at': now.isoformat(timespec='seconds'), 'from': 'saboranai', 'text': msg}, ensure_ascii=False) + '\n')
        st = {'sig': sig, 'at': time.time()}
        jsave(STATE, st)


if __name__ == '__main__':
    main()
