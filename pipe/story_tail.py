
# ===== 終わり（pipe/story_tail.py）=====
CH = ''
finish(END)
# 出方の配分（v13・手本の作者さん15本対v12の比べ 10/19）：場面に最初に出る部品の出方を、ポップ（pop・bounce・stamp）30%以下・
#   1字ずつ（type）15%以上・ぼけから（blur）15%以上・同じ出方が続くのは6回まで、に寄せる。AI の節が外れたときだけ直し、直した数を残す
_POPS = ('pop', 'bounce', 'stamp'); _CLS = lambda a: 'pop' if a in _POPS else ('slide' if a in ('left', 'right', 'slidel', 'up') else ('wipe' if a in ('wipe', 'xdraw') else a))
_TYPE_OK = ('midashi', 'oaka', 'ao', 'kin_l', 'kin', 'obi_aka', 'aka_box', 'kon', 'card_hai', 'card_ao', 'card_kuro', 'check', 'tag', 'kazu')
def _txt(e):
    inf = getattr(e._src, 'info', None) or {}
    return re.sub(r'<[^>]+>|\s', '', inf.get('pipe_text', '') or ''), inf
def _can_type(e):
    tx, inf = _txt(e)
    return bool(tx) and 2 <= len(tx) <= 12 and '\n' not in (inf.get('pipe_text') or '') and e._src.width < W - 40 and e.anim != 'type'
def _set(e, a):
    e.anim = a
    if a == 'type': e.nchar = max(1, len(_txt(e)[0])); e.dur = min(0.6, max(0.3, 0.06 * e.nchar))
    elif a == 'blur': e.dur = 0.3
def _firsts():
    g = {}
    for e in ELEMS:
        if e.anim == 'none': continue
        k = round(getattr(e, 't_plan', e.ts), 3)
        if k not in g: g[k] = e
    return [g[k] for k in sorted(g)]
def _share(F):
    c = _co.Counter(_CLS(e.anim) for e in F); n = max(1, len(F)); return {k: v / n for k, v in c.items()}, c
import collections as _co
_F = _firsts(); _before = dict(_share(_F)[1]); _changed = []
# v14（依頼主 10/19 19:12「バリエーションを最大に」）：ポップ 20%以下・1字ずつ 12%以上・ぼけから 12%以上（v13 の 30/15/15 から、新しい出方が入る分をあけた）
_P_HI, _T_LO, _B_LO = 0.20, 0.12, 0.12
_EDL = bool(os.environ.get('PIPE_EDL'))   # v14：編集の指示書（EDL）で組んだときは、出方・効果音を道具で選び直さない（依頼主 10/19 19:25「決まりで機械的に決めない」）
_pop = [] if _EDL else [e for e in _F if e.anim in _POPS]
_pop.sort(key=lambda e: (e.anim != 'pop', 0))   # まず pop から。bounce・stamp（強い言い切り）は最後に回す
for e in _pop:
    sh, _c = _share(_F)
    if sh.get('pop', 0) <= _P_HI - 0.03 and sh.get('type', 0) >= _T_LO + 0.02 and sh.get('blur', 0) >= _B_LO + 0.02: break
    if sh.get('pop', 0) <= _P_HI - 0.03 and e.anim != 'pop': continue
    old = e.anim
    if sh.get('type', 0) < _T_LO + 0.02 and _can_type(e): _set(e, 'type')
    elif sh.get('blur', 0) < _B_LO + 0.02 or sh.get('pop', 0) > _P_HI - 0.03: _set(e, 'type' if (_can_type(e) and sh.get('type', 0) < sh.get('blur', 0)) else 'blur')
    if e.anim != old: _changed.append((round(e.t_plan, 2), old, e.anim))
for e in ([] if _EDL else _F):
    sh, _c = _share(_F)
    if sh.get('type', 0) >= _T_LO + 0.02: break
    if e.anim in ('left', 'right', 'wipe', 'up') and _can_type(e):
        old = e.anim; _set(e, 'type'); _changed.append((round(e.t_plan, 2), old, 'type'))
