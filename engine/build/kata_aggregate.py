#!/usr/bin/env python3
# 型のデータをまとめる：kata/raw/*/data.json（機械で測った全本）＋ kata/per/*.json（詳しく見た本）＋ kata/lite/*.json（かんたん版）
#   python3 build/kata_aggregate.py  → kata/kata.json（KATA.md の数字の元）
import os, json, glob, statistics as st, collections
HERE = os.path.dirname(os.path.abspath(__file__)); BASE = os.path.dirname(HERE); K = os.path.join(BASE, 'kata')

def sfx_n(w):
    return sum(1 for p in w['onsets'] if p.get('guess') and not p.get('on_beat') and p.get('over_local_db', 0) >= 10)

def med(xs):
    xs = [x for x in xs if x is not None]
    return round(st.median(xs), 1) if xs else None

def q(xs, a):
    xs = sorted(x for x in xs if x is not None)
    return round(xs[int(len(xs) * a)], 1) if xs else None

raw = []
for f in sorted(glob.glob(os.path.join(K, 'raw', '*', 'data.json'))):
    d = json.load(open(f)); row = {'id': d['id'], 'channel': d['channel'], 'dur': d['duration']}
    for w in d['windows']:
        L = (w['t1'] - w['t0']) / 60
        sc = sum(1 for e in w['changes'] if e['kind'] == 'scene')
        row[w['name']] = {'changes_pm': round(len(w['changes']) / L, 1), 'scenes_pm': round(sc / L, 1), 'sfx_pm': round(sfx_n(w) / L, 1),
                          'voice_minus_bg': w['bgm'].get('voice_minus_bg_db'), 'bgm_beat': bool(w.get('bgm_beat')),
                          'sfx_on_change': round(sum(1 for p in w['onsets'] if p.get('guess') and not p.get('on_beat') and p.get('over_local_db', 0) >= 10 and p.get('near_change')) / max(1, sfx_n(w)), 2)}
    raw.append(row)

def summarize(rows, key):
    out = {}
    for wn in ('hook', 'mid', 'end', 'all'):
        rs = [r[wn] for r in rows if wn in r]
        if not rs: continue
        out[wn] = {k: {'median': med([r[k] for r in rs]), 'p25': q([r[k] for r in rs], 0.25), 'p75': q([r[k] for r in rs], 0.75)}
                   for k in ('changes_pm', 'scenes_pm', 'sfx_pm', 'voice_minus_bg', 'sfx_on_change')}
        vb = [r['voice_minus_bg'] for r in rs if r['voice_minus_bg'] is not None]
        out[wn]['bgm_audible_share'] = round(sum(1 for x in vb if x < 30) / max(1, len(vb)), 2)  # 声との差が 30dB 未満＝BGMが聞こえる
        out[wn]['n'] = len(rs)
    return out

by_ch = collections.defaultdict(list)
for r in raw: by_ch[r['channel']].append(r)
agg = {'n_videos': len(raw), 'all': summarize(raw, 'all'), 'by_channel': {c: summarize(rs, c) for c, rs in sorted(by_ch.items())}}

# 詳しく見た本：場面の役割 → 編集の手（座布団・音）の数え上げ
per = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(K, 'per', '*.json')))]
role_rows = collections.defaultdict(list)
for d in per:
    for s in d.get('scenes', []):
        r = (s.get('role') or '').split('・')[0].split('（')[0].strip()
        if not r: continue
        tel = s.get('telop') or {}
        role_rows[r].append({'id': d['id'], 't': s.get('t0'), 'zabuton': (tel.get('zabuton') if isinstance(tel, dict) else None),
                             'emphasis': (tel.get('emphasis') if isinstance(tel, dict) else None),
                             'sfx': [x.get('kind') for x in (s.get('sfx') or []) if isinstance(x, dict)], 'anim': s.get('anim'), 'intent': s.get('intent')})
agg['roles'] = {r: {'n': len(v), 'examples': v[:6]} for r, v in sorted(role_rows.items(), key=lambda x: -len(x[1])) if len(v) >= 3}
agg['families'] = collections.Counter(d.get('family', '').split('（')[0][:40] for d in per).most_common()
agg['rules'] = {d['id']: d.get('rules', []) for d in per}
lite = [json.load(open(f)) for f in sorted(glob.glob(os.path.join(K, 'lite', '*.json')))]
if lite:
    agg['lite_n'] = len(lite)
    agg['lite_families'] = collections.Counter((d.get('family') or '')[:40] for d in lite).most_common(30)
    dev = collections.Counter(x for d in lite for x in ((d.get('hook') or {}).get('devices') or []))
    agg['lite_hook_devices'] = dev.most_common(30)
    agg['lite_end_types'] = collections.Counter(((d.get('end') or {}).get('type') or '')[:30] for d in lite).most_common(20)
    agg['lite_promo_in_hook'] = sum(1 for d in lite if (d.get('hook') or {}).get('promo_in_hook') not in (None, '', 'なし', 'ない'))
json.dump(agg, open(os.path.join(K, 'kata_stats.json'), 'w'), ensure_ascii=False, indent=1)
print('videos', len(raw), 'per', len(per), 'lite', len(lite))
print(json.dumps(agg['all'], ensure_ascii=False, indent=0)[:3000])
for c, v in agg['by_channel'].items(): print(c, {w: (v[w]['changes_pm']['median'], v[w]['sfx_pm']['median'], v[w]['voice_minus_bg']['median'], v[w]['bgm_audible_share']) for w in v if w in ('hook', 'mid', 'end')})
