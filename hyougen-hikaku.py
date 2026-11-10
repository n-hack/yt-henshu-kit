#!/usr/bin/env python3
# 手本15本と自作を4つ（見やすさ・動きの型・見せ方・全画面挿絵）で並べる表（依頼主 10/22 20:33〜20:37）
#   python3 hyougen-hikaku.py <置き場（mieyasusa）> <自作の名前=見やすさjson:表現json> [...] [--md 出力.md] [--json 出力.json]
#   置き場/tehon/<id>.json（miyasusa-mon の結果）と 置き場/hy/<id>.json（hyougen-mon の結果）を手本として読む
import os, sys, json, glob, argparse, statistics as st
import numpy as np

TEHON = ['zRXbZG4AZ1k', '82LvNeazll0', 'kUPDyQA1pNs', 'crlzmL2m4sE', 'F0Qh6l4OQHA', 'NzjnSa2FrxU', 'iwoLSZoX7h8', 'FTC5gFfZSso', 'WLV8YtdQSeI',
         '2PoVYWZBlv4', 'NgA9DzmvZL0', '7dRZqvNGKPM', 'bA4JqhYKM58', 'zJCrYi2kRKo', 'mu6YEEFlteI']

def kou(mi, hy):
    """1本の値（表の行ごと）"""
    sec = hy['秒']; mn = sec / 60
    T = [x for x in mi['全部'] if x['telop']]
    cs = sorted(x['c_min'] for x in T)
    aka = [x for x in mi['赤の一覧'] if any(s.startswith(('真っ赤', '赤', '似た色')) for s in x['naze'])]
    return {
        '見やすさ：テロップの出/分': round(sum(1 for x in T if x['box'][1] + x['box'][3] / 2 < 0.8) / mn, 1),   # 下2割（字幕帯）は除く：依頼主のルール「テロップ全部」で字幕は常に出るので手本と比べない
        '見やすさ：明るさの差3未満の出の割合': round(sum(1 for c in cs if c < 3.0) / max(1, len(cs)), 3),
        '見やすさ：明るさの差4.5未満の出の割合': round(sum(1 for c in cs if c < 4.5) / max(1, len(cs)), 3),
        '見やすさ：明るさの差の下から5%': round(float(np.percentile(cs, 5)), 2) if cs else None,
        '見やすさ：似た色の出': sum(1 for x in mi['赤の一覧'] if any(s.startswith('似た色') for s in x['naze'])),
        '見やすさ：重なりの出': sum(1 for x in mi['赤の一覧'] if any(s.startswith('重なり') for s in x['naze'])),
        '動き：型の種類（3回以上）': hy['動きの型']['①型の種類（3回以上）'],
        '動き：同じ型の連続の最長': hy['動きの型']['②同じ型の連続の最長'],
        '動き：型が切り替わる平均秒': hy['動きの型']['③型が切り替わる平均の秒数'],
        '動き：1分ごとの型の種類': hy['動きの型']['④1分ごとの型の種類（平均）'],
        '動き：出来事/分': hy['動きの型']['動きの出来事/分'],
        '動き：「出し」の割合': round(hy['動きの型']['型ごと'].get('出し', 0) / max(1, hy['動きの型']['出来事の数']), 3),
        '見せ方：種類（2場面以上）': hy['見せ方']['①見せ方の種類（2場面以上）'],
        '見せ方：同じ見せ方の連続の最長': hy['見せ方']['②同じ見せ方の連続の最長'],
        '見せ方：文字だけの時間の割合': hy['見せ方']['③文字だけの時間の割合'],
        '全画面挿絵：回/分': hy['全画面挿絵']['出た回数/分'],
        '全画面挿絵：時間の割合': hy['全画面挿絵']['時間の割合'],
    }

HOUKOU = {'動き：型の種類（3回以上）': '下', '動き：1分ごとの型の種類': '下', '見せ方：種類（2場面以上）': '下', '全画面挿絵：回/分': '下', '全画面挿絵：時間の割合': '下',
          '動き：同じ型の連続の最長': '上', '動き：「出し」の割合': '上', '見せ方：同じ見せ方の連続の最長': '上', '見せ方：文字だけの時間の割合': '上', '見やすさ：テロップの出/分': '両'}
def mon(v):
    """門：手本15本の範囲（zettai/hyougen15.json）。下＝最小より少ないと止める／上＝最大より多いと止める／両＝範囲の外で止める"""
    R = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'zettai', 'hyougen15.json')))['範囲']; ng = []
    for k, h in HOUKOU.items():
        x = v.get(k); r = R.get(k)
        if x is None or r is None: continue
        if h in ('下', '両') and x < r['最小']: ng.append('%s %s ＜ 手本の最小 %s' % (k, x, r['最小']))
        if h in ('上', '両') and x > r['最大']: ng.append('%s %s ＞ 手本の最大 %s' % (k, x, r['最大']))
    return ng

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--mon':   # hyougen-hikaku.py --mon <見やすさjson> <表現json>
        v = kou(json.load(open(sys.argv[2])), json.load(open(sys.argv[3]))); ng = mon(v)
        print(json.dumps(v, ensure_ascii=False))
        print('動き・見せ方・全画面挿絵の門：' + ('合格' if not ng else '不合格（' + '・'.join(ng) + '）'))
        sys.exit(1 if ng else 0)
    ap = argparse.ArgumentParser(); ap.add_argument('oki'); ap.add_argument('jisaku', nargs='*'); ap.add_argument('--md'); ap.add_argument('--json')
    a = ap.parse_args()
    R = {}
    for t in TEHON:
        m, h = os.path.join(a.oki, 'tehon', t + '.json'), os.path.join(a.oki, 'hy', t + '.json')
        if os.path.exists(m) and os.path.exists(h): R[t] = kou(json.load(open(m)), json.load(open(h)))
    J = {}
    for s in a.jisaku:
        na, p = s.split('=', 1); m, h = p.split(':', 1); J[na] = kou(json.load(open(m)), json.load(open(h)))
    keys = list(next(iter(R.values())).keys())
    rows = []
    for k in keys:
        v = [R[t][k] for t in R if R[t][k] is not None]
        rows.append({'項目': k, '手本の中央値': round(st.median(v), 3), '手本の最小': min(v), '手本の最大': max(v), **{n: J[n][k] for n in J}})
    out = {'手本の本数': len(R), '表': rows, '手本ごと': R, '自作': J}
    if a.json: json.dump(out, open(a.json, 'w'), ensure_ascii=False, indent=1)
    L = ['| 項目 | 手本 中央値 | 手本 範囲 | ' + ' | '.join(J) + ' |', '|---|---|---|' + '---|' * len(J)]
    for r in rows: L.append('| %s | %s | %s〜%s | %s |' % (r['項目'], r['手本の中央値'], r['手本の最小'], r['手本の最大'], ' | '.join(str(r[n]) for n in J)))
    txt = '手本 %d 本（全編）と同じ道具で測った値\n\n' % len(R) + '\n'.join(L) + '\n'
    if a.md: open(a.md, 'w').write(txt)
    print(txt)