# 同じ表現の型が3回以上続く所を切る（2回まで）。型＝動く図解はその図解の型、ほかは出方の型（pipe/zukai.py の ANIM_KATA）
#   動く図解（grow）・矢印の伸び（nobi）・描き出し（egaku）・×（xdraw）は中身に合わせた出方なので替えない。替えるのは字・絵の出方だけ
_FIXED = ('grow', 'nobi', 'egaku', 'xdraw')
def _kata(e):
    inf = getattr(e._src, 'info', None) or {}
    if e.anim == 'grow' and inf.get('pipe_zukai'): return inf['pipe_zukai']
    return ANIM_KATA.get(e.anim, e.anim)
_POOL_TXT = ['type', 'blur', 'left', 'right', 'up', 'kira', 'zoom', 'drop', 'tenmetsu', 'hekomu', 'glitch', 'stamp', 'wipe', 'kaiten', 'yure']
_POOL_IMG = ['blur', 'bounce', 'left', 'right', 'up', 'drop', 'kaiten', 'zoom', 'egaku', 'tenmetsu', 'hekomu', 'yure', 'glitch']
def _ok(e, a):
    tx, inf = _txt(e)
    if a == 'type': return _can_type(e)
    if a in ('kaiten', 'yure'): return e._src.width < 900 and e._src.height < 600   # 大きい帯は回すと画面の外に出る
    if a == 'wipe': return bool(tx)
    if a == 'egaku': return not tx
    return True
_use = _co.Counter(_kata(e) for e in _F)
for i, e in enumerate([] if _EDL else _F):
    if i < 2 or e.anim in _FIXED: continue
    k = _kata(e)
    if not (_kata(_F[i - 1]) == k and _kata(_F[i - 2]) == k): continue
    nxt = _kata(_F[i + 1]) if i + 1 < len(_F) else None
    pool = _POOL_TXT if _txt(e)[0] else _POOL_IMG
    cand = [a for a in pool if _ok(e, a) and ANIM_KATA.get(a, a) not in (k, nxt)]
    if not cand: continue
    new = min(cand, key=lambda a: (_use[ANIM_KATA.get(a, a)], pool.index(a)))
    old = e.anim; _set(e, new); e.dur = _ZDUR.get(new, e.dur) if new in _ZDUR else e.dur
    _use[k] -= 1; _use[ANIM_KATA.get(new, new)] += 1; _changed.append((round(e.t_plan, 2), old, new))
_run = _best = 0; _pk = None
for e in _F:
    k = _kata(e); _run = _run + 1 if k == _pk else 1; _pk = k; _best = max(_best, _run)
_after = dict(_share(_F)[1])
# 軽い効果音（pon・fukidashi・kira_hi・telop）は2つに1つだけ鳴らす（v12 と同じ・鳴りすぎない）
_light_n = 0; _keep = []
for _t, _k in SFX:
    if _k in ('pon', 'fukidashi', 'kira_hi', 'telop') and not _EDL:
        _light_n += 1
        if _light_n % 2 == 0: continue
    _keep.append((_t, _k))
