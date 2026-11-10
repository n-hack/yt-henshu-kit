# 手本の作者さんの手本15本（ref/tehon15.jsonl）の間の長さ：narration/ref_raw.json（ref_measure.py が分けた声から測った窓ごとの間）から15本の分だけ取る
#   間＝common.silences（声の大きい所から30dB下・0.06秒以上）。文間＝書き起こしの文の境・文中＝文の中（強調前・場面は文間に入れる）
#   （元の声 kata/raw は内蔵を空ける作業で Drive へ移り、10/19 19:5x に読めなかったため、測った結果の方を使う）
import json, numpy as np
d = json.load(open('~/rin6/tools/yt-henshu/narration/ref_raw.json'))
ids = {json.loads(l)['r']['hon'].replace('.mp4', '') for l in open('~/rin6/state/yt-evervsl-1019/ref/tehon15.jsonl')}
sel = [w for w in d if w['id'] in ids]
out = {'文中': [], '文間': []}; sp = 0.0
for w in sel:
    for p in w['pause']:
        out['文中' if p['kind'] == '文中' else '文間'].append(p['len'])
    sp += sum(s['art'] for s in w['sent']) + sum(p['len'] for p in w['pause'])
res = {'本数': len({w['id'] for w in sel}), '窓': len(sel)}
for k, v in out.items():
    v = np.array(v); res[k] = {'n': len(v), **{'p%d' % p: round(float(np.percentile(v, p)), 3) for p in (10, 25, 50, 75, 90, 95)},
                               'grid': [round(float(q), 3) for q in np.percentile(v, np.arange(101))]}
allv = np.array(out['文中'] + out['文間'])
res['全体'] = {'n': len(allv), '分': round(sp / 60, 1), '間の数/分': round(len(allv) / (sp / 60), 1), '0.3秒以上/分': round(float((allv >= 0.3).sum() / (sp / 60)), 2),
             '0.5秒以上/分': round(float((allv >= 0.5).sum() / (sp / 60)), 2), 'p50': round(float(np.median(allv)), 3), 'p90': round(float(np.percentile(allv, 90)), 3)}
json.dump(res, open('tehon_ma.json', 'w'), ensure_ascii=False, indent=1)
for k in ('文中', '文間', '全体'): print(k, {kk: vv for kk, vv in res[k].items() if kk != 'grid'})
