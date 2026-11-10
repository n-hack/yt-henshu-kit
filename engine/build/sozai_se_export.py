#!/usr/bin/env python3
# 見本の効果音ライブラリを書き出す → sozai/se/<役割>.wav（＋候補 <役割>_b.wav）と sozai/se/index.tsv（どの動画の何秒から取ったか）
# 役割はまとまりごとに「鳴った瞬間の画面」（sozai/work/se_sheet_*.jpg）を作業AIが見て決めた
import json, os, glob, wave, subprocess, numpy as np
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Z = np.load(os.path.join(BASE, 'sozai/work/se_cand.npz'), allow_pickle=True); M = json.loads(str(Z['meta']))
CL = json.load(open(os.path.join(BASE, 'sozai/work/se_clusters.json')))
ROLE = {  # 役割: ([まとまり番号], 説明, 長さの上限秒)
    'telop':        ([1, 4, 21, 22], 'テロップ・座布団の文字が出る（いちばん多い基本の音）', 1.0),
    'pon':          ([3, 13, 0], '人物・イラスト・札が出る（ポン）', 0.8),
    'pon_hi':       ([40, 46, 34], '問いの札・吹き出し・短い強調（高いポン）', 0.8),
    'don':          ([20, 28, 10], '言い切りの大きな斜体（ドン）', 1.2),
    'don_long':     ([17], '言い切りの大きな斜体・余韻つき（ドーン）', 2.2),
    'kira':         ([8], '金の大きな数字・実績（キラーン）', 1.5),
    'kira_hi':      ([18, 16], '答え・マーカーが引かれる（高いキラッ）', 1.2),
    'whoosh':       ([2, 6, 31], '場面の丸ごと転換', 2.0),
    'kokuchi':      ([45, 23], '重大告知への切り替え（重大告知の4文字）', 2.2),
    'kokuchi_title':([41, 33, 26, 32], '告知の企画名・日付の画面が出る', 2.5),
    'kokuchi_line': ([25, 14], '告知の暗い地で白い文が替わる', 2.0),
    'gentei':       ([19], '告知の「1日限定」など赤い限定の文字', 2.0),
    'cta':          ([37], 'LINE登録・特典の受け取り画面（締めの行動）', 2.0),
    'shime':        ([5], '締めの画面（勉強会でお待ち・ご視聴ありがとう）へ', 2.0),
    'fukidashi':    ([35], '暗い地の人物に考える吹き出しが出る', 1.2),
}
SR = 44100
def rd(p):
    w = wave.open(p); return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
def db(x): return float(20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9))
def recut(m, maxlen):
    d = json.load(open(os.path.join(BASE, 'kata/raw', m['vid'], 'data.json')))
    w = [w for w in d['windows'] if w['name'] == m['win']][0]
    bg = rd(os.path.join(BASE, 'kata/raw', m['vid'], 'w' + m['win'], 'bg.wav'))
    t = m['t'] - w['t0']; nxt = [o['t'] - w['t0'] for o in w['onsets'] if o['t'] - w['t0'] > t + 0.12 and o['over_local_db'] >= 6]
    L = min(maxlen, (nxt[0] - t - 0.03) if nxt else maxlen)
    i0 = int((t - 0.03) * SR); y = bg[i0:i0 + int((L + 0.03) * SR)].copy()
    floor = db(bg[i0 - int(0.3 * SR):i0])
    # 後ろの床（BGM）を落とす：音の大きさが床+6dB を割ったところから 0.12 秒でフェードアウト
    hop = 441; e = np.array([db(y[k:k + hop]) for k in range(0, len(y) - hop, hop)])
    pk = e.max(); below = np.where((np.arange(len(e)) > 5) & (e < max(floor + 6, pk - 42)))[0]
    end = (below[0] * hop + int(0.12 * SR)) if len(below) else len(y)
    y = y[:min(len(y), end)]; f = min(len(y), int(0.12 * SR)); y[-f:] *= np.linspace(1, 0, f) ** 2
    y[:64] *= np.linspace(0, 1, 64)
    return y / (np.abs(y).max() + 1e-9) * 0.89, floor, pk, len(y) / SR
_cache = {}
def stems(vid, win):
    k = (vid, win)
    if k not in _cache:
        _cache.clear()
        _cache[k] = (rd(os.path.join(BASE, 'kata/raw', vid, 'w' + win, 'bg.wav')), rd(os.path.join(BASE, 'kata/raw', vid, 'w' + win, 'vocals.wav')))
    return _cache[k]
_wt0 = {}
def leak(i):
    # 声の漏れ：声を抜いた音と声の音の「300〜3000Hz の大きさの動き」が似ていれば、声が混じっている
    m = M[i]
    if (m['vid'], m['win']) not in _wt0:
        d = json.load(open(os.path.join(BASE, 'kata/raw', m['vid'], 'data.json')))
        for w in d['windows']: _wt0[(m['vid'], w['name'])] = w['t0']
    bg, vo = stems(m['vid'], m['win']); t = m['t'] - _wt0[(m['vid'], m['win'])]
    i0, i1 = int((t + 0.05) * SR), int((t + 0.05 + max(0.4, min(m['L'], 1.5))) * SR)
    fr = np.fft.rfftfreq(1024, 1 / SR); band = (fr > 300) & (fr < 3000)
    def env(x): return np.array([np.log((np.abs(np.fft.rfft(x[k:k + 1024] * np.hanning(1024))) ** 2)[band].sum() + 1e-12) for k in range(i0, min(i1, len(x)) - 1024, 441)])
    a, b = env(bg), env(vo)
    if len(a) < 5 or a.std() < 1e-6 or b.std() < 1e-6: return 0.0
    return float(np.corrcoef(a, b)[0, 1])
def score(i):
    m = M[i]; return (m['pk'] - m['pre']) + (8 if m['voice'] < -40 else 0) + (4 if m['voice'] < -32 else 0) + min(m['L'], 1.0) * 6
os.makedirs(os.path.join(BASE, 'sozai/se'), exist_ok=True)
rows = ['役割\tファイル\t説明\t動画\tチャンネル\t秒\t長さ\t直前の床dB\t声dB\t声の漏れ(相関)\tまとまり（何本で使用）']
for role, (cls, desc, mx) in ROLE.items():
    cand = sorted({i for c in cls for i in CL[c]['members']}, key=lambda i: -score(i))[:40]
    lk = {i: (leak(i) if M[i]['voice'] > -40 else 0.0) for i in cand}
    cand = sorted(cand, key=lambda i: -(score(i) - 40 * max(0, lk[i] - 0.25)))
    used = set(); got = 0
    for i in cand:
        m = M[i]
        if m['vid'] in used: continue
        y, floor, pk, L = recut(m, mx)
        if L < 0.12: continue
        name = role + ('' if got == 0 else '_' + 'bcd'[got - 1])
        p = os.path.join(BASE, 'sozai/se', name + '.wav')
        with wave.open(p, 'wb') as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())
        c_of = [c for c in cls if i in CL[c]['members']][0]
        rows.append('\t'.join(map(str, [role, name + '.wav', desc, m['vid'], m['ch'], '%.2f' % m['t'], '%.2f' % L, '%.1f' % floor, '%.1f' % m['voice'], '%.2f' % lk[i], '#%d（%d本）' % (c_of, CL[c_of]['videos'])])))
        used.add(m['vid']); got += 1
        if got == 3: break
open(os.path.join(BASE, 'sozai/se/index.tsv'), 'w').write('\n'.join(rows) + '\n')
print('\n'.join(rows))
