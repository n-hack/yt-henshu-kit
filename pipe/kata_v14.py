#!/usr/bin/env python3
# 表現の型を数える（v14・10/19）：場面表を走らせた記録（work/kata_v13.json の katalog・kirikae・firsts）を、手本13本の48型（kata-tehon.json）の箱に当てる
#   出す数：型の種類（48のうちいくつ使ったか）・型ごとの回数・動く部品/分・大きな切り替え/分・動く切り替えの種類・同じ型の最長連続
#   python3 kata_v14.py <作業フォルダ> [--mae]   （--mae は story_tail の直しの前＝AI が書いたままの出方で数える）
import os, sys, json, collections as co
sys.path.insert(0, os.path.expanduser('~/rin6/state/yt-anime-1014/build')); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
P = os.path.abspath(sys.argv[1]); MAE = '--mae' in sys.argv
TEHON = json.load(open(os.path.expanduser('~/rin6/state/yt-henshu/pipe-1019/v14/kata-tehon.json')))
BOXES = [r['kata'] for r in TEHON['rows']]
import importlib.util
spec = importlib.util.spec_from_file_location('zk', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zukai.py'))
src = open(spec.origin).read(); ns = {}
exec(src[src.index('ANIM_KATA = {'):], ns)   # 当て表だけ読む（絵の道具は読まない）
ANIM_KATA, PART_KATA, TR_KATA = ns['ANIM_KATA'], ns['PART_KATA'], ns['TR_KATA']
K = json.load(open(os.path.join(P, 'work', 'kata_v13.json')))
END = json.load(open(os.path.join(P, 'work', 'timing_fa.json')))['duration']
cnt = co.Counter()
for x in K.get('katalog', []):
    a = x['anim'] if MAE else x.get('anim_ato', x['anim'])
    if ANIM_KATA.get(a): cnt[ANIM_KATA[a]] += 1
    if PART_KATA.get(x['fn']): cnt[PART_KATA[x['fn']]] += 1
    if x.get('zukai') and x['zukai'] in BOXES: cnt[x['zukai']] += 1
    if x['fn'] in ('photo',): cnt['実写・写真'] += 1
TRL = K['kirikae']
KIND2 = {'全消し（1コマ）': '全消し（1コマ）', '字・帯だけ差し替え': '字幕・帯だけ差し替え', '前を残して足す': '前を残して足す', '重ねる（後ろをぼかす・暗くする）': '暗い地に大字（重ね）', '実写・画面・写真へ': '実写・写真'}
for x in TRL:
    if x['kind'] in KIND2: cnt[KIND2[x['kind']]] += 1
    if x.get('tr'): cnt[TR_KATA.get(x['tr'], x['tr'])] += 1
    if x['kind'] == '動く切り替え' and not x.get('tr'): pass
    ji = x.get('ji')
    if ji in BOXES: cnt[ji] += 1
    if ji == '写真の地': cnt['実写・写真'] += 1; cnt['カメラがゆっくり寄る'] += 1   # 写真の地は photo(zoom=(1.0,1.08)) でゆっくり寄る
for x in K.get('jiban', []): cnt[x] += 1
# 前を残して足す以外で「新しい画面」になった数：v13 以前の記録には ji が無い（明るい地・暗い地の区別だけ story から取れない）
BIG = ('全消し（1コマ）', '動く切り替え', '実写・画面・写真へ', '重ねる（後ろをぼかす・暗くする）')
trc = co.Counter(x['kind'] for x in TRL); trk = co.Counter(x['tr'] for x in TRL if x.get('tr'))
# 同じ型の最長連続（場面に最初に出る部品の型）
def kata_of(x):
    a = x['anim'] if MAE else x.get('anim_ato', x['anim'])
    if a == 'grow' and x.get('zukai'): return x['zukai']
    return ANIM_KATA.get(a, a)
F = {}
for x in K.get('katalog', []): F.setdefault(round(x['t'], 3), x)
seq = [kata_of(F[t]) for t in sorted(F)]
best = run = 0; prev = None; runs = co.Counter()
for k in seq:
    run = run + 1 if k == prev else 1; prev = k; best = max(best, run)
    if run == 3: runs[k] += 1
used = [b for b in BOXES if cnt.get(b)]
out = {'型の種類': len(used), '型の箱': len(BOXES), '使っていない型': [b for b in BOXES if not cnt.get(b)], '型ごとの回数': {b: cnt.get(b, 0) for b in BOXES},
       '動く部品': len(K.get('katalog', [])), '動く部品/分': round(len(K.get('katalog', [])) / END * 60, 1), '場面（切り替えの記録）': len(TRL),
       '切り替え/分（場面が替わる回数）': round(len(TRL) / END * 60, 1), '大きな切り替え/分（予定）': round(sum(trc.get(k, 0) for k in BIG) / END * 60, 1),
       '切り替え方': dict(trc), '動く切り替えの種類': dict(trk), '同じ型の最長連続': best, '3回以上続いた型': dict(runs), '場面の最初の部品の型の種類': len(set(seq)), '秒': END}
json.dump(out, open(os.path.join(P, 'work', 'kata_v14%s.json' % ('-mae' if MAE else '')), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in out.items() if k != '型ごとの回数'}, ensure_ascii=False))