SFX[:] = _keep
import json as _j
_zims = os.path.join(PROJ, 'work', 'zure-ims'); os.makedirs(_zims, exist_ok=True); _zel = []
for _e in ELEMS:   # ルール5を「その字・部品そのものが出た瞬間」で測るため、部品の絵を 1/4 で残す（zure-kensa.py が絵と画面を突き合わせる・10/19 21:1x）
    if _e.anim == 'none' or (getattr(_e._src, 'info', None) or {}).get('pipe_kasane'): continue
    _zp = os.path.join(_zims, '%03d.png' % len(_zel))
    try: _e._src.convert('RGBA').resize((max(1, _e._src.width // 4), max(1, _e._src.height // 4))).save(_zp)
    except Exception: _zp = None
    _zel.append({'t': round(getattr(_e, 't_plan', 0), 4), 'x': _e.x, 'y': _e.y, 'anchor': _e.anchor, 'w': _e._src.width, 'h': _e._src.height, 'anim': _e.anim, 'img': _zp, 'kind': getattr(_e, 'kind_', ''), 'idle': bool(getattr(_e, 'idle', None) or getattr(_e, 'frames', None) or getattr(_e, 'moves', None))})
_j.dump({'ev': ON.EV, 'elems': _zel, 'kasane_nozoku': sum(1 for e in ELEMS if e.anim != 'none' and (getattr(e._src, 'info', None) or {}).get('pipe_kasane'))}, open(os.path.join(PROJ, 'work', 'zure-plan.json'), 'w'), ensure_ascii=False)   # v14：丸で囲む・下線（前の字に重ねる飾り）は、下の字の動きと同じ範囲なので測りから外し、数だけ残す
_j.dump(USED, open(os.path.join(PROJ, 'work', 'sozai_used.json'), 'w'), ensure_ascii=False)
_j.dump({'dekata_mae': _before, 'dekata_ato': _after, 'naoshita': _changed, 'kirikae': TRLOG, 'katalog': [dict(x, anim_ato=next((e.anim for e in ELEMS if abs(getattr(e, 't_plan', -9) - x['t']) < 0.0005 and (getattr(e._src, 'info', None) or {}).get('pipe_fn', '') == x['fn']), x['anim'])) for x in KATALOG], 'kata_saichou_renzoku': _best, 'firsts': [{'t': round(e.t_plan, 3), 'kata': _kata(e), 'anim': e.anim, 'ch': getattr(e, 'pipe_ch', '')} for e in _F]}, open(os.path.join(PROJ, 'work', 'kata_v13.json'), 'w'), ensure_ascii=False, indent=1)
import ki1 as _k1
_k1.JIMAKU[:] = _k1.build_jimaku(os.path.join(PROJ, 'work', 'timing_fa.json'), END)
# BGM（依頼主 10/19 03:3x「bgmはいれといて」・手本の作者さんの動画の BGM＝sozai/bgm・出どころは sozai/bgm/index.tsv）
#   本編は honpen_gray（11.5秒から・声の帯が目立つ頭を避ける）と honpen_gray_b を交互に1秒重ねてつなぐ。
#   告知・CTA（締め）の章からは Afterglow（Audiostock 1065397・定額制スタンダード・曲の頭1.4秒の無音を飛ばす）。作業AI 10/20 23:4x「締めのBGMの既定をAfterglowに」。前の kokuchi に戻すときは BGM_SHIME=kokuchi
_BG = float(os.environ.get('BGM_DB', '-21.5'))
def _bgm_plan(t0, t1):
    out, t, k = [], t0, 0
    while t1 - t0 > 0.5:
        f, off, L_ = (('bgm/honpen_gray.wav', 11.5, 104.0) if k % 2 == 0 else ('bgm/honpen_gray_b.wav', 0.0, 40.0))
        e = min(t1, t + L_); out.append((t, e, f, off, _BG))
        if e >= t1: return out
        t, k = e - 1.0, k + 1
    return out
if KOKUCHI_FROM and 30 < KOKUCHI_FROM < END - 10:
    BGM = _bgm_plan(0.0, KOKUCHI_FROM + 0.5)
    _t = KOKUCHI_FROM - 0.5
    _SH = ('bgm/kokuchi.wav', 0.0, 124.0) if os.environ.get('BGM_SHIME') == 'kokuchi' else ('bgm/afterglow.wav', 1.4, 130.0)   # kokuchi.wav 125.6秒／afterglow.wav 132.7秒（1.4秒から）
    while _t < END - 0.5:   # 長い告知は1秒重ねてつなぐ
        _e = min(END, _t + _SH[2]); BGM.append((_t, _e, _SH[0], _SH[1], _BG)); _t = _e - 1.0
        if _e >= END: break
else:
    BGM = _bgm_plan(0.0, END)
if globals().get('BGM_EDL'): BGM = BGM_EDL   # v14：指示書に書いた BGM をそのまま
SFX_SPARSE = []
if __name__ == '__main__':
    dump_meta(PROJ, END, BGM, SFX_SPARSE); print(len(SCENES), 'scenes', len(SFX), 'sfx', len([e for e in ELEMS if e.anim != 'none']), 'moving', 'END %.2f' % END)
