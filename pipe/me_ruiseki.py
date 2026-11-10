#!/usr/bin/env python3
# 別の目の指摘を回をまたいで1つの一覧にまとめる（作業AI 10/20：AI の判定は揺れるので、消えた回を「直った」と数えない）
#   一度でも出た指摘を場面ごとに並べ、各回で出た／出ないを残す。作業AIが最後にその場面を目で見て決める
#   python3 me_ruiseki.py <出力.json> <回の名前>=<proj> [<回の名前>=<proj>:<me_ai.json の差し替え> ...]
#   出力：場面ごとの {"id","t0","shiteki":[{"kai","shurui","t","naiyou"}],"deta_kai":[...]}・同じ名前の .md も書く
import os, sys, json
out = sys.argv[1]; kai = []
for a in sys.argv[2:]:
    name, rest = a.split('=', 1); proj, _, me = rest.partition(':')
    kai.append((name, proj, me or os.path.join(proj, 'work', 'me_ai.json')))
def sec(t):
    try: return sum(float(x) * 60 ** i for i, x in enumerate(reversed(str(t).split(':'))))
    except Exception: return -1.0
ba = {}
for name, proj, me in kai:
    heads = [(x['t'], x['role'].replace('EDL ', '')) for x in json.load(open(os.path.join(proj, 'intent.json'))) if str(x.get('role', '')).startswith('EDL ')]
    heads.sort()
    def scene(t):
        cur = heads[0][1] if heads else '?'
        for t0, i in heads:
            if t0 <= t + 1e-6: cur = i
        return cur
    t0s = dict((i, t) for t, i in heads)
    if os.path.exists(me):
        M = json.load(open(me))
        for m in M.get('mondai', []) + [dict(x, reigai_de_hazushita=True) for x in M.get('reigai', [])]:
            sid = scene(sec(m.get('t')))
            ba.setdefault(sid, {'id': sid, 't0': t0s.get(sid), 'shiteki': []})['shiteki'].append({'kai': name, 'shurui': '直す所' + ('（例外で外した）' if m.get('reigai_de_hazushita') else ''), 't': m.get('t'), 'naiyou': m.get('naiyou'), 'nikai': m.get('kai')})
    sp = os.path.join(proj, 'work', 'me_shot.json')
    if os.path.exists(sp):
        S = json.load(open(sp))
        for w in S.get('wakaranai', []):
            ba.setdefault(w['id'], {'id': w['id'], 't0': t0s.get(w['id']), 'shiteki': []})['shiteki'].append({'kai': name, 'shurui': '一瞬で分からない', 't': None, 'naiyou': w.get('riyuu')})
        for w in S.get('tomatta', []):
            wid = w['id'] if isinstance(w, dict) else str(w)
            ba.setdefault(wid, {'id': wid, 't0': t0s.get(wid), 'shiteki': []})['shiteki'].append({'kai': name, 'shurui': '止まった絵', 't': None, 'naiyou': w.get('riyuu') if isinstance(w, dict) else ''})
names = [k[0] for k in kai]
res = sorted(ba.values(), key=lambda b: (b['t0'] if b['t0'] is not None else 1e9))
for b in res: b['deta_kai'] = [n for n in names if any(s['kai'] == n for s in b['shiteki'])]
json.dump({'kai': names, 'bamen': res}, open(out, 'w'), ensure_ascii=False, indent=1)
L = ['# 別の目の指摘（%s で一度でも出たもの・%d場面）' % ('・'.join(names), len(res)), '']
for b in res:
    L.append('## %s（%s秒〜）出た回：%s' % (b['id'], b['t0'], '・'.join(b['deta_kai'])))
    for s in b['shiteki']: L.append('- %s %s %s：%s%s' % (s['kai'], s['shurui'], s['t'] or '', s['naiyou'], '（%s）' % s['nikai'] if s.get('nikai') else ''))
    L.append('')
open(os.path.splitext(out)[0] + '.md', 'w').write('\n'.join(L))
print('場面 %d・指摘 %d → %s' % (len(res), sum(len(b['shiteki']) for b in res), out))
